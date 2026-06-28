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
