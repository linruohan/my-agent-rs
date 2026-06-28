from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from infra.config import get_data_dir

DB_PATH = get_data_dir() / "todos.db"

_PRIORITY_ORDER = {"high": 0, "normal": 1, "low": 2}


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
            created_at TEXT NOT NULL,
            project_id INTEGER,
            description TEXT DEFAULT '',
            updated_at TEXT DEFAULT '',
            remind_at TEXT DEFAULT ''
        )
        """
    )
    _migrate_todos(conn)
    conn.commit()
    return conn


def _migrate_todos(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(todos)")}
    if "project_id" not in cols:
        conn.execute("ALTER TABLE todos ADD COLUMN project_id INTEGER")
    if "description" not in cols:
        conn.execute("ALTER TABLE todos ADD COLUMN description TEXT DEFAULT ''")
    if "updated_at" not in cols:
        conn.execute("ALTER TABLE todos ADD COLUMN updated_at TEXT DEFAULT ''")
    if "remind_at" not in cols:
        conn.execute("ALTER TABLE todos ADD COLUMN remind_at TEXT DEFAULT ''")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_todo(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "due_date": row["due_date"],
        "priority": row["priority"],
        "completed": bool(row["completed"]),
        "project_id": row["project_id"],
        "description": row["description"] or "",
        "remind_at": row["remind_at"] or "",
    }


def create_todo_record(
    title: str,
    due_date: str = "",
    priority: str = "normal",
    project_id: int | None = None,
    description: str = "",
    remind_at: str = "",
) -> dict[str, Any]:
    if project_id is not None:
        from tools.business.project import get_project_record

        if not get_project_record(project_id):
            raise ValueError(f"Project #{project_id} not found")

    conn = _get_conn()
    try:
        ts = _now()
        cur = conn.execute(
            """
            INSERT INTO todos (title, due_date, priority, created_at, project_id, description, updated_at, remind_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (title, due_date, priority, ts, project_id, description, ts, remind_at),
        )
        conn.commit()
        record = {
            "id": cur.lastrowid,
            "title": title,
            "due_date": due_date,
            "priority": priority,
            "completed": False,
            "project_id": project_id,
            "description": description,
            "remind_at": remind_at,
        }
        from tools.business.reminders import schedule_todo_reminder

        schedule_todo_reminder(record)
        return record
    finally:
        conn.close()


def list_todo_records(
    include_completed: bool = False,
    project_id: int | None = None,
    sort_by: str = "priority",
) -> list[dict[str, Any]]:
    conn = _get_conn()
    try:
        clauses = []
        params: list[Any] = []
        if not include_completed:
            clauses.append("completed = 0")
        if project_id is not None:
            clauses.append("project_id = ?")
            params.append(project_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = conn.execute(f"SELECT * FROM todos {where}", params).fetchall()
        records = [_row_to_todo(row) for row in rows]
        if sort_by == "due_date":
            records.sort(key=lambda r: (r["due_date"] or "9999", r["id"]))
        else:
            records.sort(
                key=lambda r: (
                    _PRIORITY_ORDER.get(r["priority"], 1),
                    r["due_date"] or "9999",
                    -r["id"],
                )
            )
        return records
    finally:
        conn.close()


def get_todo_record(todo_id: int) -> dict[str, Any] | None:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
        return _row_to_todo(row) if row else None
    finally:
        conn.close()


def update_todo_record(
    todo_id: int,
    title: str | None = None,
    due_date: str | None = None,
    priority: str | None = None,
    description: str | None = None,
    completed: bool | None = None,
    project_id: int | None = None,
    clear_project: bool = False,
    remind_at: str | None = None,
    clear_reminder: bool = False,
) -> dict[str, Any] | None:
    todo = get_todo_record(todo_id)
    if not todo:
        return None

    new_project_id = todo["project_id"]
    if clear_project:
        new_project_id = None
    elif project_id is not None:
        from tools.business.project import get_project_record

        if not get_project_record(project_id):
            raise ValueError(f"Project #{project_id} not found")
        new_project_id = project_id

    new_remind_at = todo.get("remind_at") or ""
    if clear_reminder:
        new_remind_at = ""
    elif remind_at is not None:
        new_remind_at = remind_at

    conn = _get_conn()
    try:
        conn.execute(
            """
            UPDATE todos
            SET title = ?, due_date = ?, priority = ?, description = ?,
                completed = ?, project_id = ?, updated_at = ?, remind_at = ?
            WHERE id = ?
            """,
            (
                title if title is not None else todo["title"],
                due_date if due_date is not None else todo["due_date"],
                priority if priority is not None else todo["priority"],
                description if description is not None else todo["description"],
                int(completed) if completed is not None else int(todo["completed"]),
                new_project_id,
                _now(),
                new_remind_at,
                todo_id,
            ),
        )
        conn.commit()
        updated = get_todo_record(todo_id)
        if updated:
            from tools.business.reminders import schedule_todo_reminder

            schedule_todo_reminder(updated)
        return updated
    finally:
        conn.close()


def delete_todo_record(todo_id: int) -> bool:
    from tools.business.reminders import cancel_todo_reminder

    cancel_todo_reminder(todo_id)
    conn = _get_conn()
    try:
        cur = conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_todo_stats_for_project(project_id: int) -> dict[str, Any]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT priority, completed FROM todos WHERE project_id = ?",
            (project_id,),
        ).fetchall()
        total = len(rows)
        completed = sum(1 for r in rows if r["completed"])
        by_priority: dict[str, int] = {}
        for row in rows:
            if row["completed"]:
                continue
            pri = row["priority"] or "normal"
            by_priority[pri] = by_priority.get(pri, 0) + 1
        return {"total": total, "completed": completed, "by_priority": by_priority}
    finally:
        conn.close()


