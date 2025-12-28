import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from routes_monitor import TrafficMonitor, KeyManager


class TestKeyManager:
    """Tests for API key management."""
    
    def test_key_loading_from_env(self, monkeypatch):
        monkeypatch.setenv("ROUTES_API_KEY_1", "test_key_1")
        monkeypatch.setenv("ROUTES_API_KEY_2", "test_key_2")
        
        km = KeyManager()
        assert km.key_count == 2
    
    def test_key_rotation(self, monkeypatch):
        monkeypatch.setenv("ROUTES_API_KEY_1", "key1")
        monkeypatch.setenv("ROUTES_API_KEY_2", "key2")
        
        km = KeyManager(usage_limit=1)
        
        key1 = km.get_active_key()
        km.increment_usage(key1)
        
        key2 = km.get_active_key()
        assert key2 != key1
    
    def test_no_keys_raises(self, monkeypatch):
        # Clear all key env vars
        for key in list(os.environ.keys()):
            if key.startswith("ROUTES_API_KEY"):
                monkeypatch.delenv(key, raising=False)
        
        with pytest.raises(ValueError, match="No API keys found"):
            KeyManager()


class TestTrafficMonitor:
    """Tests for TrafficMonitor."""
    
    @pytest.fixture
    def config_file(self, tmp_path):
        config = {
            "routes": [
                {"id": "T01", "name": "Test", "origin": {"lat": 0, "lng": 0}, "destination": {"lat": 1, "lng": 1}}
            ]
        }
        config_path = tmp_path / "routes.json"
        config_path.write_text(json.dumps(config))
        return str(config_path)
    
    def test_load_config(self, config_file, monkeypatch):
        monkeypatch.setenv("ROUTES_API_KEY", "test")
        monitor = TrafficMonitor(config_file)
        assert len(monitor.routes) == 1
        assert monitor.routes[0]["id"] == "T01"
    
    def test_interval_determination(self, config_file, monkeypatch):
        monkeypatch.setenv("ROUTES_API_KEY", "test")
        monitor = TrafficMonitor(config_file)
        
        interval = monitor.determine_interval()
        assert interval in monitor.INTERVALS.values()
