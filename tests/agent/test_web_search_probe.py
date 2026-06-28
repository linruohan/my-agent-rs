from __future__ import annotations

import sys
from pathlib import Path

AGENT_SRC = Path(__file__).resolve().parents[1] / "agent" / "src"
if str(AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(AGENT_SRC))

from tools.capability.web_search_selector import (
    BackendProbeResult,
    ProbeSearchHit,
    format_probe_detail,
    format_probe_report,
)


def test_format_probe_report():
    report = format_probe_report(
        [
            BackendProbeResult("mojeek", True, 1200.0, 1),
            BackendProbeResult("duckduckgo", False, 5000.0, 0, error="no results"),
        ]
    )
    assert "mojeek" in report
    assert "yes" in report
    assert "duckduckgo" in report
    assert "no" in report


def test_format_probe_detail_shows_snippet_and_fetched_text():
    detail = format_probe_detail(
        BackendProbeResult(
            backend="mojeek",
            ok=True,
            latency_ms=900.0,
            result_count=1,
            hits=[
                ProbeSearchHit(
                    title="Python 3.14 release",
                    url="https://www.python.org/downloads/release/python-3140/",
                    snippet="What's new in Python 3.14",
                )
            ],
            fetched_text="Python 3.14.0 is the latest feature release of Python 3.",
        )
    )
    assert "Python 3.14 release" in detail
    assert "What's new in Python 3.14" in detail
    assert "https://www.python.org/downloads/release/python-3140/" in detail
    assert "Python 3.14.0 is the latest" in detail
