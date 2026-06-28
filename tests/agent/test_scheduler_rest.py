from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from starlette.testclient import TestClient


@pytest.fixture
def api_client(monkeypatch, tmp_path):
    from pathlib import Path
    from unittest.mock import MagicMock

    config_dir = Path(__file__).resolve().parents[2] / "agent" / "config"
    monkeypatch.setenv("AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AGENT_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("SIDECAR_AUTH_TOKEN", "test-ws-token")
    monkeypatch.setattr("tools.business.calendar.DB_PATH", tmp_path / "calendar.db")

    from langgraph.checkpoint.memory import MemorySaver

    monkeypatch.setattr("agent.graph.get_checkpointer", lambda: MemorySaver())

    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    monkeypatch.setattr(
        "agent.graph.create_llm_with_fallback",
        lambda *a, **k: (mock_llm, "mock"),
    )
    monkeypatch.setattr("agent.graph._provider_available", lambda _name: True)

    from main import build_app

    with TestClient(build_app(port=8765)) as client:
        yield client


def _auth_headers() -> dict[str, str]:
    token = os.environ["SIDECAR_AUTH_TOKEN"]
    return {"Authorization": f"Bearer {token}"}


def test_scheduler_rest_list_jobs(api_client):
    from infra.scheduler import schedule_reminder

    run_at = datetime.now(timezone.utc) + timedelta(hours=1)
    schedule_reminder("rest-job-1", "Test", "Hello", run_at)

    resp = api_client.get("/scheduler/jobs", headers=_auth_headers())
    assert resp.status_code == 200
    jobs = resp.json()["jobs"]
    assert any(j["id"] == "rest-job-1" for j in jobs)


def test_scheduler_rest_requires_auth(api_client):
    resp = api_client.get("/scheduler/jobs")
    assert resp.status_code == 401
