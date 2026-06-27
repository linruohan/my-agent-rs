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


_backends: dict[str, SearchBackend] = {
    "duckduckgo": DuckDuckGoBackend(),
    "mock": MockSearchBackend(),
}


def get_search_backend(name: str) -> SearchBackend:
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
        backend = get_search_backend(backend_name)
        limit = max_results_override or max_results
        results = backend.search(query, max_results=limit, allowed_domains=allowed_domains)
        text, _ = format_results_with_citations(results)
        return text

    return web_search
