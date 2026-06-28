from __future__ import annotations

import os
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

DEFAULT_FREE_BACKENDS = (
    "duckduckgo",
    "brave",
    "google",
    "bing",
    "startpage",
    "mojeek",
)


def free_backend_list(config: dict[str, Any]) -> list[str]:
    configured = config.get("free_backends")
    source = configured if isinstance(configured, list) and configured else DEFAULT_FREE_BACKENDS
    unique: list[str] = []
    seen: set[str] = set()
    for name in source:
        key = str(name)
        if key and key not in seen:
            seen.add(key)
            unique.append(key)
    return unique


def active_backend_list(config: dict[str, Any]) -> list[str]:
    """Backends to race for a search request."""
    backend = str(config.get("backend") or "auto")
    chain: list[str] = []

    if backend not in {"auto", "fastest", "race", "parallel"}:
        chain.append(backend)

    for name in config.get("fallback_backends") or []:
        if name and name not in chain:
            chain.append(str(name))

    if backend in {"auto", "fastest", "race", "parallel"} or not chain:
        for name in free_backend_list(config):
            if name not in chain:
                chain.append(name)

    if os.environ.get("TAVILY_API_KEY") and "tavily" not in chain:
        chain.append("tavily")

    return chain


@dataclass
class ProbeSearchHit:
    title: str
    url: str
    snippet: str


@dataclass
class BackendProbeResult:
    backend: str
    ok: bool
    latency_ms: float
    result_count: int
    error: str | None = None
    hits: list[ProbeSearchHit] = field(default_factory=list)
    fetched_text: str | None = None
    fetch_error: str | None = None


def _hits_from_results(results: list[Any]) -> list[ProbeSearchHit]:
    hits: list[ProbeSearchHit] = []
    for item in results:
        hits.append(
            ProbeSearchHit(
                title=str(getattr(item, "title", "") or ""),
                url=str(getattr(item, "url", "") or ""),
                snippet=str(getattr(item, "snippet", "") or ""),
            )
        )
    return hits


def _fetch_page_preview(
    url: str,
    *,
    max_chars: int = 400,
    timeout_sec: int = 15,
) -> tuple[str | None, str | None]:
    if not url:
        return None, "empty url"
    try:
        from tools.capability.web_fetch import fetch_url

        text = fetch_url(url, max_chars=max_chars, timeout_sec=timeout_sec).strip()
        if not text:
            return None, "empty page text"
        return text, None
    except Exception as exc:
        return None, str(exc)


def probe_search_backend(
    backend_name: str,
    config: dict[str, Any] | None = None,
    *,
    query: str = "hello",
    max_results: int = 3,
    fetch_page: bool = True,
    fetch_max_chars: int = 400,
) -> BackendProbeResult:
    """Probe a single search backend and report whether it returns real results."""
    from infra.search_context import get_search_region
    from tools.capability.web_search import SearchRequest

    cfg = dict(config or {})
    region = get_search_region(cfg)
    timeout_sec = float(cfg.get("search_timeout_sec") or 15)
    start = time.perf_counter()

    request = SearchRequest(
        query=query,
        max_results=max_results,
        region=region,
    )

    try:
        _, results = _search_backend_once(backend_name, request, cfg)
        latency_ms = (time.perf_counter() - start) * 1000
        if latency_ms > timeout_sec * 1000:
            return BackendProbeResult(
                backend=backend_name,
                ok=False,
                latency_ms=latency_ms,
                result_count=0,
                error="timeout",
            )
        if not results:
            return BackendProbeResult(
                backend=backend_name,
                ok=False,
                latency_ms=latency_ms,
                result_count=0,
                error="no results",
            )

        hits = _hits_from_results(results)
        fetched_text: str | None = None
        fetch_error: str | None = None
        if fetch_page and hits[0].url:
            fetched_text, fetch_error = _fetch_page_preview(
                hits[0].url,
                max_chars=fetch_max_chars,
            )

        return BackendProbeResult(
            backend=backend_name,
            ok=True,
            latency_ms=latency_ms,
            result_count=len(results),
            hits=hits,
            fetched_text=fetched_text,
            fetch_error=fetch_error,
        )
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        return BackendProbeResult(
            backend=backend_name,
            ok=False,
            latency_ms=latency_ms,
            result_count=0,
            error=str(exc),
        )


