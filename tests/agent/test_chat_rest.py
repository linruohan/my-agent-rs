from __future__ import annotations

import json
import os

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
    reply = AIMessage(content="REST SSE 回复")
    mock_llm.invoke.return_value = reply

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


def _parse_sse_events(raw: str) -> list[dict]:
    events: list[dict] = []
    for block in raw.split("\n\n"):
        for line in block.split("\n"):
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events


def test_chat_rest_sse_stream(chat_client):
    created = chat_client.post(
        "/sessions",
        headers=_auth_headers(),
        json={"title": "SSE Chat"},
    )
    thread_id = created.json()["thread_id"]

    with chat_client.stream(
        "POST",
        f"/sessions/{thread_id}/chat",
        headers=_auth_headers(),
        json={"content": "你好"},
    ) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        body = "".join(resp.iter_text())
        events = _parse_sse_events(body)
        types = [e.get("type") for e in events]
        assert "done" in types
        assert "error" not in types

    stop = chat_client.post(
        f"/sessions/{thread_id}/chat/stop",
        headers=_auth_headers(),
    )
    assert stop.status_code == 200
