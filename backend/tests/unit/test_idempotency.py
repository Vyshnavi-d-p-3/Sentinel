"""Tests for the in-memory webhook delivery cache."""

from __future__ import annotations

import time

from app.core.idempotency import DeliveryCache


def test_unseen_delivery_returns_false() -> None:
    cache = DeliveryCache()
    assert cache.has_seen("abc") is False


def test_mark_then_has_seen() -> None:
    cache = DeliveryCache()
    cache.mark_seen("abc")
    assert cache.has_seen("abc") is True
    assert cache.has_seen("xyz") is False


def test_empty_id_is_never_recorded() -> None:
    cache = DeliveryCache()
    cache.mark_seen("")
    assert cache.has_seen("") is False


def test_lru_eviction_when_capacity_exceeded() -> None:
    cache = DeliveryCache(max_entries=3)
    cache.mark_seen("a")
    cache.mark_seen("b")
    cache.mark_seen("c")
    cache.mark_seen("d")  # should evict "a" (oldest)

    assert cache.has_seen("a") is False
    assert cache.has_seen("b") is True
    assert cache.has_seen("c") is True
    assert cache.has_seen("d") is True


def test_ttl_expiry(monkeypatch) -> None:
    cache = DeliveryCache(ttl_sec=1)
    cache.mark_seen("a")
    assert cache.has_seen("a") is True

    # Fast-forward time past the TTL.
    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + 5)
    assert cache.has_seen("a") is False
