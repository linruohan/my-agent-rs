from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from infra.config import get_data_dir


class MemoryStore:
    """SQLite-backed long-term memory for user preferences and templates."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or (get_data_dir() / "memory.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory (
                    namespace TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (namespace, key)
                )
                """
            )
            conn.commit()

    def put(self, namespace: str, key: str, value: Any) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO memory (namespace, key, value, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(namespace, key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (namespace, key, json.dumps(value, ensure_ascii=False), now),
            )
            conn.commit()

    def get(self, namespace: str, key: str, default: Any = None) -> Any:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT value FROM memory WHERE namespace = ? AND key = ?",
                (namespace, key),
            ).fetchone()
        if row is None:
            return default
        return json.loads(row[0])

    def search(self, namespace: str, query: str, limit: int = 5) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT key, value, updated_at FROM memory
                WHERE namespace = ? AND (key LIKE ? OR value LIKE ?)
                ORDER BY updated_at DESC LIMIT ?
                """,
                (namespace, f"%{query}%", f"%{query}%", limit),
            ).fetchall()
        return [
            {"key": r["key"], "value": json.loads(r["value"]), "updated_at": r["updated_at"]}
            for r in rows
        ]

    def delete(self, namespace: str, key: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "DELETE FROM memory WHERE namespace = ? AND key = ?",
                (namespace, key),
            )
            conn.commit()
            return cur.rowcount > 0

    def list_namespace(self, namespace: str) -> list[str]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT key FROM memory WHERE namespace = ? ORDER BY key",
                (namespace,),
            ).fetchall()
        return [r[0] for r in rows]


def get_user_preferences() -> dict[str, Any]:
    store = MemoryStore()
    prefs = store.get("user", "preferences", {})
    return prefs if isinstance(prefs, dict) else {}
