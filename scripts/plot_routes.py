"""
Plot Tbilisi routes on a map with real-time travel times from Google Routes API v2.

Google Routes API v2 Response Structure (with polyline field mask):
{
    "routes": [{
        "duration": "1080s",           # total duration with traffic
        "staticDuration": "900s",      # duration without traffic
        "distanceMeters": 5200,
        "polyline": {
            "encodedPolyline": "encoded_string"  # decode to get route coordinates
        }
    }]
}
"""

import json
import os
import sys
import requests
import polyline
import folium
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Add src to path to import key_manager
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from routes_monitor.key_manager import KeyManager

# Load environment variables
load_dotenv()

# Configuration
CONFIG_PATH = Path(__file__).parent.parent / "config" / "routes.json"
OUTPUT_MAP_PATH = Path(__file__).parent.parent / "output" / "routes_map.html"

# Google Routes API v2 endpoint
ROUTES_API_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
FIELD_MASK = "routes.duration,routes.staticDuration,routes.distanceMeters,routes.polyline.encodedPolyline"


def load_routes_config() -> list:
    """Load routes from configuration file."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    return config["routes"]


def get_route_from_google(origin: dict, destination: dict, api_key: str) -> dict | None:
    """
    Fetch route data from Google Routes API v2.
    
    Args:
        origin: {"lat": float, "lng": float}
        destination: {"lat": float, "lng": float}
        api_key: Google Routes API key
    
    Returns:
        Dictionary with travel_time_seconds, distance_meters,
        and coordinates (list of [lat, lng] pairs)
    """
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": FIELD_MASK,
    }
    
    # Convert lat/lng to latitude/longitude format expected by Routes API
    origin_latlng = {"latitude": origin["lat"], "longitude": origin["lng"]}
    dest_latlng = {"latitude": destination["lat"], "longitude": destination["lng"]}
    
    payload = {
        "origin": {"location": {"latLng": origin_latlng}},
        "destination": {"location": {"latLng": dest_latlng}},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE_OPTIMAL",
        "departureTime": (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat().replace('+00:00', 'Z'),
    }
    
    try:
        response = requests.post(ROUTES_API_URL, headers=headers, json=payload, timeout=10)
        data = response.json()
        
        if response.status_code != 200:
            error_msg = data.get("error", {}).get("message", "Unknown error")
            print(f"  API Error: {error_msg}")
            return None
        
        if "routes" not in data or not data["routes"]:
            print(f"  API Error: No routes returned")
            return None
        
        route = data["routes"][0]
        
        # Parse duration (format: "1080s")
        duration_str = route.get("duration", "0s")
        duration_seconds = int(duration_str.rstrip("s"))
        
        static_duration_str = route.get("staticDuration", "0s")
        static_seconds = int(static_duration_str.rstrip("s"))
        
        # Get distance
        distance_meters = route.get("distanceMeters", 0)
        
        # Decode the polyline to get route coordinates
        encoded_polyline = route.get("polyline", {}).get("encodedPolyline", "")
        if encoded_polyline:
            coordinates = polyline.decode(encoded_polyline)  # Returns list of (lat, lng) tuples
        else:
            coordinates = []
        
        # Format duration text
        mins = duration_seconds // 60
        travel_time_text = f"{mins} min" if mins < 60 else f"{mins // 60} hr {mins % 60} min"
        
        # Format distance text
        if distance_meters >= 1000:
            distance_text = f"{distance_meters / 1000:.1f} km"
        else:
            distance_text = f"{distance_meters} m"
        
        return {
            "travel_time_seconds": duration_seconds,
            "static_duration_seconds": static_seconds,
            "travel_time_text": travel_time_text,
            "distance_meters": distance_meters,
            "distance_text": distance_text,
            "delay_seconds": duration_seconds - static_seconds,
            "coordinates": coordinates  # List of (lat, lng) tuples
        }
        
    except requests.RequestException as e:
        print(f"  Request error: {e}")
        return None


def get_color_by_travel_time(seconds: int, distance_meters: int) -> str:
    """
    Assign color based on average speed (proxy for congestion).
    
    Green: Fast (>40 km/h)
    Yellow: Moderate (25-40 km/h)
    Orange: Slow (15-25 km/h)
    Red: Very slow (<15 km/h)
    """
    if distance_meters == 0:
        return "gray"
    
    speed_kmh = (distance_meters / 1000) / (seconds / 3600)
    
    if speed_kmh > 40:
        return "green"
    elif speed_kmh > 25:
        return "orange"
    elif speed_kmh > 15:
        return "darkorange"
    else:
        return "red"


def create_routes_map(routes_data: list) -> folium.Map:
    """
    Create a Folium map with all routes plotted.
    
    Args:
        routes_data: List of dicts with route info and coordinates
    
    Returns:
        Folium Map object
    """
    # Center map on Tbilisi
    center_lat = 41.7151
    center_lng = 44.8271
    
    m = folium.Map(
        location=[center_lat, center_lng],
        zoom_start=12,
        tiles="cartodbpositron"
    )
    
    # Add routes to map
    for route in routes_data:
        if route.get("coordinates"):
            color = get_color_by_travel_time(
                route["travel_time_seconds"],
                route["distance_meters"]
            )
            
            # Create popup content
            popup_html = f"""
            <b>{route['name']}</b><br>
            ID: {route['id']}<br>
            Travel Time: {route['travel_time_text']}<br>
            Distance: {route['distance_text']}<br>
            """
            
            # Draw the route polyline
            folium.PolyLine(
                locations=route["coordinates"],
                color=color,
                weight=4,
                opacity=0.8,
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"{route['id']}: {route['name']} ({route['travel_time_text']})"
            ).add_to(m)
            
            # Add markers for start and end
            folium.CircleMarker(
                location=route["coordinates"][0],
                radius=5,
                color="blue",
                fill=True,
                popup=f"Start: {route['name']}"
            ).add_to(m)
            
            folium.CircleMarker(
                location=route["coordinates"][-1],
                radius=5,
                color="darkred",
                fill=True,
                popup=f"End: {route['name']}"
            ).add_to(m)
    
    # Add legend
    legend_html = """
    <div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000;
                background-color: white; padding: 10px; border-radius: 5px;
                border: 2px solid grey; font-size: 14px;">
        <b>Traffic Speed</b><br>
        <i style="background: green; width: 20px; height: 10px; display: inline-block;"></i> Fast (>40 km/h)<br>
        <i style="background: orange; width: 20px; height: 10px; display: inline-block;"></i> Moderate (25-40 km/h)<br>
        <i style="background: darkorange; width: 20px; height: 10px; display: inline-block;"></i> Slow (15-25 km/h)<br>
        <i style="background: red; width: 20px; height: 10px; display: inline-block;"></i> Very Slow (<15 km/h)<br>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Add timestamp
    timestamp_html = f"""
    <div style="position: fixed; top: 10px; right: 10px; z-index: 1000;
                background-color: white; padding: 10px; border-radius: 5px;
                border: 2px solid grey; font-size: 12px;">
        <b>Tbilisi Routes Monitor</b><br>
        Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    </div>
    """
    m.get_root().html.add_child(folium.Element(timestamp_html))
    
    return m


