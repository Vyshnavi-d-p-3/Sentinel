"""
In-memory webhook idempotency cache keyed by ``X-GitHub-Delivery``.

GitHub guarantees ``X-GitHub-Delivery`` is unique per delivery attempt; we keep
a bounded LRU of recent IDs so retries are cheap and don't trigger duplicate
reviews. The cache is intentionally process-local — for multi-replica
deployments swap this for a Redis-backed implementation behind the same
``mark_seen`` / ``has_seen`` interface.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict


class DeliveryCache:
    """Thread-safe TTL-LRU keyed on opaque delivery IDs."""

    def __init__(self, max_entries: int = 4096, ttl_sec: int = 24 * 3600) -> None:
        self._max = max_entries
        self._ttl = ttl_sec
        self._items: OrderedDict[str, float] = OrderedDict()
        self._lock = threading.Lock()

    def has_seen(self, delivery_id: str) -> bool:
        if not delivery_id:
            return False
        now = time.time()
        with self._lock:
            self._purge_expired(now)
            ts = self._items.get(delivery_id)
            return ts is not None

    def mark_seen(self, delivery_id: str) -> None:
        if not delivery_id:
            return
        now = time.time()
        with self._lock:
            self._purge_expired(now)
            self._items[delivery_id] = now
            self._items.move_to_end(delivery_id)
            while len(self._items) > self._max:
                self._items.popitem(last=False)

    def _purge_expired(self, now: float) -> None:
        cutoff = now - self._ttl
        # Iterate from oldest (left) and pop until we hit a non-expired entry.
        while self._items:
            key, ts = next(iter(self._items.items()))
            if ts >= cutoff:
                break
            self._items.popitem(last=False)


# Module-level singleton. ``main.py`` and the webhook router share this.
delivery_cache = DeliveryCache()
