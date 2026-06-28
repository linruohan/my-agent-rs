from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    from playwright.sync_api import sync_playwright

    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

_EXTRACT_IMAGES_JS = """
() => {
  const items = [];
  const seen = new Set();

  function addItem(title, thumbUrl, pageUrl) {
    const url = thumbUrl || pageUrl;
    if (!url || seen.has(url)) return;
    seen.add(url);
    items.push({
      title: (title || '').trim().slice(0, 120),
      thumb_url: thumbUrl || url,
      page_url: pageUrl || '',
    });
  }

  for (const li of document.querySelectorAll('li[data-objurl], li.imgitem, .imgitem')) {
    const objUrl = li.getAttribute('data-objurl') || li.dataset?.objurl || '';
    const thumbUrl =
      li.getAttribute('data-thumburl') ||
      li.dataset?.thumburl ||
      li.querySelector('img')?.src ||
      objUrl;
    const pageUrl = li.getAttribute('data-fromurl') || li.dataset?.fromurl || '';
    const title =
      li.getAttribute('data-title') ||
      li.dataset?.title ||
      li.querySelector('img')?.alt ||
      '';
    addItem(title, thumbUrl, pageUrl);
  }

  if (items.length === 0) {
    for (const img of document.querySelectorAll('#imgid img, .imgpage img, .imgbox img')) {
      const src = img.src || img.getAttribute('data-imgurl') || '';
      if (!src || src.startsWith('data:')) continue;
      addItem(img.alt || '', src, img.closest('a')?.href || '');
    }
  }

  return items;
}
"""


@dataclass
class ImageSearchResult:
    title: str
    thumb_url: str
    page_url: str


def _build_search_url(query: str) -> str:
    return f"https://image.baidu.com/search/index?tn=baiduimage&word={quote(query)}"


def _normalize_url(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    if url.startswith("//"):
        return "https:" + url
    return url


def _parse_extracted(raw_items: list[dict[str, str]]) -> list[ImageSearchResult]:
    results: list[ImageSearchResult] = []
    for item in raw_items:
        thumb = _normalize_url(item.get("thumb_url", ""))
        page = _normalize_url(item.get("page_url", ""))
        if not thumb and not page:
            continue
        results.append(
            ImageSearchResult(
                title=item.get("title", "") or "图片",
                thumb_url=thumb or page,
                page_url=page,
            )
        )
    return results


def format_image_results(
    query: str,
    results: list[ImageSearchResult],
) -> tuple[str, list[dict[str, str]]]:
    if not results:
        return f'未在百度图片找到与 "{query}" 相关的结果。', []

    lines = [f'百度图片搜索 "{query}" 共 {len(results)} 条结果：', ""]
    citations: list[dict[str, str]] = []

    for i, item in enumerate(results, 1):
        title = item.title or f"图片 {i}"
        lines.append(f"{i}. {title}")
        lines.append(f"![{title}]({item.thumb_url})")
        if item.page_url:
            lines.append(f"Source: {item.page_url}")
            citations.append({"url": item.page_url, "title": title})
        else:
            lines.append(f"Source: {item.thumb_url}")
            citations.append({"url": item.thumb_url, "title": title})
        lines.append("")

    return "\n".join(lines).strip(), citations


def run_baidu_image_search(
    query: str,
    config: dict[str, Any] | None = None,
    *,
    max_results: int | None = None,
    scrape_fn=None,
) -> list[ImageSearchResult]:
    """Search Baidu Images via Playwright. scrape_fn is injectable for tests."""
    cfg = config or {}
    limit = max_results or cfg.get("max_results", 8)
    timeout_ms = int(cfg.get("timeout_sec", 30)) * 1000
    headless = cfg.get("headless", True)

    if scrape_fn is not None:
        return scrape_fn(query, cfg)[:limit]

    if not _PLAYWRIGHT_AVAILABLE:
        raise RuntimeError(
            "Playwright 未安装。请运行: pip install -e \".[browser]\" && playwright install chromium"
        )

    url = _build_search_url(query)
    raw_items: list[dict[str, str]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            context = browser.new_context(
                user_agent=_USER_AGENT,
                locale="zh-CN",
                viewport={"width": 1280, "height": 900},
            )
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(1500)
            page.evaluate("window.scrollBy(0, 600)")
            page.wait_for_timeout(800)
            try:
                page.wait_for_selector(
                    "li[data-objurl], .imgitem, #imgid img, .imgpage img",
                    timeout=min(timeout_ms, 10000),
                )
            except PlaywrightTimeout:
                pass
            raw_items = page.evaluate(_EXTRACT_IMAGES_JS)
        finally:
            browser.close()

    return _parse_extracted(raw_items)[:limit]


def create_baidu_image_search_tool(config: dict[str, Any]):
    from langchain_core.tools import tool

    max_results = config.get("max_results", 8)

    @tool
    def baidu_image_search(query: str, max_results_override: int = 0) -> str:
        """Search Baidu Images (百度图片) for pictures matching a query.

        Use this when the user asks to find, search, or show images/photos/pictures,
        especially via Baidu or for Chinese queries. Returns thumbnail URLs as Markdown
        images that can be displayed in chat.

        Args:
            query: Image search keywords, e.g. "皮卡丘", "sunset beach".
            max_results_override: Optional limit on number of images (0 = use default).
        """
        limit = max_results_override or max_results
        try:
            results = run_baidu_image_search(query, config, max_results=limit)
            text, _ = format_image_results(query, results)
            return text
        except Exception as e:
            return f"百度图片搜索失败: {e}"

    return baidu_image_search
