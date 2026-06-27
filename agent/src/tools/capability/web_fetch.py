from __future__ import annotations

import re
from typing import Any

import httpx


def _fallback_extract(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_url(url: str, max_chars: int = 50000, timeout_sec: int = 30) -> str:
    with httpx.Client(follow_redirects=True, timeout=timeout_sec) as client:
        resp = client.get(url)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")

        if "pdf" in content_type.lower():
            return _extract_pdf(resp.content, max_chars)

        html = resp.text
        try:
            import trafilatura

            text = trafilatura.extract(html, include_links=True) or ""
        except ImportError:
            text = ""

        if not text:
            text = _fallback_extract(html)

        return text[:max_chars]


def _extract_pdf(content: bytes, max_chars: int) -> str:
    try:
        from pypdf import PdfReader
        import io

        reader = PdfReader(io.BytesIO(content))
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        return "\n".join(pages)[:max_chars]
    except ImportError:
        return "[PDF content - install pypdf for extraction]"


def create_web_fetch_tool(config: dict[str, Any]):
    from langchain_core.tools import tool

    max_chars = config.get("max_chars", 50000)
    timeout_sec = config.get("timeout_sec", 30)

    @tool
    def web_fetch(url: str, max_chars_override: int = 0) -> str:
        """Fetch and extract readable text content from a URL (HTML or PDF)."""
        limit = max_chars_override or max_chars
        try:
            return fetch_url(url, max_chars=limit, timeout_sec=timeout_sec)
        except httpx.HTTPError as e:
            return f"Failed to fetch {url}: {e}"

    return web_fetch
