"""Tests for user app config API."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def config_client(monkeypatch, tmp_path):
    agent_dir = Path(__file__).resolve().parents[2] / "agent"
    monkeypatch.setenv("AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AGENT_CONFIG_DIR", str(agent_dir / "config"))

    from langgraph.checkpoint.memory import MemorySaver
    from unittest.mock import MagicMock

    monkeypatch.setattr("agent.graph.get_checkpointer", lambda: MemorySaver())
    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    monkeypatch.setattr(
        "agent.graph.create_llm_with_fallback",
        lambda *a, **k: (mock_llm, "mock"),
    )

    from main import build_app

    with TestClient(build_app(port=8765)) as client:
        yield client


def test_user_config_roundtrip(config_client):
    payload = {
        "hitl": {"timeout_sec": 120, "on_timeout": "reject", "notify_before_sec": 15},
        "llm": {"temperature": 0.5, "max_tokens": 2048},
        "web_search": {"backend": "duckduckgo"},
    }
    put = config_client.put("/config/user", json=payload)
    assert put.status_code == 200
    data = put.json()
    assert data["hitl"]["timeout_sec"] == 120
    assert data["llm"]["max_tokens"] == 2048
    assert data["web_search"]["backend"] == "duckduckgo"

    get = config_client.get("/config/user")
    assert get.status_code == 200
    assert get.json()["llm"]["temperature"] == 0.5
