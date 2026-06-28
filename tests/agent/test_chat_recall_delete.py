from __future__ import annotations

import sqlite3

from memory.chat_recall import ChatHistoryStore


def test_delete_by_thread_id(tmp_path):
    store = ChatHistoryStore(db_path=tmp_path / "chat_history.db")
    store.record("thread-a", "What is Rust?", "Rust is a systems language.")
    store.record("thread-b", "What is Python?", "Python is a dynamic language.")

    removed = store.delete_by_thread_id("thread-a")
    assert removed == 1

    assert store.find_similar("What is Rust?") is None
    assert store.find_similar("What is Python?") is not None
