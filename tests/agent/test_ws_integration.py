from __future__ import annotations

import pytest
from starlette.testclient import TestClient


@pytest.fixture
def test_client(monkeypatch, tmp_path):
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
    monkeypatch.setattr(
        "agent.graph.invoke_with_fallback",
        lambda fn, **k: (fn(mock_llm), "mock"),
    )

    from main import build_app

    with TestClient(build_app(port=8765)) as client:
        yield client


def test_ws_auth_and_session_flow(test_client, monkeypatch):
    import os

    token = os.environ.get("SIDECAR_AUTH_TOKEN", "")
    assert token

    with test_client.websocket_connect("/ws") as ws:
        connected = ws.receive_json()
        assert connected["type"] == "connected"
        assert connected.get("auth_required") is True

        ws.send_json({"type": "auth", "token": token})
        auth_ok = ws.receive_json()
        assert auth_ok["type"] == "auth.ok"

        ws.send_json({"type": "session.create", "title": "WS Test"})
        created = ws.receive_json()
        assert created["type"] == "session.created"
        thread_id = created["thread_id"]

        ws.send_json({"type": "session.list"})
        listed = ws.receive_json()
        assert listed["type"] == "session.list"
        assert any(s["thread_id"] == thread_id for s in listed["sessions"])

        ws.send_json({"type": "ping"})
        pong = ws.receive_json()
        assert pong["type"] == "pong"


def test_mcp_config_roundtrip(test_client):
    resp = test_client.put(
        "/config/mcp",
        json={"servers": {"github": {"enabled": True}}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["servers"]["github"]["enabled"] is True

    get_resp = test_client.get("/config/mcp")
    assert get_resp.json()["servers"]["github"]["enabled"] is True
