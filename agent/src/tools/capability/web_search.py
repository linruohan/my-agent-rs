from __future__ import annotations

import os
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
    """DuckDuckGo text search via the maintained `ddgs` package."""

    def search(
        self,
        query: str,
        max_results: int = 5,
        allowed_domains: list[str] | None = None,
    ) -> list[SearchResult]:
        last_error: Exception | None = None

        for factory in (_ddgs_client, _legacy_ddgs_client):
            try:
                ddgs = factory()
            except ImportError as exc:
                last_error = exc
                continue

            results: list[SearchResult] = []
            try:
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
                if results:
                    return results
            except Exception as exc:
                last_error = exc
                continue

        if last_error is not None:
            raise RuntimeError(f"DuckDuckGo search failed: {last_error}") from last_error
        return []


def _ddgs_client():
    from ddgs import DDGS

    return DDGS()


def _legacy_ddgs_client():
    from duckduckgo_search import DDGS

    return DDGS()


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


def _backend_chain(config: dict[str, Any]) -> list[str]:
    primary = config.get("backend", "duckduckgo")
    fallbacks = config.get("fallback_backends") or []
    chain: list[str] = []
    for name in [primary, *fallbacks, "tavily"]:
        if name and name not in chain:
            chain.append(name)
    return chain


def run_web_search(
    query: str,
    config: dict[str, Any] | None = None,
    *,
    max_results: int | None = None,
) -> list[SearchResult]:
    """Run search with configured backend chain and graceful fallback."""
    cfg = config or {}
    limit = max_results or cfg.get("max_results", 5)
    allowed_domains = cfg.get("allowed_domains") or None
    errors: list[str] = []

    for backend_name in _backend_chain(cfg):
        if backend_name == "tavily" and not os.environ.get("TAVILY_API_KEY"):
            continue
        try:
            backend = get_search_backend(backend_name, cfg)
            results = backend.search(
                query,
                max_results=limit,
                allowed_domains=allowed_domains,
            )
            if results:
                return results
        except Exception as exc:
            errors.append(f"{backend_name}: {exc}")

    if errors:
        raise RuntimeError("; ".join(errors))
    return []


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

    max_results = config.get("max_results", 5)
    allowed_domains = config.get("allowed_domains") or None

    @tool
    def web_search(query: str, max_results_override: int = 0) -> str:
        """Search the web for current information. Returns summarized results with source URLs."""
        limit = max_results_override or max_results
        try:
            results = run_web_search(
                query,
                {**config, "allowed_domains": allowed_domains},
                max_results=limit,
            )
        except Exception as exc:
            return (
                f"Web search failed for query '{query}'. "
                f"Try web_fetch on a known official URL instead. Details: {exc}"
            )
        text, _ = format_results_with_citations(results)
        return text

    return web_search
