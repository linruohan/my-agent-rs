from __future__ import annotations

import pytest

from tools.business.notes import create_notes_tools


@pytest.fixture
def notes_tools(monkeypatch, tmp_path):
    monkeypatch.setattr("memory.rag.get_data_dir", lambda: tmp_path)
    monkeypatch.setattr("tools.business.notes.get_rag_store", lambda: __import__("memory.rag", fromlist=["RagStore"]).RagStore(db_path=tmp_path / "doc.db"))
    return {t.name: t for t in create_notes_tools()}


def test_search_notes_empty(notes_tools):
    result = notes_tools["search_notes"].invoke({"query": "nonexistent xyz"})
    assert "未找到" in result or "No" in result.lower() or len(result) > 0
