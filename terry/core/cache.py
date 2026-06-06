"""Caching system - reduce API calls and costs."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any


class Cache:
    """Simple file-based cache with TTL support."""

    def __init__(self, cache_dir: Path | None = None, default_ttl: int = 3600):
        """Initialize cache.

        Args:
            cache_dir: Directory to store cache files
            default_ttl: Default time-to-live in seconds (1 hour)
        """
        self.cache_dir = cache_dir or Path.home() / ".terry" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_ttl = default_ttl

        # In-memory cache for fast access
        self.memory_cache: dict[str, tuple[Any, float]] = {}

    def _generate_key(self, data: Any) -> str:
        """Generate cache key from data.

        Args:
            data: Data to hash

        Returns:
            Hash string
        """
        # Convert to JSON string for consistent hashing
        data_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(data_str.encode()).hexdigest()

    def get(self, key: str) -> Any | None:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        # Check memory cache first
        if key in self.memory_cache:
            value, expiry = self.memory_cache[key]
            if time.time() < expiry:
                return value
            else:
                # Expired, remove from memory
                del self.memory_cache[key]

        # Check disk cache
        cache_file = self.cache_dir / f"{key}.json"
        if not cache_file.exists():
            return None

        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            expiry = data.get("expiry", 0)

            if time.time() < expiry:
                value = data.get("value")
                # Add to memory cache
                self.memory_cache[key] = (value, expiry)
                return value
            else:
                # Expired, delete file
                cache_file.unlink()
                return None
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if None)
        """
        if ttl is None:
            ttl = self.default_ttl

        expiry = time.time() + ttl

        # Store in memory
        self.memory_cache[key] = (value, expiry)

        # Store on disk
        cache_file = self.cache_dir / f"{key}.json"
        data = {
            "key": key,
            "value": value,
            "expiry": expiry,
            "created": time.time(),
        }

        cache_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def delete(self, key: str) -> bool:
        """Delete value from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted
        """
        # Remove from memory
        if key in self.memory_cache:
            del self.memory_cache[key]

        # Remove from disk
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                cache_file.unlink()
                return True
            except Exception:
                return False

        return False

    def clear(self) -> int:
        """Clear all cache entries.

        Returns:
            Number of entries cleared
        """
        # Clear memory cache
        count = len(self.memory_cache)
        self.memory_cache.clear()

        # Clear disk cache
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
                count += 1
            except Exception:
                pass

        return count

    def cleanup_expired(self) -> int:
        """Remove expired entries from cache.

        Returns:
            Number of entries removed
        """
        removed = 0
        current_time = time.time()

        # Clean memory cache
        expired_keys = [
            key for key, (_, expiry) in self.memory_cache.items()
            if current_time >= expiry
        ]
        for key in expired_keys:
            del self.memory_cache[key]
            removed += 1

        # Clean disk cache
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                expiry = data.get("expiry", 0)

                if current_time >= expiry:
                    cache_file.unlink()
                    removed += 1
            except Exception:
                # Corrupted file, delete it
                try:
                    cache_file.unlink()
                    removed += 1
                except Exception:
                    pass

        return removed

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        disk_files = list(self.cache_dir.glob("*.json"))
        current_time = time.time()

        # Count expired entries
        expired_count = 0
        for cache_file in disk_files:
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                if current_time >= data.get("expiry", 0):
                    expired_count += 1
            except Exception:
                expired_count += 1

        return {
            "memory_entries": len(self.memory_cache),
            "disk_entries": len(disk_files),
            "expired_entries": expired_count,
            "active_entries": len(disk_files) - expired_count,
            "cache_dir": str(self.cache_dir),
        }


