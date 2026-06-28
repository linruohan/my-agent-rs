from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlparse

from infra.search_context import (
    build_official_site_queries,
    enrich_search_query,
    get_search_region,
    infer_official_domains,
    is_official_priority_query,
    merge_results_prefer_official,
)
from tools.capability.web_search_selector import resolve_search_backend

FREE_DDGS_ENGINES = frozenset(
    {"duckduckgo", "brave", "google", "bing", "startpage", "mojeek", "yandex", "wikipedia"}
)


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


@dataclass
class SearchRequest:
    query: str
    max_results: int = 5
    allowed_domains: list[str] | None = None
    region: str = "wt-wt"
    timelimit: str | None = None
    ddgs_backend: str | None = None


class SearchBackend(Protocol):
    def search(self, request: SearchRequest) -> list[SearchResult]: ...


def _ddgs_client():
    from ddgs import DDGS

    return DDGS()


def _parse_ddgs_items(
    items,
    *,
    max_results: int,
    allowed_domains: list[str] | None,
) -> list[SearchResult]:
    results: list[SearchResult] = []
    for item in items:
        url = item.get("href", item.get("link", ""))
        if allowed_domains and not _url_matches_domains(url, allowed_domains):
            continue
        results.append(
            SearchResult(
                title=item.get("title", ""),
                url=url,
                snippet=item.get("body", item.get("snippet", "")),
            )
        )
        if len(results) >= max_results:
            break
    return results


class DdgsEngineBackend:
    """Free text search via ddgs engines (duckduckgo, brave, google, bing, ...)."""

    def __init__(self, engine: str):
        self.engine = engine

    def search(self, request: SearchRequest) -> list[SearchResult]:
        engine = request.ddgs_backend or self.engine
        ddgs = _ddgs_client()
        try:
            items = ddgs.text(
                request.query,
                max_results=request.max_results,
                region=request.region,
                timelimit=request.timelimit,
                backend=engine,
            )
            return _parse_ddgs_items(
                items,
                max_results=request.max_results,
                allowed_domains=request.allowed_domains,
            )
        except Exception as exc:
            raise RuntimeError(f"{engine} search failed: {exc}") from exc


class DuckDuckGoBackend(DdgsEngineBackend):
    def __init__(self):
        super().__init__("duckduckgo")


def _url_matches_domains(url: str, domains: list[str]) -> bool:
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return any(host == domain or host.endswith(f".{domain}") for domain in domains)


class MockSearchBackend:
    """For testing without network."""

    def __init__(self, responses: dict[str, list[SearchResult]] | None = None):
        self.responses = responses or {}
        self.requests: list[SearchRequest] = []

    def search(self, request: SearchRequest) -> list[SearchResult]:
        self.requests.append(request)
        if request.query in self.responses:
            return self.responses[request.query][: request.max_results]
        return [
            SearchResult(
                title=f"Result for {request.query}",
                url="https://example.com/1",
                snippet=f"Mock search result about {request.query}",
            )
        ][: request.max_results]


class TavilyBackend:
    """Tavily search API backend (requires TAVILY_API_KEY)."""

    def search(self, request: SearchRequest) -> list[SearchResult]:
        api_key = os.environ.get("TAVILY_API_KEY", "")
        if not api_key:
            raise RuntimeError("TAVILY_API_KEY not configured")

        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        kwargs: dict[str, Any] = {
            "query": request.query,
            "max_results": request.max_results,
        }
        if request.allowed_domains:
            kwargs["include_domains"] = request.allowed_domains
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
    """Self-hosted or public SearXNG instance backend."""

    def __init__(self, base_url: str = "http://127.0.0.1:8080"):
        self.base_url = base_url.rstrip("/")

    def search(self, request: SearchRequest) -> list[SearchResult]:
        import httpx

        params = {"q": request.query, "format": "json", "categories": "general"}
        resp = httpx.get(f"{self.base_url}/search", params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        results: list[SearchResult] = []
        for item in data.get("results", [])[: request.max_results]:
            url = item.get("url", "")
            if request.allowed_domains and not _url_matches_domains(
                url, request.allowed_domains
            ):
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
    "mock": MockSearchBackend(),
}


def _ensure_engine_backend(name: str) -> SearchBackend:
    if name not in _backends:
        _backends[name] = DdgsEngineBackend(name)
    return _backends[name]


def register_search_backend(name: str, backend: SearchBackend) -> None:
    _backends[name] = backend


