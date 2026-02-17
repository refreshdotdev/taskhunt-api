"""ETag-aware caching for GitHub API responses."""

import logging
from dataclasses import dataclass, field
from time import time
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A cache entry with ETag support."""

    data: Any
    etag: str | None = None
    timestamp: float = field(default_factory=time)


class ETagCache:
    """Cache that stores data with ETags for conditional requests.

    When GitHub returns 304 Not Modified, the cached data is still valid
    and the request doesn't count against rate limits.
    """

    def __init__(self):
        self._cache: dict[str, CacheEntry] = {}

    def get(self, key: str) -> CacheEntry | None:
        """Get a cache entry by key."""
        return self._cache.get(key)

    def get_etag(self, key: str) -> str | None:
        """Get the ETag for a cached key."""
        entry = self._cache.get(key)
        return entry.etag if entry else None

    def set(self, key: str, data: Any, etag: str | None = None) -> None:
        """Store data with optional ETag."""
        self._cache[key] = CacheEntry(data=data, etag=etag, timestamp=time())
        logger.debug(f"Cached {key} with ETag: {etag}")

    def touch(self, key: str) -> None:
        """Update timestamp for a cache entry (used when 304 received)."""
        if key in self._cache:
            self._cache[key].timestamp = time()
            logger.debug(f"Touched cache entry {key} (304 Not Modified)")

    def is_fresh(self, key: str, max_age_seconds: float) -> bool:
        """Check if a cache entry is fresh (within max_age)."""
        entry = self._cache.get(key)
        if entry is None:
            return False
        return (time() - entry.timestamp) < max_age_seconds

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()

    def invalidate(self, key: str) -> None:
        """Invalidate a specific cache entry."""
        self._cache.pop(key, None)


# Global cache instance
_cache: ETagCache | None = None


def get_cache() -> ETagCache:
    """Get the global cache instance."""
    global _cache
    if _cache is None:
        _cache = ETagCache()
    return _cache
