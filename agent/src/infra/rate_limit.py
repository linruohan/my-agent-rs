from __future__ import annotations

import time
from collections import defaultdict, deque

from infra.config import load_rag_config
from infra.metrics import inc


class SlidingWindowLimiter:
    """Simple per-key sliding window rate limiter."""

    def __init__(self, max_calls: int, window_sec: float):
        self.max_calls = max(1, max_calls)
        self.window_sec = max(1.0, window_sec)
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        bucket = self._events[key]
        while bucket and now - bucket[0] > self.window_sec:
            bucket.popleft()
        if len(bucket) >= self.max_calls:
            return False
        bucket.append(now)
        return True

    def retry_after_sec(self, key: str) -> int:
        now = time.monotonic()
        bucket = self._events.get(key)
        if not bucket:
            return 0
        oldest = bucket[0]
        wait = self.window_sec - (now - oldest)
        return max(1, int(wait) + 1)


_rag_ingest_limiter: SlidingWindowLimiter | None = None


def get_rag_ingest_limiter() -> SlidingWindowLimiter | None:
    global _rag_ingest_limiter
    cfg = load_rag_config().get("ingest", {})
    per_minute = int(cfg.get("rate_limit_per_minute", 0))
    if per_minute <= 0:
        return None
    if _rag_ingest_limiter is None:
        _rag_ingest_limiter = SlidingWindowLimiter(per_minute, 60.0)
    return _rag_ingest_limiter


def check_rag_ingest_allowed(client_key: str) -> tuple[bool, int]:
    limiter = get_rag_ingest_limiter()
    if limiter is None:
        return True, 0
    if limiter.allow(client_key):
        inc("rag.ingest.requests")
        return True, 0
    inc("rag.ingest.rate_limited")
    return False, limiter.retry_after_sec(client_key)
