from __future__ import annotations

from infra.session_store import SessionStore


def test_session_crud(tmp_path):
    store = SessionStore(db_path=tmp_path / "sessions.db")

    session = store.create("Test Session")
    assert session["thread_id"]
    assert session["title"] == "Test Session"

    assert store.exists(session["thread_id"])

    sessions = store.list_sessions()
    assert len(sessions) == 1

    store.touch(session["thread_id"])

    assert store.delete(session["thread_id"])
    assert not store.exists(session["thread_id"])
