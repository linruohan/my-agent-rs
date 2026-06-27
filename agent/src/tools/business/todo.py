from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from infra.config import get_data_dir

DB_PATH = get_data_dir() / "todos.db"


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            due_date TEXT DEFAULT '',
            priority TEXT DEFAULT 'normal',
            completed INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def create_todo_record(title: str, due_date: str = "", priority: str = "normal") -> dict[str, Any]:
    conn = _get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO todos (title, due_date, priority, created_at) VALUES (?, ?, ?, ?)",
            (title, due_date, priority, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        return {
            "id": cur.lastrowid,
            "title": title,
            "due_date": due_date,
            "priority": priority,
            "completed": False,
        }
    finally:
        conn.close()


def list_todo_records(include_completed: bool = False) -> list[dict[str, Any]]:
    conn = _get_conn()
    try:
        if include_completed:
            rows = conn.execute("SELECT * FROM todos ORDER BY id DESC").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM todos WHERE completed = 0 ORDER BY id DESC"
            ).fetchall()
        return [
            {
                "id": row["id"],
                "title": row["title"],
                "due_date": row["due_date"],
                "priority": row["priority"],
                "completed": bool(row["completed"]),
            }
            for row in rows
        ]
    finally:
        conn.close()


def create_todo_tools():
    from langchain_core.tools import tool

    @tool
    def create_todo(title: str, due_date: str = "", priority: str = "normal") -> str:
        """创建一条待办事项。"""
        record = create_todo_record(title, due_date, priority)
        return f"已创建待办 #{record['id']}: {record['title']} (优先级: {priority}, 截止: {due_date or '无'})"

    @tool
    def list_todos(include_completed: bool = False) -> str:
        """列出所有待办事项。"""
        records = list_todo_records(include_completed)
        if not records:
            return "暂无待办事项。"
        lines = []
        for r in records:
            status = "✓" if r["completed"] else "○"
            lines.append(
                f"{status} #{r['id']} [{r['priority']}] {r['title']}"
                + (f" (截止: {r['due_date']})" if r["due_date"] else "")
            )
        return "\n".join(lines)

    return [create_todo, list_todos]
