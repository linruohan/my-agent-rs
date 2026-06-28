from __future__ import annotations

import sys
from pathlib import Path

AGENT_SRC = Path(__file__).resolve().parents[1] / "agent" / "src"
if str(AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(AGENT_SRC))

from tools.capability.web_search import (
    MockSearchBackend,
    format_results_with_citations,
    get_search_backend,
    run_web_search,
)


def test_mock_search_backend():
    backend = MockSearchBackend()
    results = backend.search("Rust programming", max_results=3)
    assert len(results) == 1
    assert "Rust programming" in results[0].title


def test_format_results_with_citations():
    backend = MockSearchBackend()
    results = backend.search("test query")
    text, citations = format_results_with_citations(results)
    assert "test query" in text
    assert len(citations) == 1
    assert citations[0]["url"].startswith("https://")


def test_get_search_backend_mock():
    backend = get_search_backend("duckduckgo")
    assert backend is not None


def test_run_web_search_uses_mock_backend():
    from tools.capability import web_search as ws_mod

    ws_mod.register_search_backend("mock_chain", MockSearchBackend())
    results = run_web_search("Rust", {"backend": "mock_chain", "max_results": 2})
    assert len(results) == 1
    assert "Rust" in results[0].title