class LLMCache:
    """Specialized cache for LLM API calls."""

    def __init__(self, cache: Cache | None = None):
        """Initialize LLM cache.

        Args:
            cache: Cache instance to use
        """
        self.cache = cache or Cache()

    def get_response(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        model: str = "default",
    ) -> Any | None:
        """Get cached LLM response.

        Args:
            messages: Conversation messages
            system: System prompt
            tools: Tool definitions
            model: Model name

        Returns:
            Cached response or None
        """
        cache_key_data = {
            "type": "llm_response",
            "messages": messages,
            "system": system,
            "tools": tools,
            "model": model,
        }

        key = self.cache._generate_key(cache_key_data)
        return self.cache.get(key)

    def set_response(
        self,
        messages: list[dict[str, Any]],
        response: Any,
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        model: str = "default",
        ttl: int = 3600,
    ) -> None:
        """Cache LLM response.

        Args:
            messages: Conversation messages
            response: LLM response to cache
            system: System prompt
            tools: Tool definitions
            model: Model name
            ttl: Time-to-live in seconds
        """
        cache_key_data = {
            "type": "llm_response",
            "messages": messages,
            "system": system,
            "tools": tools,
            "model": model,
        }

        key = self.cache._generate_key(cache_key_data)
        self.cache.set(key, response, ttl=ttl)


class ToolCache:
    """Specialized cache for tool execution results."""

    def __init__(self, cache: Cache | None = None):
        """Initialize tool cache.

        Args:
            cache: Cache instance to use
        """
        self.cache = cache or Cache()

    def get_result(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any | None:
        """Get cached tool result.

        Args:
            tool_name: Tool name
            arguments: Tool arguments

        Returns:
            Cached result or None
        """
        cache_key_data = {
            "type": "tool_result",
            "tool": tool_name,
            "arguments": arguments,
        }

        key = self.cache._generate_key(cache_key_data)
        return self.cache.get(key)

    def set_result(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        result: Any,
        ttl: int = 300,  # 5 minutes default for tools
    ) -> None:
        """Cache tool result.

        Args:
            tool_name: Tool name
            arguments: Tool arguments
            result: Tool result to cache
            ttl: Time-to-live in seconds
        """
        cache_key_data = {
            "type": "tool_result",
            "tool": tool_name,
            "arguments": arguments,
        }

        key = self.cache._generate_key(cache_key_data)
        self.cache.set(key, result, ttl=ttl)


# Global cache instances
_cache_instance: Cache | None = None
_llm_cache_instance: LLMCache | None = None
_tool_cache_instance: ToolCache | None = None


def get_cache(cache_dir: Path | None = None) -> Cache:
    """Get or create the global cache instance.

    Args:
        cache_dir: Optional cache directory override

    Returns:
        Cache instance
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = Cache(cache_dir)
    return _cache_instance


def get_llm_cache() -> LLMCache:
    """Get or create the global LLM cache instance.

    Returns:
        LLMCache instance
    """
    global _llm_cache_instance
    if _llm_cache_instance is None:
        _llm_cache_instance = LLMCache(get_cache())
    return _llm_cache_instance


def get_tool_cache() -> ToolCache:
    """Get or create the global tool cache instance.

    Returns:
        ToolCache instance
    """
    global _tool_cache_instance
    if _tool_cache_instance is None:
        _tool_cache_instance = ToolCache(get_cache())
    return _tool_cache_instance


def set_cache(instance: Cache) -> None:
    """Inject a custom Cache instance (for testing/DI)."""
    global _cache_instance
    _cache_instance = instance


def set_llm_cache(instance: LLMCache) -> None:
    """Inject a custom LLMCache instance (for testing/DI)."""
    global _llm_cache_instance
    _llm_cache_instance = instance


def set_tool_cache(instance: ToolCache) -> None:
    """Inject a custom ToolCache instance (for testing/DI)."""
    global _tool_cache_instance
    _tool_cache_instance = instance


def reset_cache() -> None:
    """Reset all cache singletons (forces re-initialization on next get)."""
    global _cache_instance, _llm_cache_instance, _tool_cache_instance
    _cache_instance = None
    _llm_cache_instance = None
    _tool_cache_instance = None
