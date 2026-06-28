from __future__ import annotations

import os

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


def test_sessions_rest_list_and_history(api_client):
    with api_client.websocket_connect("/ws") as ws:
        connected = ws.receive_json()
        assert connected["type"] == "connected"
        ws.send_json({"type": "auth", "token": os.environ["SIDECAR_AUTH_TOKEN"]})
        assert ws.receive_json()["type"] == "auth.ok"
        ws.send_json({"type": "session.create", "title": "REST Session"})
        created = ws.receive_json()
        thread_id = created["thread_id"]

    listed = api_client.get("/sessions", headers=_auth_headers())
    assert listed.status_code == 200
    sessions = listed.json()["sessions"]
    assert any(s["thread_id"] == thread_id for s in sessions)

    history = api_client.get(f"/sessions/{thread_id}/history", headers=_auth_headers())
    assert history.status_code == 200
    assert history.json()["thread_id"] == thread_id
    assert isinstance(history.json()["messages"], list)


def test_sessions_rest_requires_auth(api_client):
    resp = api_client.get("/sessions")
    assert resp.status_code == 401


def test_sessions_rest_write_lifecycle(api_client):
    created = api_client.post(
        "/sessions",
        headers=_auth_headers(),
        json={"title": "REST Write Test"},
    )
    assert created.status_code == 200
    body = created.json()
    thread_id = body["thread_id"]
    assert body["title"] == "REST Write Test"

    archived = api_client.post(
        f"/sessions/{thread_id}/archive",
        headers=_auth_headers(),
    )
    assert archived.status_code == 200
    assert archived.json()["ok"] is True

    archived_list = api_client.get("/sessions/archived", headers=_auth_headers())
    assert any(s["thread_id"] == thread_id for s in archived_list.json()["sessions"])

    unarchived = api_client.post(
        f"/sessions/{thread_id}/unarchive",
        headers=_auth_headers(),
    )
    assert unarchived.status_code == 200

    deleted = api_client.delete(f"/sessions/{thread_id}", headers=_auth_headers())
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True

    listed = api_client.get("/sessions", headers=_auth_headers())
    assert not any(s["thread_id"] == thread_id for s in listed.json()["sessions"])

    missing = api_client.delete(f"/sessions/{thread_id}", headers=_auth_headers())
    assert missing.status_code == 404
