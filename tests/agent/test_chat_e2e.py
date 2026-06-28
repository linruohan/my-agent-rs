from __future__ import annotations

import os
import time

import pytest
from starlette.testclient import TestClient


@pytest.fixture
def chat_client(monkeypatch, tmp_path):
    from pathlib import Path
    from unittest.mock import MagicMock

    from langchain_core.messages import AIMessage

    config_dir = Path(__file__).resolve().parents[2] / "agent" / "config"
    monkeypatch.setenv("AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AGENT_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("SIDECAR_AUTH_TOKEN", "test-ws-token")
    monkeypatch.setattr("tools.business.calendar.DB_PATH", tmp_path / "calendar.db")

    from langgraph.checkpoint.memory import MemorySaver

    monkeypatch.setattr("agent.graph.get_checkpointer", lambda: MemorySaver())

    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    reply = AIMessage(content="你好，我是测试助理。")
    mock_llm.invoke.return_value = reply

    monkeypatch.setattr(
        "agent.graph.create_llm_with_fallback",
        lambda *a, **k: (mock_llm, "mock"),
    )
    monkeypatch.setattr("agent.graph._provider_available", lambda _name: True)

    from main import build_app

    with TestClient(build_app(port=8765)) as client:
        yield client


def _ws_auth(ws, token: str) -> None:
    connected = ws.receive_json()
    assert connected["type"] == "connected"
    ws.send_json({"type": "auth", "token": token})
    assert ws.receive_json()["type"] == "auth.ok"


def _collect_until_done(ws, thread_id: str, timeout_s: float = 8.0):
    deadline = time.monotonic() + timeout_s
    events: list[dict] = []
    while time.monotonic() < deadline:
        msg = ws.receive_json()
        events.append(msg)
        if msg.get("type") == "done" and msg.get("thread_id") == thread_id:
            return events
        if msg.get("type") == "error" and msg.get("thread_id") == thread_id:
            pytest.fail(f"chat error: {msg.get('message')}")
    pytest.fail(f"timeout waiting for done; got {[e.get('type') for e in events]}")


def test_chat_send_receives_done(chat_client):
    token = os.environ["SIDECAR_AUTH_TOKEN"]
    with chat_client.websocket_connect("/ws") as ws:
        _ws_auth(ws, token)
        ws.send_json({"type": "session.create", "title": "E2E Chat"})
        created = ws.receive_json()
        assert created["type"] == "session.created"
        thread_id = created["thread_id"]

        ws.send_json(
            {
                "type": "chat.send",
                "thread_id": thread_id,
                "content": "你好",
            }
        )
        events = _collect_until_done(ws, thread_id)
        types = [e.get("type") for e in events]
        assert "done" in types
