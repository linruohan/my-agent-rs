from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tools.registry import ToolRegistry


@pytest.fixture
def test_app(monkeypatch, tmp_path):
    config_dir = __import__("pathlib").Path(__file__).resolve().parents[2] / "agent" / "config"
    monkeypatch.setenv("AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AGENT_CONFIG_DIR", str(config_dir))
    monkeypatch.setattr("tools.business.calendar.DB_PATH", tmp_path / "calendar.db")

    from langgraph.checkpoint.memory import MemorySaver

    monkeypatch.setattr("agent.graph.get_checkpointer", lambda: MemorySaver())
    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    monkeypatch.setattr(
        "agent.graph.create_llm_with_fallback",
        lambda *a, **k: (mock_llm, "mock"),
    )

    from main import build_app

    return build_app(port=8765)


def test_mcp_tool_listed_as_enabled():
    registry = ToolRegistry({"mcp_servers": {"github": {"enabled": True}}})
    tool = MagicMock()
    tool.name = "github_search"
    tool.description = "Search GitHub"
    registry.register(tool, "mcp", {"risk": "medium"})

    items = registry.list_all()
    assert len(items) == 1
    assert items[0]["name"] == "github_search"
    assert items[0]["category"] == "mcp"
    assert items[0]["enabled"] is True
    assert items[0]["risk"] == "medium"


@pytest.mark.asyncio
async def test_mcp_status_endpoint(test_app):
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/mcp/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "configured" in data
        assert "loaded_count" in data
        assert data["version"] == "0.1.0"
