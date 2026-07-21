"""
In-process response cache for repeated model calls and repeated questions.

Sprint 3: exact-match key on (task, normalized content). This is the load-bearing
cheap win before a real semantic/vector cache (Stage 6/7 "raising the ceiling").
"""
from __future__ import annotations

import hashlib
import threading
import time
from typing import Any, Optional


def _normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


def make_key(task: str, content: str, extra: str = "") -> str:
    raw = f"{task}|{_normalize(content)}|{extra}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ResponseCache:
    """Thread-safe TTL cache with hit/miss counters for token-economics reports."""

    def __init__(self, ttl_seconds: float = 3600.0, max_entries: int = 2048):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        now = time.time()
        with self._lock:
            item = self._store.get(key)
            if not item:
                self.misses += 1
                return None
            expires_at, value = item
            if expires_at < now:
                del self._store[key]
                self.misses += 1
                return None
            self.hits += 1
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if len(self._store) >= self.max_entries:
                # Drop oldest ~10% by expiry
                ordered = sorted(self._store.items(), key=lambda kv: kv[1][0])
                for k, _ in ordered[: max(1, self.max_entries // 10)]:
                    self._store.pop(k, None)
            self._store[key] = (time.time() + self.ttl_seconds, value)

    def stats(self) -> dict:
        with self._lock:
            return {
                "hits": self.hits,
                "misses": self.misses,
                "size": len(self._store),
                "hit_rate": (self.hits / (self.hits + self.misses))
                if (self.hits + self.misses) else 0.0,
            }

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self.hits = 0
            self.misses = 0


# Process-wide caches used by gateway + pipeline
llm_cache = ResponseCache(ttl_seconds=1800, max_entries=1024)
question_cache = ResponseCache(ttl_seconds=1800, max_entries=512)
