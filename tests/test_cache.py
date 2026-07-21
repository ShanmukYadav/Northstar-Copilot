"""Unit tests for Sprint 3 response cache — no API key required."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from gateway.cache import ResponseCache, make_key


def test_make_key_normalizes_whitespace_and_case():
    a = make_key("router", "How many  ORDERS?")
    b = make_key("router", "how many orders?")
    assert a == b


def test_cache_hit_miss_and_stats():
    c = ResponseCache(ttl_seconds=60, max_entries=10)
    assert c.get("k1") is None
    c.set("k1", {"ok": True})
    assert c.get("k1") == {"ok": True}
    stats = c.stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["size"] == 1


def test_cache_expiry():
    c = ResponseCache(ttl_seconds=0.01, max_entries=10)
    c.set("k", 123)
    import time
    time.sleep(0.05)
    assert c.get("k") is None
