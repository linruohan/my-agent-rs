"""Tests for user tool enable/disable configuration."""

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


def test_tools_config_list(test_client):
    resp = test_client.get("/config/tools")
    assert resp.status_code == 200
    data = resp.json()
    assert "tools" in data
    assert data["count"] == len(data["tools"])
    assert data["enabled_count"] <= data["count"]
    names = {t["name"] for t in data["tools"]}
    assert "web_search" in names
    assert "bash" in names


def test_tools_config_disable_roundtrip(test_client):
    get_before = test_client.get("/config/tools").json()
    web_search = next(t for t in get_before["tools"] if t["name"] == "web_search")
    assert web_search["enabled"] is True

    put_resp = test_client.put(
        "/config/tools",
        json={"capability": {"web_search": {"enabled": False}}},
    )
    assert put_resp.status_code == 200
    put_data = put_resp.json()
    assert put_data["ok"] is True
    disabled = next(t for t in put_data["tools"] if t["name"] == "web_search")
    assert disabled["enabled"] is False

    reload_resp = test_client.post("/tools/reload")
    assert reload_resp.status_code == 200

    get_after = test_client.get("/config/tools").json()
    web_after = next(t for t in get_after["tools"] if t["name"] == "web_search")
    assert web_after["enabled"] is False

    test_client.put(
        "/config/tools",
        json={"capability": {"web_search": {"enabled": True}}},
    )
    test_client.post("/tools/reload")


def test_effective_tools_config_merges_user_override(monkeypatch, tmp_path):
    from infra import config as cfg_mod

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(cfg_mod, "get_data_dir", lambda: data_dir)

    cfg_mod.save_tools_user_config(
        {"capability": {"web_search": {"enabled": False}}}
    )
    effective = cfg_mod.load_effective_tools_config()
    assert effective["capability"]["web_search"]["enabled"] is False

    tools = cfg_mod.list_configurable_tools()
    ws = next(t for t in tools if t["name"] == "web_search")
    assert ws["enabled"] is False
