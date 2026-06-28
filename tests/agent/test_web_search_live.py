from __future__ import annotations

import sys
from pathlib import Path

import pytest

AGENT_SRC = Path(__file__).resolve().parents[1] / "agent" / "src"
if str(AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(AGENT_SRC))

from tools.capability.web_search_selector import (
    DEFAULT_FREE_BACKENDS,
    format_probe_detail,
    format_probe_report_detailed,
    probe_all_search_backends,
    probe_search_backend,
)

LIVE_CONFIG = {
    "region": "cn-zh",
    "search_timeout_sec": 25,
    "free_backends": list(DEFAULT_FREE_BACKENDS),
}

LIVE_QUERY = "python 3.14 新特性"


@pytest.mark.network
@pytest.mark.parametrize("backend_name", DEFAULT_FREE_BACKENDS)
def test_search_backend_live(backend_name: str):
    result = probe_search_backend(
        backend_name,
        LIVE_CONFIG,
        query=LIVE_QUERY,
        max_results=3,
        fetch_page=True,
        fetch_max_chars=400,
    )
    print(format_probe_detail(result))
    if not result.ok:
        pytest.skip(result.error or "no results")


@pytest.mark.network
def test_search_backends_live_report():
    results = probe_all_search_backends(
        LIVE_CONFIG,
        query=LIVE_QUERY,
        max_results=3,
        fetch_page=True,
        fetch_max_chars=400,
    )
    report = format_probe_report_detailed(results)
    print(report)

    working = [item.backend for item in results if item.ok]
    assert working, f"no search backend available\n{report}"
