from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from infra.config import get_data_dir

DB_PATH = get_data_dir() / "calendar.db"


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            location TEXT DEFAULT '',
            description TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def create_event_record(
    title: str,
    start_time: str,
    end_time: str,
    location: str = "",
    description: str = "",
) -> dict[str, Any]:
    conn = _get_conn()
    try:
        cur = conn.execute(
            """
            INSERT INTO events (title, start_time, end_time, location, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (title, start_time, end_time, location, description, datetime.utcnow().isoformat()),
        )
        conn.commit()
        return {
            "id": cur.lastrowid,
            "title": title,
            "start_time": start_time,
            "end_time": end_time,
            "location": location,
            "description": description,
        }
    finally:
        conn.close()


def list_events(start_date: str = "", end_date: str = "") -> list[dict[str, Any]]:
    conn = _get_conn()
    try:
        query = "SELECT * FROM events"
        params: list[str] = []
        conditions = []
        if start_date:
            conditions.append("start_time >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("end_time <= ?")
            params.append(end_date)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY start_time ASC"
        rows = conn.execute(query, params).fetchall()
        return [
            {
                "id": row["id"],
                "title": row["title"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "location": row["location"],
                "description": row["description"],
            }
            for row in rows
        ]
    finally:
        conn.close()


def detect_conflicts(start_time: str, end_time: str) -> list[dict[str, Any]]:
    events = list_events()
    conflicts = []
    for e in events:
        if e["start_time"] < end_time and e["end_time"] > start_time:
            conflicts.append(e)
    return conflicts


def create_calendar_tools():
    from langchain_core.tools import tool

    @tool
    def read_calendar(start_date: str = "", end_date: str = "") -> str:
        """查询日历事件。可选 start_date / end_date 过滤（ISO 格式）。"""
        events = list_events(start_date, end_date)
        if not events:
            return "指定范围内没有日历事件。"
        lines = []
        for e in events:
            loc = f" @ {e['location']}" if e["location"] else ""
            lines.append(
                f"#{e['id']} {e['title']}: {e['start_time']} ~ {e['end_time']}{loc}"
            )
        return "\n".join(lines)

    @tool
    def create_calendar_event(
        title: str,
        start_time: str,
        end_time: str,
        location: str = "",
        description: str = "",
    ) -> str:
        """创建日历事件。此操作可能需要用户确认后才会执行。"""
        conflicts = detect_conflicts(start_time, end_time)
        if conflicts:
            names = ", ".join(c["title"] for c in conflicts)
            return f"检测到时间冲突，与以下事件重叠: {names}。请调整时间后重试。"
        record = create_event_record(title, start_time, end_time, location, description)
        return (
            f"已创建日历事件 #{record['id']}: {record['title']} "
            f"({record['start_time']} ~ {record['end_time']})"
        )

    return [read_calendar, create_calendar_event]
