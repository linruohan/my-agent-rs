from __future__ import annotations

import sys
from pathlib import Path

AGENT_SRC = Path(__file__).resolve().parents[1] / "agent" / "src"
if str(AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(AGENT_SRC))

from tools.capability import web_search_selector as selector
from tools.capability.web_search import SearchRequest, SearchResult, register_search_backend
from tools.capability.web_search import MockSearchBackend


class _LatencyMockBackend(MockSearchBackend):
    def __init__(self, delay: float, responses: dict[str, list[SearchResult]] | None = None):
        super().__init__(responses)
        self.delay = delay

    def search(self, request: SearchRequest) -> list[SearchResult]:
        import time

        time.sleep(self.delay)
        return super().search(request)


def test_resolve_search_backend_uses_cached_value(monkeypatch):
    selector.reset_search_backend_cache()
    calls = {"count": 0}

    def fake_benchmark(config):
        calls["count"] += 1
        return "brave"

    monkeypatch.setattr(selector, "benchmark_free_backends", fake_benchmark)
    cfg = {"backend": "auto", "benchmark_ttl_sec": 3600}

    assert selector.resolve_search_backend(cfg) == "brave"
    assert selector.resolve_search_backend(cfg) == "brave"
    assert calls["count"] == 1


def test_benchmark_free_backends_picks_fastest(monkeypatch):
    register_search_backend("fast_mock", _LatencyMockBackend(0.01))
    register_search_backend("slow_mock", _LatencyMockBackend(0.2))

    chosen = selector.benchmark_free_backends(
        {
            "free_backends": ["slow_mock", "fast_mock"],
            "benchmark_query": "latency test",
            "benchmark_timeout_sec": 5,
            "region": "cn-zh",
        }
    )
    assert chosen == "fast_mock"
