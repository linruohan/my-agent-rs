from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def test_app(monkeypatch, tmp_path):
    config_dir = __import__("pathlib").Path(__file__).resolve().parents[2] / "agent" / "config"
    monkeypatch.setenv("AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AGENT_CONFIG_DIR", str(config_dir))
    monkeypatch.setattr("tools.business.todo.DB_PATH", tmp_path / "todos.db")
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

    return build_app(port=8765)


@pytest.mark.asyncio
async def test_bootstrap_endpoint(test_app):
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/bootstrap")
        assert resp.status_code == 200
        data = resp.json()
        assert data["health"]["status"] == "ok"
        assert "tools" in data["tools"]
        assert "count" in data["tools"]
        assert "configured" in data["mcp"]


@pytest.mark.asyncio
async def test_tools_endpoint(test_app):
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/tools")
        assert resp.status_code == 200
        data = resp.json()
        assert "tools" in data
        assert "count" in data
        assert len(data["tools"]) > 0


@pytest.mark.asyncio
async def test_providers_endpoint(test_app):
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/providers")
        assert resp.status_code == 200
        data = resp.json()
        assert "fallback_chain" in data
        assert "deepseek" in data["providers"]
