# Routes Monitor

Traffic monitoring tool using Google Routes API v2. Tracks travel times and delays across configured routes with variable sampling intervals.

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Configure API keys (copy and edit)
cp .env.example .env

# Configure routes (copy and edit)
cp config/routes.example.json config/routes.json
```

## Usage

```bash
# Run with defaults
python -m routes_monitor.cli

# Custom config
python -m routes_monitor.cli -c config/my_routes.json -o data/my_city
```

## Project Structure

```
routes-monitor/
├── src/routes_monitor/
│   ├── __init__.py
│   ├── monitor.py      # Core TrafficMonitor class
│   ├── key_manager.py  # API key rotation
│   └── cli.py          # Command-line interface
├── config/
│   └── routes.example.json
├── tests/
├── .env.example
├── requirements.txt
└── README.md
```
