from __future__ import annotations

import pytest

from memory.rag import RagStore, is_knowledge_query


@pytest.fixture
def rag_store(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "memory.rag.get_data_dir", lambda: tmp_path
    )
    store = RagStore(db_path=tmp_path / "documents.db")
    store.store_dir = tmp_path / "vectorstore"
    store.store_dir.mkdir(parents=True, exist_ok=True)
    return store


def test_ingest_and_search(rag_store):
    count = rag_store.ingest_text(
        "Rust is a systems programming language focused on safety and performance.",
        source="rust-notes.md",
    )
    assert count >= 1

    results = rag_store.search("Rust programming safety")
    assert len(results) >= 1
    assert results[0]["source"] == "rust-notes.md"


def test_skip_duplicate_ingest(rag_store):
    text = "Duplicate content test for hash dedup."
    assert rag_store.ingest_text(text, source="dup.md") >= 1
    assert rag_store.ingest_text(text, source="dup.md") == 0


def test_is_knowledge_query():
    assert is_knowledge_query("在我的知识库里搜索 Rust 资料")
    assert not is_knowledge_query("今天天气怎么样")


def test_list_and_delete_source(rag_store):
    rag_store.ingest_text("Note content alpha", source="a.md")
    rag_store.ingest_text("Note content beta", source="b.md")
    sources = rag_store.list_sources()
    assert "a.md" in sources
    assert rag_store.delete_source("a.md")
    sources_after = rag_store.list_sources()
    assert "a.md" not in sources_after
