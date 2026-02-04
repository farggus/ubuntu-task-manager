"""Shared cache for process iteration data.

This module provides a cached wrapper around psutil.process_iter() to avoid
duplicate iterations across collectors (SystemCollector and ProcessesCollector).
"""

import threading
import time
from typing import Any, Dict, List, Optional

import psutil

# Cache TTL in seconds - short to ensure fresh data
CACHE_TTL = 2.0

# Module-level cache with thread safety
_cache_lock = threading.Lock()
_cache_data: Optional[List[Dict[str, Any]]] = None
_cache_timestamp: float = 0.0
_cache_attrs: Optional[List[str]] = None


def get_process_list(attrs: List[str]) -> List[Dict[str, Any]]:
    """Get cached list of process info dictionaries.

    Args:
        attrs: List of process attributes to fetch (e.g., ['pid', 'status', 'name'])

    Returns:
        List of process info dictionaries with requested attributes.
        If cached data has all requested attrs and is fresh, returns cached data.
        Otherwise, fetches fresh data and updates cache.
    """
    global _cache_data, _cache_timestamp, _cache_attrs

    with _cache_lock:
        now = time.monotonic()
        cache_valid = (
            _cache_data is not None
            and (now - _cache_timestamp) < CACHE_TTL
            and _cache_attrs is not None
            and set(attrs).issubset(set(_cache_attrs))
        )

        if cache_valid:
            return _cache_data  # type: ignore

        # Fetch fresh data
        new_data = []
        for p in psutil.process_iter(attrs):
            try:
                new_data.append(p.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        _cache_data = new_data
        _cache_timestamp = now
        _cache_attrs = attrs

        return new_data


def get_process_stats() -> Dict[str, int]:
    """Get process count statistics from cached data.

    Returns:
        Dictionary with 'total' and 'zombies' counts.
    """
    processes = get_process_list(["status"])

    total = len(processes)
    zombies = sum(1 for p in processes if p.get("status") == psutil.STATUS_ZOMBIE)

    return {"total": total, "zombies": zombies}


def invalidate_cache() -> None:
    """Force cache invalidation (for testing or manual refresh)."""
    global _cache_data, _cache_timestamp, _cache_attrs

    with _cache_lock:
        _cache_data = None
        _cache_timestamp = 0.0
        _cache_attrs = None