def get_search_backend(name: str, config: dict[str, Any] | None = None) -> SearchBackend:
    if name == "tavily":
        return TavilyBackend()
    if name == "searxng":
        cfg = config or {}
        return SearXNGBackend(cfg.get("searxng_url", "http://127.0.0.1:8080"))
    if name in FREE_DDGS_ENGINES or name == "duckduckgo":
        return _ensure_engine_backend(name)
    if name not in _backends:
        raise ValueError(f"Unknown search backend: {name}")
    return _backends[name]


def _backend_chain(config: dict[str, Any]) -> list[str]:
    primary = resolve_search_backend(config)
    fallbacks = config.get("fallback_backends") or []
    chain: list[str] = []
    for name in [primary, *fallbacks]:
        if name and name not in chain and name not in {"auto", "fastest"}:
            chain.append(name)

    if config.get("backend") in {"auto", "fastest"}:
        for name in config.get("free_backends") or []:
            if name and name not in chain and name not in {"auto", "fastest"}:
                chain.append(name)

    if os.environ.get("TAVILY_API_KEY"):
        chain.append("tavily")
    return chain


def _search_with_backend_chain(
    query: str,
    cfg: dict[str, Any],
    *,
    limit: int,
    allowed_domains: list[str] | None,
    region: str,
    timelimit: str | None,
) -> tuple[list[SearchResult], list[str]]:
    errors: list[str] = []

    for backend_name in _backend_chain(cfg):
        if backend_name == "tavily" and not os.environ.get("TAVILY_API_KEY"):
            continue
        request = SearchRequest(
            query=query,
            max_results=limit,
            allowed_domains=allowed_domains,
            region=region,
            timelimit=timelimit,
            ddgs_backend=backend_name if backend_name in FREE_DDGS_ENGINES else None,
        )
        try:
            backend = get_search_backend(backend_name, cfg)
            results = backend.search(request)
            if results:
                return results, errors
        except Exception as exc:
            errors.append(f"{backend_name}: {exc}")

    return [], errors


def _dedupe_results(results: list[SearchResult]) -> list[SearchResult]:
    seen: set[str] = set()
    unique: list[SearchResult] = []
    for item in results:
        if item.url in seen:
            continue
        seen.add(item.url)
        unique.append(item)
    return unique


def run_web_search(
    query: str,
    config: dict[str, Any] | None = None,
    *,
    max_results: int | None = None,
) -> list[SearchResult]:
    """Run search with timezone region, query enrichment, and official-site priority."""
    cfg = config or {}
    limit = max_results or cfg.get("max_results", 5)
    region = get_search_region(cfg)
    timelimit = cfg.get("timelimit")
    enriched_query = enrich_search_query(query)
    errors: list[str] = []

    if is_official_priority_query(query):
        official_domains = infer_official_domains(query)
        if official_domains:
            official_results: list[SearchResult] = []
            for site_query in build_official_site_queries(query, official_domains):
                domain = site_query.split("site:", 1)[1].split(" ", 1)[0]
                results, attempt_errors = _search_with_backend_chain(
                    site_query,
                    cfg,
                    limit=limit,
                    allowed_domains=[domain],
                    region=region,
                    timelimit=timelimit,
                )
                errors.extend(attempt_errors)
                official_results.extend(results)

            official_results = _dedupe_results(official_results)
            if len(official_results) >= min(2, limit):
                return official_results[:limit]

            general_results, attempt_errors = _search_with_backend_chain(
                enriched_query,
                cfg,
                limit=limit,
                allowed_domains=cfg.get("allowed_domains") or None,
                region=region,
                timelimit=timelimit,
            )
            errors.extend(attempt_errors)
            merged = merge_results_prefer_official(
                official_results,
                general_results,
                official_domains=official_domains,
                limit=limit,
            )
            if merged:
                return merged

    results, attempt_errors = _search_with_backend_chain(
        enriched_query,
        cfg,
        limit=limit,
        allowed_domains=cfg.get("allowed_domains") or None,
        region=region,
        timelimit=timelimit,
    )
    errors.extend(attempt_errors)
    if results:
        return results

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

    @tool
    def web_search(query: str, max_results_override: int = 0) -> str:
        """Search the web for current information.

        Auto-selects the fastest free search provider, uses the user's timezone region,
        enriches time-sensitive queries with the current year, and prioritizes official
        websites for release/feature questions.
        """
        limit = max_results_override or max_results
        try:
            results = run_web_search(query, config, max_results=limit)
        except Exception as exc:
            return (
                f"Web search failed for query '{query}'. "
                f"Try web_fetch on a known official URL instead. Details: {exc}"
            )
        text, _ = format_results_with_citations(results)
        return text

    return web_search
