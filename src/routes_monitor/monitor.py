import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from .key_manager import KeyManager

logger = logging.getLogger(__name__)


class TrafficMonitor:
    """Core traffic monitoring class using Google Routes API v2."""
    
    API_ENDPOINT = "https://routes.googleapis.com/directions/v2:computeRoutes"
    FIELD_MASK = "routes,geocodingResults,fallbackInfo"
    
    # Interval presets (seconds)
    INTERVALS = {
        "peak": 15 * 60,       # 08:00-11:00, 17:00-20:00
        "inter_peak": 45 * 60, # 11:00-17:00, 20:00-23:00
        "off_peak": 120 * 60,  # 23:00-08:00
    }
    
    def __init__(self, config_path: str, output_dir: str = "data/raw"):
        self.config_path = Path(config_path)
        self.output_dir = Path(output_dir)
        self.routes: list[dict] = []
        self.key_manager = KeyManager()
        
        self._load_config()
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_config(self):
        """Load routes from JSON config."""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        self.routes = config.get('routes', [])
        logger.info(f"Loaded {len(self.routes)} routes from {self.config_path}")
    
    def determine_interval(self) -> int:
        """Variable Interval Sampling Strategy based on time of day."""
        hour = datetime.now().hour
        
        if (8 <= hour < 11) or (17 <= hour < 20):
            return self.INTERVALS["peak"]
        elif (11 <= hour < 17) or (20 <= hour < 23):
            return self.INTERVALS["inter_peak"]
        else:
            return self.INTERVALS["off_peak"]
    
    def fetch_route(self, route: dict) -> dict | None:
        """Execute a single API call for a route."""
        api_key = self.key_manager.get_active_key()
        
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": self.FIELD_MASK,
        }
        
        payload = {
            "origin": {"location": {"latLng": route["origin"]}},
            "destination": {"location": {"latLng": route["destination"]}},
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_AWARE_OPTIMAL",
            "departureTime": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "computeAlternativeRoutes": True,
        }
        
        try:
            response = requests.post(self.API_ENDPOINT, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            self.key_manager.increment_usage(api_key)
            self._save_response(route, data, api_key)
            self._log_result(route, data)
            
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API error for {route.get('id')}: {e}")
            return None
    
    def _save_response(self, route: dict, data: dict, key: str):
        """Save raw API response to file."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        route_id = route.get('id', 'unknown')
        file_path = self.output_dir / f"{route_id}_{timestamp}.json"
        
        payload = {
            "timestamp": datetime.now().isoformat(),
            "route_id": route_id,
            "route_name": route.get('name'),
            "api_key_suffix": key[-4:],
            "response": data,
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    
    def _log_result(self, route: dict, data: dict):
        """Log route duration results."""
        if 'routes' not in data:
            logger.warning(f"No route found for {route.get('id')}")
            return
        
        r = data['routes'][0]
        duration = int(r.get('duration', '0s').rstrip('s'))
        static = int(r.get('staticDuration', '0s').rstrip('s'))
        delay = duration - static
        
        logger.info(f"Route {route['id']}: {duration}s (delay: {delay}s)")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {route['id']}: {duration}s (delay: {delay}s)")
    
    def run(self):
        """Main monitoring loop."""
        logger.info("Starting traffic monitor...")
        print("Monitor started. Press Ctrl+C to stop.")
        
        try:
            while True:
                cycle_start = time.time()
                interval = self.determine_interval()
                
                logger.info(f"Collection cycle starting. Interval: {interval/60:.0f} min")
                
                for route in self.routes:
                    self.fetch_route(route)
                    time.sleep(0.2)  # Rate limiting
                
                elapsed = time.time() - cycle_start
                sleep_time = max(0, interval - elapsed)
                
                print(f"Cycle complete. Next in {sleep_time/60:.1f} min")
                time.sleep(sleep_time)
                
        except KeyboardInterrupt:
            logger.info("Monitor stopped by user")
            print("\nStopped.")
