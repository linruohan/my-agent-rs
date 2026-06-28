from __future__ import annotations

import pytest

from infra.config import get_workspace_dir, resolve_workspace_path
from infra.rag_paths import validate_rag_ingest_path


def test_resolve_workspace_path_rejects_traversal(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        "infra.config.get_workspace_dir",
        lambda: workspace.resolve(),
    )

    safe = workspace / "notes.md"
    safe.write_text("# hello", encoding="utf-8")

    resolved = resolve_workspace_path("notes.md")
    assert resolved == safe.resolve()

    with pytest.raises(ValueError, match="escapes workspace"):
        resolve_workspace_path("../../outside.txt")


def test_validate_rag_ingest_path(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        "infra.config.get_workspace_dir",
        lambda: workspace.resolve(),
    )

    doc = workspace / "doc.md"
    doc.write_text("# doc", encoding="utf-8")

    assert validate_rag_ingest_path("doc.md") == doc.resolve()

    with pytest.raises(ValueError, match="escapes workspace"):
        validate_rag_ingest_path("../../secret.txt")

    with pytest.raises(ValueError, match="Unsupported file type"):
        bad = workspace / "run.exe"
        bad.write_bytes(b"MZ")
        validate_rag_ingest_path("run.exe")


def test_validate_rag_inline_content(monkeypatch):
    monkeypatch.setattr(
        "infra.rag_paths.load_rag_config",
        lambda: {"ingest": {"max_inline_chars": 100, "max_pdf_b64_bytes": 256}},
    )
    from infra.rag_paths import validate_rag_inline_content, validate_rag_pdf_b64

    assert validate_rag_inline_content("hello") == "hello"
    with pytest.raises(ValueError, match="too large"):
        validate_rag_inline_content("x" * 101)

    import base64

    small_pdf = base64.b64encode(b"%PDF-small").decode()
    assert validate_rag_pdf_b64(f"__pdf_b64__:{small_pdf}")
    with pytest.raises(ValueError, match="too large"):
        validate_rag_pdf_b64(f"__pdf_b64__:{base64.b64encode(b'x' * 300).decode()}")


def test_prometheus_metrics(monkeypatch, tmp_path):
    from infra.metrics import inc, observe_turn_duration, prometheus_text

    inc("agent.turns", 0)
    observe_turn_duration(120)
    text = prometheus_text()
    assert "agent_turns" in text
    assert "turn_duration_ms_p95" in text


def test_tracing_noop_without_env(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    from infra.tracing import setup_tracing, trace_span, tracing_enabled

    assert setup_tracing() is False
    assert tracing_enabled() is False
    with trace_span("test.span"):
        pass


def test_metrics_endpoint(monkeypatch, tmp_path):
    from pathlib import Path
    from starlette.testclient import TestClient

    config_dir = Path(__file__).resolve().parents[2] / "agent" / "config"
    monkeypatch.setenv("AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AGENT_CONFIG_DIR", str(config_dir))
    monkeypatch.setattr("tools.business.calendar.DB_PATH", tmp_path / "calendar.db")

    from langgraph.checkpoint.memory import MemorySaver

    monkeypatch.setattr("agent.graph.get_checkpointer", lambda: MemorySaver())

    from main import build_app

    with TestClient(build_app(port=8765)) as client:
        resp = client.get("/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "counters" in data
        assert "tool_call_duration_ms" in data
        assert "turn_duration_ms" in data

        prom = client.get("/metrics/prometheus")
        assert prom.status_code == 200
        assert "text/plain" in prom.headers.get("content-type", "")
        assert "turn_duration_ms_p95" in prom.text
