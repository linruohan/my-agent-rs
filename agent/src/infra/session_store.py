from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from infra.config import get_data_dir


class SessionStore:
    """SQLite-backed session metadata store."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or (get_data_dir() / "sessions.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    thread_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    archived INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            try:
                conn.execute(
                    "ALTER TABLE sessions ADD COLUMN archived INTEGER NOT NULL DEFAULT 0"
                )
            except sqlite3.OperationalError:
                pass
            conn.commit()

    def create(self, title: str | None = None) -> dict[str, Any]:
        thread_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        display_title = title or "新会话"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO sessions (thread_id, title, created_at, updated_at, archived)
                VALUES (?, ?, ?, ?, 0)
                """,
                (thread_id, display_title, now, now),
            )
            conn.commit()
        return {
            "thread_id": thread_id,
            "title": display_title,
            "created_at": now,
            "archived": False,
        }

    def list_sessions(self, include_archived: bool = False) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if include_archived:
                rows = conn.execute(
                    """
                    SELECT thread_id, title, created_at, updated_at, archived
                    FROM sessions ORDER BY updated_at DESC
                    """
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT thread_id, title, created_at, updated_at, archived
                    FROM sessions
                    WHERE archived = 0
                    ORDER BY updated_at DESC
                    """
                ).fetchall()
        return [
            {
                **dict(row),
                "archived": bool(row["archived"]),
            }
            for row in rows
        ]

    def list_archived_sessions(self) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT thread_id, title, created_at, updated_at, archived
                FROM sessions WHERE archived = 1 ORDER BY updated_at DESC
                """
            ).fetchall()
        return [{**dict(row), "archived": True} for row in rows]

    def set_archived(self, thread_id: str, archived: bool) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "UPDATE sessions SET archived = ? WHERE thread_id = ?",
                (1 if archived else 0, thread_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def delete(self, thread_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM sessions WHERE thread_id = ?", (thread_id,))
            conn.commit()
            return cur.rowcount > 0

    def exists(self, thread_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM sessions WHERE thread_id = ?", (thread_id,)
            ).fetchone()
        return row is not None

    def touch(self, thread_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE thread_id = ?",
                (now, thread_id),
            )
            conn.commit()