def _format_todo_line(r: dict[str, Any]) -> str:
    status = "✓" if r["completed"] else "○"
    line = f"{status} #{r['id']} [{r['priority']}] {r['title']}"
    if r["due_date"]:
        line += f" (截止: {r['due_date']})"
    if r.get("remind_at"):
        line += f" [提醒: {r['remind_at']}]"
    elif r["due_date"]:
        line += " [到期提醒]"
    if r.get("project_id"):
        line += f" [项目 #{r['project_id']}]"
    return line


def _reminder_note(record: dict[str, Any]) -> str:
    from tools.business.reminders import effective_todo_remind_at, parse_remind_time

    when = effective_todo_remind_at(record)
    if not when:
        return ""
    parsed = parse_remind_time(when)
    if not parsed:
        return "（提醒时间格式无效，请用 ISO 8601）"
    if parsed <= datetime.now(timezone.utc):
        return "（提醒时间已过）"
    return f"，已设置提醒 {when}"


def create_todo_tools():
    from langchain_core.tools import tool

    @tool
    def create_todo(
        title: str,
        due_date: str = "",
        priority: str = "normal",
        project_id: int = 0,
        description: str = "",
        remind_at: str = "",
    ) -> str:
        """创建一条待办事项，可选关联项目 ID。due_date/remind_at 支持 ISO 8601 到期与提醒。"""
        try:
            pid = project_id if project_id > 0 else None
            record = create_todo_record(
                title, due_date, priority, pid, description, remind_at
            )
        except ValueError as e:
            return str(e)
        reminder_note = _reminder_note(record)
        proj_note = f"，项目 #{pid}" if pid else ""
        return (
            f"已创建待办 #{record['id']}: {record['title']} "
            f"(优先级: {priority}, 截止: {due_date or '无'}){proj_note}{reminder_note}"
        )

    @tool
    def list_todos(
        include_completed: bool = False,
        project_id: int = 0,
        sort_by: str = "priority",
    ) -> str:
        """列出待办，支持按项目筛选、按优先级或截止日期排序。"""
        pid = project_id if project_id > 0 else None
        records = list_todo_records(include_completed, pid, sort_by)
        if not records:
            return "暂无待办事项。"
        return "\n".join(_format_todo_line(r) for r in records)

    @tool
    def update_todo(
        todo_id: int,
        title: str = "",
        due_date: str = "",
        priority: str = "",
        description: str = "",
        remind_at: str = "",
    ) -> str:
        """更新待办标题、截止日、优先级、描述或提醒时间。"""
        try:
            updated = update_todo_record(
                todo_id,
                title=title or None,
                due_date=due_date or None,
                priority=priority or None,
                description=description or None,
                remind_at=remind_at or None,
            )
        except ValueError as e:
            return str(e)
        if not updated:
            return f"待办 #{todo_id} 不存在。"
        reminder = _reminder_note(updated)
        return f"已更新待办 #{todo_id}: {updated['title']}{reminder}"

    @tool
    def set_todo_reminder(todo_id: int, remind_at: str) -> str:
        """设置待办提醒时间（ISO 8601）。传空字符串清除提醒。"""
        if remind_at.strip():
            updated = update_todo_record(todo_id, remind_at=remind_at.strip())
        else:
            updated = update_todo_record(todo_id, clear_reminder=True)
        if not updated:
            return f"待办 #{todo_id} 不存在。"
        if updated.get("completed"):
            return f"待办 #{todo_id} 已完成，无需提醒。"
        note = _reminder_note(updated)
        return f"待办 #{todo_id} 提醒已更新{note or '（已清除）'}"

    @tool
    def complete_todo(todo_id: int, completed: bool = True) -> str:
        """标记待办为完成或重新打开。"""
        updated = update_todo_record(todo_id, completed=completed)
        if not updated:
            return f"待办 #{todo_id} 不存在。"
        state = "已完成" if completed else "已重新打开"
        return f"待办 #{todo_id} {state}: {updated['title']}"

    @tool
    def delete_todo(todo_id: int) -> str:
        """删除一条待办事项（需用户确认）。"""
        todo = get_todo_record(todo_id)
        if not todo:
            return f"待办 #{todo_id} 不存在。"
        delete_todo_record(todo_id)
        return f"已删除待办 #{todo_id}: {todo['title']}"

    @tool
    def assign_todo_to_project(todo_id: int, project_id: int) -> str:
        """将待办分配到指定项目。"""
        try:
            updated = update_todo_record(todo_id, project_id=project_id)
        except ValueError as e:
            return str(e)
        if not updated:
            return f"待办 #{todo_id} 不存在。"
        return f"待办 #{todo_id} 已分配到项目 #{project_id}"

    return [
        create_todo,
        list_todos,
        update_todo,
        complete_todo,
        delete_todo,
        assign_todo_to_project,
        set_todo_reminder,
    ]
