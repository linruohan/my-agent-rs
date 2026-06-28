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
    monkeypatch.setattr("agent.graph._provider_available", lambda _name: True)

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


def _ws_auth(ws, token: str) -> None:
    connected = ws.receive_json()
    assert connected["type"] == "connected"
    ws.send_json({"type": "auth", "token": token})
    assert ws.receive_json()["type"] == "auth.ok"


def test_rag_ingest_ws_rate_limit(test_client, monkeypatch):
    import os

    import infra.rate_limit as rl

    rl._rag_ingest_limiter = None
    monkeypatch.setattr(
        "infra.rate_limit.load_rag_config",
        lambda: {"ingest": {"rate_limit_per_minute": 2, "max_inline_chars": 500000}},
    )
    monkeypatch.setattr(
        "memory.rag.RagStore.ingest_text",
        lambda self, text, source="inline": 1,
    )

    token = os.environ["SIDECAR_AUTH_TOKEN"]
    with test_client.websocket_connect("/ws") as ws:
        _ws_auth(ws, token)
        for i in range(2):
            ws.send_json(
                {
                    "type": "rag.ingest",
                    "content": f"test chunk {i}",
                    "source": "ws-test",
                }
            )
            resp = ws.receive_json()
            assert resp["type"] == "rag.ingest", resp

        ws.send_json(
            {"type": "rag.ingest", "content": "over limit", "source": "ws-test"}
        )
        err = ws.receive_json()
        assert err["type"] == "error"
        assert err["code"] == "RATE_LIMIT"

    prom = test_client.get("/metrics/prometheus")
    assert prom.status_code == 200
    assert "rag_ingest_requests" in prom.text
    assert "rag_ingest_rate_limited" in prom.text


def test_session_history_after_chat(test_client, monkeypatch):
    import os
    import time
    from unittest.mock import MagicMock

    from langchain_core.messages import AIMessage

    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.return_value = AIMessage(content="历史回复测试")
    monkeypatch.setattr(
        "agent.graph.create_llm_with_fallback",
        lambda *a, **k: (mock_llm, "mock"),
    )

    token = os.environ["SIDECAR_AUTH_TOKEN"]
    with test_client.websocket_connect("/ws") as ws:
        _ws_auth(ws, token)

        ws.send_json({"type": "session.create", "title": "History Sync Test"})
        created = ws.receive_json()
        thread_id = created["thread_id"]

        ws.send_json(
            {
                "type": "chat.send",
                "thread_id": thread_id,
                "content": "同步历史测试",
            }
        )

        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            msg = ws.receive_json()
            if msg.get("type") == "done" and msg.get("thread_id") == thread_id:
                break
        else:
            pytest.fail("timeout waiting for chat done")

        ws.send_json({"type": "session.history", "thread_id": thread_id})
        history = ws.receive_json()
        assert history["type"] == "session.history"
        assert history["thread_id"] == thread_id
        roles = [m.get("role") for m in history["messages"]]
        assert "user" in roles
        assert "assistant" in roles


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
