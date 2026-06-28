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


def test_active_backend_list_race_mode():
    names = selector.active_backend_list(
        {
            "backend": "race",
            "free_backends": ["duckduckgo", "mojeek"],
        }
    )
    assert names == ["duckduckgo", "mojeek"]


def test_race_search_backends_uses_first_finished():
    register_search_backend("race_fast", _LatencyMockBackend(0.05))
    register_search_backend("race_slow", _LatencyMockBackend(0.5))

    request = SearchRequest(query="latency test", max_results=1, region="cn-zh")
    results, errors, winner = selector.race_search_backends(
        request,
        {
            "backend": "race",
            "free_backends": ["race_slow", "race_fast"],
            "search_timeout_sec": 5,
        },
    )

    assert winner == "race_fast"
    assert len(results) == 1
    assert not errors or all("no results" not in err for err in errors)
