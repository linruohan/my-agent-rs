from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

AGENT_DIR = Path(__file__).resolve().parents[2] / "agent"


@pytest.fixture
def test_app(monkeypatch, tmp_path):
    config_dir = AGENT_DIR / "config"
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

    from main import build_app

    app = build_app(port=8765)
    yield app


@pytest.mark.asyncio
async def test_health_endpoint(test_app):
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0"
        assert "api_version" in data
        assert "version_ok" in data
        assert "auth_required" in data
