from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from infra.config import get_data_dir

DB_PATH = get_data_dir() / "projects.db"

VALID_STATUSES = ("planning", "active", "on_hold", "completed", "archived")


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            due_date TEXT DEFAULT '',
            remind_at TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS project_docs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            file_path TEXT DEFAULT '',
            note TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
        """
    )
    _migrate_projects(conn)
    conn.commit()
    return conn


def _migrate_projects(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(projects)")}
    if "remind_at" not in cols:
        conn.execute("ALTER TABLE projects ADD COLUMN remind_at TEXT DEFAULT ''")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_project_record(
    name: str,
    description: str = "",
    status: str = "active",
    due_date: str = "",
    remind_at: str = "",
) -> dict[str, Any]:
    status = status if status in VALID_STATUSES else "active"
    conn = _get_conn()
    try:
        ts = _now()
        cur = conn.execute(
            """
            INSERT INTO projects (name, description, status, due_date, remind_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (name, description, status, due_date, remind_at, ts, ts),
        )
        conn.commit()
        record = {
            "id": cur.lastrowid,
            "name": name,
            "description": description,
            "status": status,
            "due_date": due_date,
            "remind_at": remind_at,
        }
        from tools.business.reminders import schedule_project_reminder

        schedule_project_reminder(record)
        return record
    finally:
        conn.close()


def list_project_records(status: str = "") -> list[dict[str, Any]]:
    conn = _get_conn()
    try:
        if status and status in VALID_STATUSES:
            rows = conn.execute(
                "SELECT * FROM projects WHERE status = ? ORDER BY id DESC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM projects WHERE status != 'archived' ORDER BY id DESC"
            ).fetchall()
        return [_row_to_project(row) for row in rows]
    finally:
        conn.close()


def get_project_record(project_id: int) -> dict[str, Any] | None:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return _row_to_project(row) if row else None
    finally:
        conn.close()


def update_project_record(
    project_id: int,
    name: str | None = None,
    description: str | None = None,
    status: str | None = None,
    due_date: str | None = None,
    remind_at: str | None = None,
    clear_reminder: bool = False,
) -> dict[str, Any] | None:
    project = get_project_record(project_id)
    if not project:
        return None
    if status is not None and status not in VALID_STATUSES:
        status = project["status"]
    new_remind_at = project.get("remind_at") or ""
    if clear_reminder:
        new_remind_at = ""
    elif remind_at is not None:
        new_remind_at = remind_at
    conn = _get_conn()
    try:
        conn.execute(
            """
            UPDATE projects
            SET name = ?, description = ?, status = ?, due_date = ?, remind_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                name if name is not None else project["name"],
                description if description is not None else project["description"],
                status if status is not None else project["status"],
                due_date if due_date is not None else project["due_date"],
                new_remind_at,
                _now(),
                project_id,
            ),
        )
        conn.commit()
        updated = get_project_record(project_id)
        if updated:
            from tools.business.reminders import schedule_project_reminder

            schedule_project_reminder(updated)
        return updated
    finally:
        conn.close()


def _resolve_doc_path(path: str) -> Path | None:
    from pathlib import Path

    from infra.config import resolve_workspace_path

    raw = (path or "").strip()
    if not raw:
        return None
    try:
        target = resolve_workspace_path(raw)
        if target.exists():
            return target
    except ValueError:
        pass
    direct = Path(raw)
    if direct.is_file():
        return direct
    return None


def _ingest_project_doc_to_rag(
    project_id: int,
    title: str,
    file_path: str = "",
    note: str = "",
) -> str:
    """Index project document path or note into RAG."""
    from memory.rag import SUPPORTED_EXTENSIONS, RagStore, _extract_file_text

    rag = RagStore()
    source_base = f"project-{project_id}/{title}"
    parts: list[str] = []

    target = _resolve_doc_path(file_path)
    if file_path.strip() and target is None:
        parts.append(f"文件不存在或不在工作区内，未索引: {file_path.strip()}")
    elif target is not None:
        if target.suffix.lower() not in SUPPORTED_EXTENSIONS:
            parts.append(f"不支持的文件类型: {target.suffix}")
        else:
            try:
                content = _extract_file_text(target)
                count = rag.ingest_text(content, source=source_base)
                if count:
                    parts.append(f"RAG 已索引文件 ({count} chunks)")
                else:
                    parts.append("RAG 跳过（内容未变化）")
            except Exception as e:
                parts.append(f"RAG 索引失败: {e}")

    text = (note or "").strip()
    if text:
        count = rag.ingest_text(text, source=f"{source_base}:note")
        if count:
            parts.append(f"RAG 已索引备注 ({count} chunks)")

    return "；".join(parts)


def add_project_doc_record(
    project_id: int,
    title: str,
    file_path: str = "",
    note: str = "",
    auto_ingest: bool = True,
) -> dict[str, Any] | None:
    if not get_project_record(project_id):
        return None
    conn = _get_conn()
    try:
        cur = conn.execute(
            """
            INSERT INTO project_docs (project_id, title, file_path, note, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (project_id, title, file_path, note, _now()),
        )
        conn.commit()
        doc = {
            "id": cur.lastrowid,
            "project_id": project_id,
            "title": title,
            "file_path": file_path,
            "note": note,
        }
        if auto_ingest and (file_path.strip() or note.strip()):
            doc["rag_ingest"] = _ingest_project_doc_to_rag(
                project_id, title, file_path, note
            )
        return doc
    finally:
        conn.close()


def list_project_docs(project_id: int) -> list[dict[str, Any]]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM project_docs WHERE project_id = ? ORDER BY id DESC",
            (project_id,),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "project_id": row["project_id"],
                "title": row["title"],
                "file_path": row["file_path"],
                "note": row["note"],
            }
            for row in rows
        ]
    finally:
        conn.close()


