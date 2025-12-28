import argparse
import logging
import sys
from pathlib import Path

from .monitor import TrafficMonitor


def setup_logging(log_file: str = "traffic_monitor.log"):
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(),
        ]
    )


def main():
    parser = argparse.ArgumentParser(description="Traffic route monitoring using Google Routes API")
    parser.add_argument(
        "-c", "--config",
        default="config/routes.json",
        help="Path to routes config JSON (default: config/routes.json)"
    )
    parser.add_argument(
        "-o", "--output",
        default="data/raw",
        help="Output directory for raw responses (default: data/raw)"
    )
    parser.add_argument(
        "--log-file",
        default="traffic_monitor.log",
        help="Log file path (default: traffic_monitor.log)"
    )
    
    args = parser.parse_args()
    
    setup_logging(args.log_file)
    
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}")
        print("Create one from config/routes.example.json")
        sys.exit(1)
    
    try:
        monitor = TrafficMonitor(str(config_path), args.output)
        monitor.run()
    except ValueError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
