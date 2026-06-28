from __future__ import annotations

import sys
from pathlib import Path

AGENT_SRC = Path(__file__).resolve().parents[1] / "agent" / "src"
if str(AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(AGENT_SRC))

from infra.search_context import (
    build_official_site_queries,
    enrich_search_query,
    get_search_region,
    infer_official_domains,
    is_official_priority_query,
    merge_results_prefer_official,
)
from tools.capability.web_search import SearchResult


def test_get_search_region_explicit_override():
    assert get_search_region({"region": "jp-jp"}) == "jp-jp"


def test_get_search_region_from_env(monkeypatch):
    monkeypatch.setenv("AGENT_TIMEZONE", "Asia/Shanghai")
    assert get_search_region({}) == "cn-zh"


def test_infer_official_domains_for_python():
    domains = infer_official_domains("python 3.14 新特性")
    assert "python.org" in domains
    assert "docs.python.org" in domains


def test_enrich_search_query_adds_current_year():
    from infra.time_context import get_current_datetime

    now = get_current_datetime()
    enriched = enrich_search_query("python latest release notes")
    assert str(now.year) in enriched


def test_enrich_search_query_skips_year_for_specific_version():
    query = "Python 3.12 release date features official"
    assert enrich_search_query(query) == query


def test_build_official_site_queries():
    queries = build_official_site_queries("python 3.14 features", ["python.org"])
    assert queries[0].startswith("site:python.org")


def test_is_official_priority_query():
    assert is_official_priority_query("Python 3.14 release notes")
    assert not is_official_priority_query("写一个快排算法")


def test_merge_results_prefer_official():
    official = [
        SearchResult("Official", "https://python.org/release", "from official"),
    ]
    general = [
        SearchResult("Blog", "https://example.com/post", "blog post"),
        SearchResult("Docs", "https://docs.python.org/3.14", "docs"),
    ]
    merged = merge_results_prefer_official(
        official,
        general,
        official_domains=["python.org", "docs.python.org"],
        limit=3,
    )
    assert merged[0].url.startswith("https://python.org")
    assert any("docs.python.org" in item.url for item in merged)