def _row_to_project(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "status": row["status"],
        "due_date": row["due_date"],
        "remind_at": row["remind_at"] if "remind_at" in row.keys() else "",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _project_reminder_note(project: dict[str, Any]) -> str:
    from tools.business.reminders import parse_remind_time

    when = (project.get("remind_at") or project.get("due_date") or "").strip()
    if not when:
        return ""
    parsed = parse_remind_time(when)
    if not parsed:
        return "（提醒时间格式无效）"
    if parsed <= datetime.now(timezone.utc):
        return "（提醒时间已过）"
    return f"，已设置提醒 {when}"


def create_project_tools():
    from langchain_core.tools import tool

    @tool
    def create_project(
        name: str,
        description: str = "",
        status: str = "active",
        due_date: str = "",
        remind_at: str = "",
    ) -> str:
        """Create a project; due_date/remind_at (ISO 8601) schedule deadline reminders."""
        record = create_project_record(name, description, status, due_date, remind_at)
        note = _project_reminder_note(record)
        return (
            f"已创建项目 #{record['id']}: {record['name']} "
            f"(状态: {record['status']}, 截止: {record['due_date'] or '无'}){note}"
        )

    @tool
    def list_projects(status: str = "") -> str:
        """List projects. Optional status filter: planning/active/on_hold/completed/archived."""
        records = list_project_records(status)
        if not records:
            return "暂无项目。"
        lines = []
        for p in records:
            line = f"#{p['id']} [{p['status']}] {p['name']}"
            if p["due_date"]:
                line += f" (截止: {p['due_date']})"
            if p.get("remind_at"):
                line += f" [提醒: {p['remind_at']}]"
            if p["description"]:
                line += f" — {p['description'][:80]}"
            lines.append(line)
        return "\n".join(lines)

    @tool
    def update_project(
        project_id: int,
        name: str = "",
        description: str = "",
        status: str = "",
        due_date: str = "",
    ) -> str:
        """Update project metadata or lifecycle status."""
        updated = update_project_record(
            project_id,
            name=name or None,
            description=description or None,
            status=status or None,
            due_date=due_date or None,
        )
        if not updated:
            return f"项目 #{project_id} 不存在。"
        note = _project_reminder_note(updated)
        return f"已更新项目 #{project_id}: {updated['name']} (状态: {updated['status']}){note}"

    @tool
    def set_project_reminder(project_id: int, remind_at: str) -> str:
        """Set project reminder time (ISO 8601). Empty string clears reminder."""
        if remind_at.strip():
            updated = update_project_record(project_id, remind_at=remind_at.strip())
        else:
            updated = update_project_record(project_id, clear_reminder=True)
        if not updated:
            return f"项目 #{project_id} 不存在。"
        if updated.get("status") in ("completed", "archived"):
            return f"项目 #{project_id} 已结束，无需提醒。"
        note = _project_reminder_note(updated)
        return f"项目 #{project_id} 提醒已更新{note or '（已清除）'}"

    @tool
    def get_project_status(project_id: int) -> str:
        """Get project progress: task counts and linked documents."""
        from tools.business.todo import get_todo_stats_for_project

        project = get_project_record(project_id)
        if not project:
            return f"项目 #{project_id} 不存在。"
        stats = get_todo_stats_for_project(project_id)
        docs = list_project_docs(project_id)
        total = stats["total"]
        done = stats["completed"]
        pct = int(done / total * 100) if total else 0
        lines = [
            f"项目 #{project_id}: {project['name']} [{project['status']}]",
            f"任务进度: {done}/{total} ({pct}%)",
        ]
        if stats["by_priority"]:
            lines.append(
                "待办优先级: "
                + ", ".join(f"{k}={v}" for k, v in stats["by_priority"].items())
            )
        if docs:
            lines.append(f"文档 ({len(docs)}):")
            for d in docs[:10]:
                path_part = f" @ {d['file_path']}" if d["file_path"] else ""
                lines.append(f"  - #{d['id']} {d['title']}{path_part}")
        return "\n".join(lines)

    @tool
    def add_project_document(
        project_id: int,
        title: str,
        file_path: str = "",
        note: str = "",
    ) -> str:
        """Attach a document reference or note to a project."""
        doc = add_project_doc_record(project_id, title, file_path, note)
        if not doc:
            return f"项目 #{project_id} 不存在。"
        msg = f"已为项目 #{project_id} 添加文档 #{doc['id']}: {title}"
        if doc.get("rag_ingest"):
            msg += f"。{doc['rag_ingest']}"
        return msg

    return [
        create_project,
        list_projects,
        update_project,
        get_project_status,
        add_project_document,
        set_project_reminder,
    ]
