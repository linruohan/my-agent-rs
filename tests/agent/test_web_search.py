from __future__ import annotations

import sys
from pathlib import Path

AGENT_SRC = Path(__file__).resolve().parents[1] / "agent" / "src"
if str(AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(AGENT_SRC))

from tools.capability.web_search import (
    MockSearchBackend,
    SearchRequest,
    SearchResult,
    format_results_with_citations,
    get_search_backend,
    register_search_backend,
    run_web_search,
)
from infra.search_context import enrich_search_query


def test_mock_search_backend():
    backend = MockSearchBackend()
    results = backend.search(SearchRequest(query="Rust programming", max_results=3))
    assert len(results) == 1
    assert "Rust programming" in results[0].title


def test_format_results_with_citations():
    backend = MockSearchBackend()
    results = backend.search(SearchRequest(query="test query"))
    text, citations = format_results_with_citations(results)
    assert "test query" in text
    assert len(citations) == 1
    assert citations[0]["url"].startswith("https://")


def test_get_search_backend_mock():
    backend = get_search_backend("duckduckgo")
    assert backend is not None


def test_run_web_search_uses_mock_backend():
    mock = MockSearchBackend()
    register_search_backend("mock_chain", mock)
    results = run_web_search("Rust", {"backend": "mock_chain", "max_results": 2, "region": "cn-zh"})
    assert len(results) == 1
    assert "Rust" in results[0].title
    assert mock.requests[0].region == "cn-zh"


def test_run_web_search_official_first_with_mock():
    from infra.search_context import build_official_site_queries, enrich_search_query

    enriched = enrich_search_query("python 3.14 新特性")
    site_queries = build_official_site_queries("python 3.14 新特性", ["python.org", "docs.python.org", "peps.python.org"])
    official = SearchResult(
        "Python 3.14.0",
        "https://www.python.org/downloads/release/python-3140/",
        "Official release page",
    )
    mock = MockSearchBackend(
        {
            **{site_query: [official] for site_query in site_queries},
            enriched: [
                SearchResult(
                    "Blog post",
                    "https://example.com/python-314",
                    "Third-party blog",
                )
            ],
        }
    )
    register_search_backend("mock_official", mock)

    results = run_web_search(
        "python 3.14 新特性",
        {"backend": "mock_official", "max_results": 3, "region": "cn-zh"},
    )

    assert results
    assert any("python.org" in item.url for item in results)
    assert any("site:python.org" in req.query for req in mock.requests)
