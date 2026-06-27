from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


class SearchBackend(Protocol):
    def search(
        self,
        query: str,
        max_results: int = 5,
        allowed_domains: list[str] | None = None,
    ) -> list[SearchResult]: ...


class DuckDuckGoBackend:
    def search(
        self,
        query: str,
        max_results: int = 5,
        allowed_domains: list[str] | None = None,
    ) -> list[SearchResult]:
        from duckduckgo_search import DDGS

        results: list[SearchResult] = []
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=max_results):
                url = item.get("href", item.get("link", ""))
                if allowed_domains and not any(d in url for d in allowed_domains):
                    continue
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=url,
                        snippet=item.get("body", item.get("snippet", "")),
                    )
                )
        return results


class MockSearchBackend:
    """For testing without network."""

    def search(
        self,
        query: str,
        max_results: int = 5,
        allowed_domains: list[str] | None = None,
    ) -> list[SearchResult]:
        return [
            SearchResult(
                title=f"Result for {query}",
                url="https://example.com/1",
                snippet=f"Mock search result about {query}",
            )
        ][:max_results]


class TavilyBackend:
    """Tavily search API backend (requires TAVILY_API_KEY)."""

    def search(
        self,
        query: str,
        max_results: int = 5,
        allowed_domains: list[str] | None = None,
    ) -> list[SearchResult]:
        import os

        api_key = os.environ.get("TAVILY_API_KEY", "")
        if not api_key:
            raise RuntimeError("TAVILY_API_KEY not configured")

        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        kwargs: dict[str, Any] = {"query": query, "max_results": max_results}
        if allowed_domains:
            kwargs["include_domains"] = allowed_domains
        response = client.search(**kwargs)
        results: list[SearchResult] = []
        for item in response.get("results", []):
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", item.get("snippet", "")),
                )
            )
        return results


class SearXNGBackend:
    """Self-hosted SearXNG instance backend."""

    def __init__(self, base_url: str = "http://127.0.0.1:8080"):
        self.base_url = base_url.rstrip("/")

    def search(
        self,
        query: str,
        max_results: int = 5,
        allowed_domains: list[str] | None = None,
    ) -> list[SearchResult]:
        import httpx

        params = {"q": query, "format": "json", "categories": "general"}
        resp = httpx.get(f"{self.base_url}/search", params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        results: list[SearchResult] = []
        for item in data.get("results", [])[:max_results]:
            url = item.get("url", "")
            if allowed_domains and not any(d in url for d in allowed_domains):
                continue
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=url,
                    snippet=item.get("content", item.get("snippet", "")),
                )
            )
        return results


_backends: dict[str, SearchBackend] = {
    "duckduckgo": DuckDuckGoBackend(),
    "mock": MockSearchBackend(),
}


def register_search_backend(name: str, backend: SearchBackend) -> None:
    _backends[name] = backend


def get_search_backend(name: str, config: dict[str, Any] | None = None) -> SearchBackend:
    if name == "tavily":
        return TavilyBackend()
    if name == "searxng":
        cfg = config or {}
        return SearXNGBackend(cfg.get("searxng_url", "http://127.0.0.1:8080"))
    if name not in _backends:
        raise ValueError(f"Unknown search backend: {name}")
    return _backends[name]


def format_results_with_citations(results: list[SearchResult]) -> tuple[str, list[dict[str, str]]]:
    if not results:
        return "No results found.", []

    lines = []
    citations = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. **{r.title}**\n   {r.snippet}\n   Source: {r.url}")
        citations.append({"title": r.title, "url": r.url})
    return "\n\n".join(lines), citations


def create_web_search_tool(config: dict[str, Any]):
    from langchain_core.tools import tool

    backend_name = config.get("backend", "duckduckgo")
    max_results = config.get("max_results", 5)
    allowed_domains = config.get("allowed_domains") or None

    @tool
    def web_search(query: str, max_results_override: int = 0) -> str:
        """Search the web for current information. Returns summarized results with source URLs."""
        backend = get_search_backend(backend_name, config)
        limit = max_results_override or max_results
        results = backend.search(query, max_results=limit, allowed_domains=allowed_domains)
        text, _ = format_results_with_citations(results)
        return text

    return web_search
