"""
Caching Utilities
Simple in-memory cache for frequent queries
"""

import logging
import time
from functools import wraps
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class SimpleCache:
    """
    Simple in-memory cache with TTL (Time To Live)

    For production, consider using Redis or Memcached
    """

    def __init__(self, default_ttl: int = 300):
        """
        Initialize cache

        Args:
            default_ttl: Default time-to-live in seconds (5 minutes)
        """
        self._cache: dict[str, tuple[Any, float]] = {}
        self.default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        if key not in self._cache:
            return None

        value, expiry = self._cache[key]

        # Check if expired
        if time.time() > expiry:
            del self._cache[key]
            return None

        return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with TTL"""
        ttl = ttl or self.default_ttl
        expiry = time.time() + ttl
        self._cache[key] = (value, expiry)

    def delete(self, key: str) -> None:
        """Delete key from cache"""
        if key in self._cache:
            del self._cache[key]

    def clear(self) -> None:
        """Clear all cache entries"""
        self._cache.clear()

    def cleanup_expired(self) -> int:
        """Remove expired entries, return count of removed items"""
        now = time.time()
        expired_keys = [key for key, (_, expiry) in self._cache.items() if now > expiry]

        for key in expired_keys:
            del self._cache[key]

        return len(expired_keys)

    def size(self) -> int:
        """Get current cache size"""
        return len(self._cache)


# Global cache instance
_cache = SimpleCache(default_ttl=300)  # 5 minutes default


def get_cache() -> SimpleCache:
    """Get global cache instance"""
    return _cache


def cached(ttl: int = 300, key_prefix: str = ""):
    """
    Decorator to cache function results

    Args:
        ttl: Time-to-live in seconds
        key_prefix: Prefix for cache key

    Usage:
        @cached(ttl=600, key_prefix="user")
        def get_user(user_id: str):
            return db.query(User).filter(User.id == user_id).first()
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{key_prefix}:{func.__name__}:{str(args)}:{str(kwargs)}"

            # Try to get from cache
            cached_value = _cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_value

            # Call function and cache result
            logger.debug(f"Cache miss: {cache_key}")
            result = func(*args, **kwargs)
            _cache.set(cache_key, result, ttl=ttl)

            return result

        return wrapper

    return decorator


def cache_key(*args, **kwargs) -> str:
    """Generate cache key from arguments"""
    key_parts = [str(arg) for arg in args]
    key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
    return ":".join(key_parts)


# Cache key generators for common queries
def user_cache_key(user_id: str) -> str:
    """Generate cache key for user"""
    return f"user:{user_id}"


def subject_cache_key(subject_id: str) -> str:
    """Generate cache key for subject"""
    return f"subject:{subject_id}"


def student_goals_cache_key(student_id: str) -> str:
    """Generate cache key for student goals"""
    return f"goals:student:{student_id}"


def student_rating_cache_key(student_id: str, subject_id: str) -> str:
    """Generate cache key for student rating"""
    return f"rating:student:{student_id}:subject:{subject_id}"


def practice_bank_items_cache_key(
    subject_id: str, difficulty_min: int, difficulty_max: int
) -> str:
    """Generate cache key for practice bank items"""
    return f"practice:bank:subject:{subject_id}:diff:{difficulty_min}-{difficulty_max}"
