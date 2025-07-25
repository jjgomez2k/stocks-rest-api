import time
from typing import Any, Dict, Tuple, Optional

class TTLCache:
    def __init__(self, ttl_seconds: int = 300): # Default 5 minutes
        self.cache: Dict[str, Tuple[Any, float]] = {} # {key: (value, expiry_timestamp)}
        self.ttl_seconds = ttl_seconds

    def get(self, key: str) -> Optional[Any]:
        if key in self.cache:
            value, expiry_time = self.cache[key]
            if time.time() < expiry_time:
                return value
            else:
                # Cache expired, remove it
                del self.cache[key]
                return None
        return None

    def set(self, key: str, value: Any):
        expiry_time = time.time() + self.ttl_seconds
        self.cache[key] = (value, expiry_time)

    def clear(self):
        self.cache = {}