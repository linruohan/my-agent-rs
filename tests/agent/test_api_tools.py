from __future__ import annotations

from unittest.mock import MagicMock

import pytest


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
    monkeypatch.setattr("agent.graph._provider_available", lambda _name: True)

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
        provider_ids = [p["id"] for p in data["providers"]]
        assert "deepseek" in provider_ids


@pytest.mark.asyncio
async def test_provider_models_endpoint(test_app):
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/providers/deepseek/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"] == "deepseek"
        assert "models" in data
        assert len(data["models"]) >= 1


@pytest.mark.asyncio
async def test_provider_models_with_test(test_app, monkeypatch):
    from httpx import ASGITransport, AsyncClient

    async def fake_test(provider_name, models, **kwargs):
        return {m: {"ok": True, "status_code": 200} for m in models}

    monkeypatch.setattr("llm.models.test_provider_models", fake_test)

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/providers/deepseek/models?test=true")
        assert resp.status_code == 200
        data = resp.json()
        assert "tests" in data
        assert data["tests"][data["models"][0]]["status_code"] == 200