def main():
    """Main function to fetch routes and create map."""
    try:
        key_manager = KeyManager()
    except ValueError as e:
        print(f"ERROR: {e}")
        print("Please set ROUTES_API_KEY_1 in .env file.")
        return
    
    print(f"Loading routes from {CONFIG_PATH}...")
    routes = load_routes_config()
    print(f"Found {len(routes)} routes to process.\n")
    
    routes_with_data = []
    
    for i, route in enumerate(routes, 1):
        print(f"[{i}/{len(routes)}] Fetching: {route['id']} - {route['name']}...")
        
        api_key = key_manager.get_active_key()
        route_data = get_route_from_google(
            route["origin"],
            route["destination"],
            api_key
        )
        
        if route_data:
            key_manager.increment_usage(api_key)
            routes_with_data.append({
                "id": route["id"],
                "name": route["name"],
                **route_data
            })
            delay_info = f" (delay: +{route_data['delay_seconds']}s)" if route_data['delay_seconds'] > 0 else ""
            print(f"  ✓ {route_data['travel_time_text']} | {route_data['distance_text']}{delay_info}")
        else:
            print(f"  ✗ Failed to get route data")
    
    print(f"\nSuccessfully fetched {len(routes_with_data)}/{len(routes)} routes.")
    
    # Create output directory if needed
    OUTPUT_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Create and save map
    print(f"\nCreating map...")
    map_obj = create_routes_map(routes_with_data)
    map_obj.save(str(OUTPUT_MAP_PATH))
    print(f"Map saved to: {OUTPUT_MAP_PATH}")
    
    # Also save route data as JSON for reference
    data_path = OUTPUT_MAP_PATH.with_suffix(".json")
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "routes": routes_with_data
        }, f, indent=2, ensure_ascii=False)
    print(f"Route data saved to: {data_path}")


if __name__ == "__main__":
    main()