def probe_all_search_backends(
    config: dict[str, Any] | None = None,
    *,
    query: str = "hello",
    max_results: int = 3,
    fetch_page: bool = True,
    fetch_max_chars: int = 400,
) -> list[BackendProbeResult]:
    """Probe every configured free backend individually."""
    cfg = dict(config or {})
    backends = free_backend_list(cfg)
    return [
        probe_search_backend(
            name,
            cfg,
            query=query,
            max_results=max_results,
            fetch_page=fetch_page,
            fetch_max_chars=fetch_max_chars,
        )
        for name in backends
    ]


def format_probe_report(results: list[BackendProbeResult]) -> str:
    lines = ["backend       ok   ms     count  error", "----------------------------------------------"]
    for item in results:
        err = (item.error or "")[:40]
        lines.append(
            f"{item.backend:<13} {'yes' if item.ok else 'no':<4} "
            f"{item.latency_ms:6.0f} {item.result_count:<6} {err}"
        )
    return "\n".join(lines)


def format_probe_detail(result: BackendProbeResult) -> str:
    lines = [
        f"=== {result.backend} ===",
        f"ok={result.ok} latency_ms={result.latency_ms:.0f} count={result.result_count}",
    ]
    if result.error:
        lines.append(f"error: {result.error}")
        return "\n".join(lines)

    for index, hit in enumerate(result.hits, start=1):
        lines.append(f"[{index}] {hit.title}")
        if hit.snippet:
            lines.append(f"    摘要: {hit.snippet}")
        if hit.url:
            lines.append(f"    链接: {hit.url}")

    if result.fetched_text:
        lines.append("    网页正文:")
        lines.append(f"    {result.fetched_text}")
    elif result.fetch_error:
        lines.append(f"    网页抓取失败: {result.fetch_error}")

    return "\n".join(lines)


def format_probe_report_detailed(results: list[BackendProbeResult]) -> str:
    blocks = [format_probe_detail(item) for item in results]
    summary = format_probe_report(results)
    return summary + "\n\n" + "\n\n".join(blocks)


def _search_backend_once(
    backend_name: str,
    request: Any,
    config: dict[str, Any],
) -> tuple[str, list[Any]]:
    from tools.capability.web_search import FREE_DDGS_ENGINES, SearchRequest, get_search_backend

    if backend_name == "tavily" and not os.environ.get("TAVILY_API_KEY"):
        return backend_name, []

    req = SearchRequest(
        query=request.query,
        max_results=request.max_results,
        allowed_domains=request.allowed_domains,
        region=request.region,
        timelimit=request.timelimit,
        ddgs_backend=backend_name if backend_name in FREE_DDGS_ENGINES else None,
    )
    backend = get_search_backend(backend_name, config)
    results = backend.search(req)
    return backend_name, results


def race_search_backends(
    request: Any,
    config: dict[str, Any],
) -> tuple[list[Any], list[str], str | None]:
    """Query all backends in parallel; return the first successful result."""
    backends = active_backend_list(config)
    if not backends:
        return [], ["no backends configured"], None

    timeout_sec = float(config.get("search_timeout_sec") or 15)
    errors: list[str] = []
    deadline = time.perf_counter() + timeout_sec

    if len(backends) == 1:
        name = backends[0]
        try:
            _, results = _search_backend_once(name, request, config)
            if results:
                return results, errors, name
            errors.append(f"{name}: no results")
        except Exception as exc:
            errors.append(f"{name}: {exc}")
        return [], errors, None

    max_workers = min(len(backends), 8)
    started = time.perf_counter()
    query_preview = str(getattr(request, "query", "") or "")[:80]
    pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="search-race")
    try:
        futures = {
            pool.submit(_search_backend_once, name, request, config): name
            for name in backends
        }
        pending = set(futures.keys())

        while pending and time.perf_counter() < deadline:
            done, pending = wait(
                pending,
                timeout=min(0.25, max(0.05, deadline - time.perf_counter())),
                return_when=FIRST_COMPLETED,
            )
            for future in done:
                name = futures[future]
                try:
                    winner_name, results = future.result(timeout=0)
                    if results:
                        elapsed = time.perf_counter() - started
                        logger.debug(
                            "Web search race won by {} ({:.2f}s) query={!r}",
                            winner_name,
                            elapsed,
                            query_preview,
                        )
                        return results, errors, winner_name
                    errors.append(f"{winner_name}: no results")
                except Exception as exc:
                    errors.append(f"{name}: {exc}")
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    return [], errors, None
