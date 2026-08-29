import time
from typing import Any, Optional, Dict

_in_memory_cache: Dict[str, Dict[str, Any]] = {}

async def cache_set(key: str, value: Any, ttl_seconds: int = 3600):
    """Stores key-value in cache with TTL expiry."""
    expires_at = time.time() + ttl_seconds
    _in_memory_cache[key] = {
        "value": value,
        "expires_at": expires_at
    }

async def cache_get(key: str) -> Optional[Any]:
    """Retrieves key from cache if not expired."""
    entry = _in_memory_cache.get(key)
    if not entry:
        return None
    if time.time() > entry["expires_at"]:
        _in_memory_cache.pop(key, None)
        return None
    return entry["value"]

async def cache_delete(key: str):
    """Deletes key from cache."""
    _in_memory_cache.pop(key, None)
