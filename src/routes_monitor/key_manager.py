import logging
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class KeyManager:
    """Manages API key rotation and usage tracking."""
    
    DEFAULT_USAGE_LIMIT = 4800  # Safety threshold (Google limit is 5000)
    
    def __init__(self, usage_limit: int = None):
        self.usage_limit = usage_limit or self.DEFAULT_USAGE_LIMIT
        self.keys: list[str] = []
        self.usage: dict[str, int] = {}
        self.current_index = 0
        self._load_keys_from_env()
    
    def _load_keys_from_env(self):
        """Load API keys from environment variables (ROUTES_API_KEY_1, ROUTES_API_KEY_2, etc.)"""
        i = 1
        while True:
            key = os.getenv(f"ROUTES_API_KEY_{i}")
            if not key:
                break
            self.keys.append(key)
            self.usage[key] = 0
            i += 1
        
        # Fallback: single key
        if not self.keys:
            single_key = os.getenv("ROUTES_API_KEY")
            if single_key:
                self.keys.append(single_key)
                self.usage[single_key] = 0
        
        if not self.keys:
            raise ValueError("No API keys found. Set ROUTES_API_KEY or ROUTES_API_KEY_1 in .env")
        
        logger.info(f"Loaded {len(self.keys)} API key(s)")
    
    def get_active_key(self) -> str:
        """Returns a valid API key that hasn't exceeded the usage limit."""
        start_index = self.current_index
        
        while True:
            key = self.keys[self.current_index]
            
            if self.usage[key] < self.usage_limit:
                return key
            
            logger.warning(f"Key ...{key[-4:]} exhausted ({self.usage[key]} calls). Rotating.")
            self.current_index = (self.current_index + 1) % len(self.keys)
            
            if self.current_index == start_index:
                raise RuntimeError("All API keys exhausted for the month")
    
    def increment_usage(self, key: str):
        """Track a successful API call."""
        if key in self.usage:
            self.usage[key] += 1
    
    @property
    def key_count(self) -> int:
        return len(self.keys)
    
    def get_usage_summary(self) -> dict:
        """Returns usage stats for all keys."""
        return {f"...{k[-4:]}": v for k, v in self.usage.items()}
