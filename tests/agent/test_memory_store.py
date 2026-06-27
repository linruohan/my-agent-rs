from __future__ import annotations

from memory.store import MemoryStore


def test_memory_store_crud(tmp_path):
    store = MemoryStore(db_path=tmp_path / "memory.db")

    store.put("user", "preferences", {"language": "zh", "theme": "dark"})
    prefs = store.get("user", "preferences")
    assert prefs["language"] == "zh"

    results = store.search("user", "theme")
    assert len(results) == 1
    assert results[0]["key"] == "preferences"

    keys = store.list_namespace("user")
    assert "preferences" in keys

    assert store.delete("user", "preferences")
    assert store.get("user", "preferences") is None
