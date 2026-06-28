from __future__ import annotations

import pytest

from infra.rate_limit import SlidingWindowLimiter, check_rag_ingest_allowed


def test_sliding_window_limiter():
    limiter = SlidingWindowLimiter(max_calls=2, window_sec=60)
    assert limiter.allow("a") is True
    assert limiter.allow("a") is True
    assert limiter.allow("a") is False
    assert limiter.allow("b") is True


def test_rag_ingest_rate_limit(monkeypatch):
    import infra.rate_limit as rl

    rl._rag_ingest_limiter = None
    monkeypatch.setattr(
        "infra.rate_limit.load_rag_config",
        lambda: {"ingest": {"rate_limit_per_minute": 2}},
    )

    assert check_rag_ingest_allowed("ws-1") == (True, 0)
    assert check_rag_ingest_allowed("ws-1") == (True, 0)
    allowed, retry = check_rag_ingest_allowed("ws-1")
    assert allowed is False
    assert retry >= 1


def test_rag_ingest_unlimited_when_zero(monkeypatch):
    import infra.rate_limit as rl

    rl._rag_ingest_limiter = None
    monkeypatch.setattr(
        "infra.rate_limit.load_rag_config",
        lambda: {"ingest": {"rate_limit_per_minute": 0}},
    )
    for _ in range(5):
        assert check_rag_ingest_allowed("ws-x") == (True, 0)
