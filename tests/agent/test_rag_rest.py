from __future__ import annotations

import os

import pytest
from starlette.testclient import TestClient


@pytest.fixture
def api_client(monkeypatch, tmp_path):
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


def _auth_headers() -> dict[str, str]:
    token = os.environ["SIDECAR_AUTH_TOKEN"]
    return {"Authorization": f"Bearer {token}"}


def test_rag_rest_lifecycle(api_client, monkeypatch):
    ingested: list[tuple[str, str]] = []

    def fake_ingest_text(self, text, source="inline"):
        ingested.append((text, source))
        return 2

    monkeypatch.setattr("memory.rag.RagStore.ingest_text", fake_ingest_text)
    monkeypatch.setattr("memory.rag.RagStore.list_sources", lambda self: ["doc-a"])
    monkeypatch.setattr("memory.rag.RagStore.search", lambda self, q, top_k=6: [])
    monkeypatch.setattr("memory.rag.RagStore.delete_source", lambda self, s: s == "doc-a")

    listed = api_client.get("/rag/sources", headers=_auth_headers())
    assert listed.status_code == 200
    assert listed.json()["sources"] == ["doc-a"]

    ingest = api_client.post(
        "/rag/ingest",
        headers=_auth_headers(),
        json={"source": "rest-doc", "content": "hello rag"},
    )
    assert ingest.status_code == 200
    assert "Ingested 2 chunks" in ingest.json()["result"]
    assert ingested == [("hello rag", "rest-doc")]

    search = api_client.post(
        "/rag/search",
        headers=_auth_headers(),
        json={"query": "hello", "top_k": 3},
    )
    assert search.status_code == 200
    assert search.json()["query"] == "hello"

    deleted = api_client.post(
        "/rag/delete",
        headers=_auth_headers(),
        json={"source": "doc-a"},
    )
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True


def test_memory_rest_roundtrip(api_client):
    put = api_client.put(
        "/memory/user/preferences",
        headers=_auth_headers(),
        json={"value": {"theme": "dark", "lang": "zh"}},
    )
    assert put.status_code == 200
    assert put.json()["ok"] is True

    got = api_client.get("/memory/user/preferences", headers=_auth_headers())
    assert got.status_code == 200
    assert got.json()["value"]["theme"] == "dark"


def test_rag_rest_requires_auth(api_client):
    assert api_client.get("/rag/sources").status_code == 401
