from __future__ import annotations

import sys
from pathlib import Path

AGENT_SRC = Path(__file__).resolve().parents[1] / "agent" / "src"
if str(AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(AGENT_SRC))

from tools.capability.baidu_image_search import (
    ImageSearchResult,
    _build_search_url,
    _parse_extracted,
    create_baidu_image_search_tool,
    format_image_results,
    run_baidu_image_search,
)


def test_build_search_url():
    url = _build_search_url("皮卡丘")
    assert "image.baidu.com" in url
    assert "word=" in url


def test_parse_extracted():
    raw = [
        {"title": "皮卡丘", "thumb_url": "//img0.baidu.com/a.jpg", "page_url": "https://example.com"},
        {"title": "", "thumb_url": "", "page_url": ""},
    ]
    results = _parse_extracted(raw)
    assert len(results) == 1
    assert results[0].thumb_url == "https://img0.baidu.com/a.jpg"
    assert results[0].page_url == "https://example.com"


def test_format_image_results():
    results = [
        ImageSearchResult("皮卡丘", "https://img.example.com/1.jpg", "https://page.example.com"),
    ]
    text, citations = format_image_results("皮卡丘", results)
    assert "![皮卡丘](https://img.example.com/1.jpg)" in text
    assert "Source: https://page.example.com" in text
    assert len(citations) == 1
    assert citations[0]["url"] == "https://page.example.com"


def test_format_image_results_empty():
    text, citations = format_image_results("test", [])
    assert "未在百度图片找到" in text
    assert citations == []


def test_run_baidu_image_search_with_mock():
    def mock_scrape(query: str, cfg: dict) -> list[ImageSearchResult]:
        assert query == "皮卡丘"
        return [
            ImageSearchResult("皮卡丘1", "https://img.example.com/a.jpg", "https://page.example.com/a"),
            ImageSearchResult("皮卡丘2", "https://img.example.com/b.jpg", "https://page.example.com/b"),
        ]

    results = run_baidu_image_search(
        "皮卡丘",
        {"max_results": 1},
        scrape_fn=mock_scrape,
    )
    assert len(results) == 1
    assert results[0].title == "皮卡丘1"


def test_baidu_image_search_tool():
    def mock_scrape(query: str, cfg: dict) -> list[ImageSearchResult]:
        return [
            ImageSearchResult("test", "https://img.example.com/x.jpg", "https://page.example.com/x"),
        ]

    tool = create_baidu_image_search_tool({"max_results": 5})
    assert tool.name == "baidu_image_search"

    from tools.capability import baidu_image_search as mod

    original = mod.run_baidu_image_search

    def patched(query, config=None, *, max_results=None, scrape_fn=None):
        return original(query, config, max_results=max_results, scrape_fn=mock_scrape)

    mod.run_baidu_image_search = patched
    try:
        out = tool.invoke({"query": "测试"})
        assert "![test]" in out
        assert "Source: https://page.example.com/x" in out
    finally:
        mod.run_baidu_image_search = original
