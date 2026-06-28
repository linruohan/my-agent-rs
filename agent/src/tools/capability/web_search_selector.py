from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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

_lock = threading.Lock()
_cached_backend: str | None = None
_cached_at: float = 0.0


def _free_backend_list(config: dict[str, Any]) -> list[str]:
    configured = config.get("free_backends")
    if isinstance(configured, list) and configured:
        return [str(name) for name in configured]
    return list(DEFAULT_FREE_BACKENDS)


def _probe_backend(
    backend_name: str,
    *,
    probe_query: str,
    region: str,
    timeout_sec: float,
) -> tuple[str, float] | None:
    from tools.capability.web_search import SearchRequest, get_search_backend

    start = time.perf_counter()
    try:
        backend = get_search_backend(backend_name, {})
        results = backend.search(
            SearchRequest(
                query=probe_query,
                max_results=1,
                region=region,
            )
        )
        if not results:
            return None
        elapsed = time.perf_counter() - start
        if elapsed > timeout_sec:
            return None
        return backend_name, elapsed
    except Exception as exc:
        logger.debug("Search benchmark failed for {}: {}", backend_name, exc)
        return None


def benchmark_free_backends(config: dict[str, Any]) -> str | None:
    """Probe configured free backends in parallel and return the fastest working one."""
    from infra.search_context import get_search_region

    probe_query = str(config.get("benchmark_query") or "hello world")
    timeout_sec = float(config.get("benchmark_timeout_sec") or 10)
    region = get_search_region(config)
    backends = _free_backend_list(config)

    winners: list[tuple[str, float]] = []
    max_workers = min(len(backends), 6)
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="search-bench") as pool:
        futures = {
            pool.submit(
                _probe_backend,
                name,
                probe_query=probe_query,
                region=region,
                timeout_sec=timeout_sec,
            ): name
            for name in backends
        }
        try:
            completed = as_completed(futures, timeout=timeout_sec + 2)
            for future in completed:
                try:
                    result = future.result(timeout=1)
                except Exception:
                    continue
                if result is not None:
                    winners.append(result)
        except TimeoutError:
            for future in futures:
                if future.done():
                    try:
                        result = future.result(timeout=0)
                    except Exception:
                        continue
                    if result is not None:
                        winners.append(result)

    if not winners:
        return None

    winners.sort(key=lambda item: item[1])
    fastest, latency = winners[0]
    logger.info(
        "Search benchmark: selected {} ({:.2f}s), candidates={}",
        fastest,
        latency,
        ", ".join(f"{name}:{lat:.2f}s" for name, lat in winners[:4]),
    )
    return fastest


def resolve_search_backend(config: dict[str, Any]) -> str:
    """Resolve backend name, optionally auto-picking the fastest free provider."""
    backend = str(config.get("backend") or "duckduckgo")
    if backend not in {"auto", "fastest"}:
        return backend

    ttl_sec = int(config.get("benchmark_ttl_sec") or 3600)
    now = time.time()
    global _cached_backend, _cached_at

    with _lock:
        if _cached_backend and now - _cached_at < ttl_sec:
            return _cached_backend

    fastest = benchmark_free_backends(config)
    chosen = fastest or "duckduckgo"
    with _lock:
        _cached_backend = chosen
        _cached_at = now
    return chosen


def warm_search_backends(config: dict[str, Any]) -> str:
    """Run benchmark eagerly (e.g. on sidecar startup)."""
    if not config.get("benchmark_on_startup", True):
        backend = str(config.get("backend") or "duckduckgo")
        return backend if backend not in {"auto", "fastest"} else "duckduckgo"
    return resolve_search_backend(config)


def reset_search_backend_cache() -> None:
    global _cached_backend, _cached_at
    with _lock:
        _cached_backend = None
        _cached_at = 0.0
