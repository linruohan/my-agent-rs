from __future__ import annotations

import sqlite3


def test_task_store_migrates_legacy_db_without_project_columns(tmp_path, monkeypatch):
    """已有 task.db（无 project_id 列）应能正常升级。"""
    monkeypatch.setenv("AGENT_DATA_DIR", str(tmp_path))
    db = tmp_path / "task.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL DEFAULT '',
            due_at TEXT,
            repeat_rule TEXT,
            remind_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            tags TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'pending',
            owner TEXT,
            repeat_end TEXT,
            repeat_count INTEGER NOT NULL DEFAULT 0,
            remind_spec TEXT,
            remind_schedule TEXT,
            attachments TEXT NOT NULL DEFAULT '[]'
        );
        INSERT INTO tasks (title, content, created_at, updated_at)
        VALUES ('legacy', '', '2026-01-01', '2026-01-01');
        """
    )
    conn.commit()
    conn.close()

    from tools.task.store import TaskStore

    store = TaskStore()
    row = store.get(1)
    assert row is not None
    assert row.title == "legacy"
    assert row.project_id is None
    assert row.section_id is None

    cols = {r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(tasks)").fetchall()}
    assert "project_id" in cols
    assert "section_id" in cols
