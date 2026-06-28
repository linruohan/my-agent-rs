"""HTTP API 与旧版 todos 前端的 TaskStore 适配层。"""

from __future__ import annotations

from typing import Any

from tools.task.store import TaskRow, TaskStore, VALID_STATUS

PROJECT_TAG_PREFIX = "project:"
PRIORITY_TAGS = frozenset({"high", "normal", "low"})


def project_tag(project_id: int) -> str:
    return f"{PROJECT_TAG_PREFIX}{project_id}"


def _parse_project_id(tags: list[str]) -> int | None:
    for tag in tags:
        if tag.startswith(PROJECT_TAG_PREFIX):
            try:
                return int(tag[len(PROJECT_TAG_PREFIX) :])
            except ValueError:
                continue
    return None


def _parse_priority(tags: list[str]) -> str:
    for tag in tags:
        if tag in PRIORITY_TAGS:
            return tag
    return "normal"


def _user_tags(tags: list[str]) -> list[str]:
    out: list[str] = []
    for tag in tags:
        if tag.startswith(PROJECT_TAG_PREFIX) or tag in PRIORITY_TAGS:
            continue
        out.append(tag)
    return out


def task_to_todo(row: TaskRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "title": row.title,
        "due_date": row.due_at or "",
        "priority": _parse_priority(row.tags),
        "completed": row.status == "done",
        "project_id": _parse_project_id(row.tags),
        "description": row.content,
        "remind_at": row.remind_at or "",
        "status": row.status,
        "owner": row.owner,
        "tags": _user_tags(row.tags),
    }


def _build_tags(
    priority: str = "normal",
    project_id: int | None = None,
    extra_tags: list[str] | None = None,
) -> list[str]:
    tags: list[str] = []
    if priority and priority != "normal":
        tags.append(priority)
    if project_id is not None:
        tags.append(project_tag(project_id))
    for tag in extra_tags or []:
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def create_todo_record(
    title: str,
    due_date: str = "",
    priority: str = "normal",
    project_id: int | None = None,
    description: str = "",
    remind_at: str = "",
    *,
    store: TaskStore | None = None,
) -> dict[str, Any]:
    if project_id is not None:
        from tools.business.project import get_project_record

        if not get_project_record(project_id):
            raise ValueError(f"Project #{project_id} not found")

    store = store or TaskStore()
    row = store.add(
        title,
        description,
        due_at=due_date or None,
        remind_at=remind_at or None,
        tags=_build_tags(priority, project_id),
        status="pending",
    )
    return task_to_todo(row)


def list_todo_records(
    include_completed: bool = False,
    project_id: int | None = None,
    sort_by: str = "priority",
    *,
    store: TaskStore | None = None,
) -> list[dict[str, Any]]:
    store = store or TaskStore()
    rows = store.list_all(include_done=include_completed)
    records = [task_to_todo(r) for r in rows]
    if project_id is not None:
        records = [r for r in records if r.get("project_id") == project_id]
    if not include_completed:
        records = [r for r in records if not r["completed"]]

    priority_order = {"high": 0, "normal": 1, "low": 2}
    if sort_by == "due_date":
        records.sort(key=lambda r: (r["due_date"] or "9999", r["id"]))
    else:
        records.sort(
            key=lambda r: (
                priority_order.get(r["priority"], 1),
                r["due_date"] or "9999",
                -r["id"],
            )
        )
    return records


def get_todo_record(todo_id: int, *, store: TaskStore | None = None) -> dict[str, Any] | None:
    store = store or TaskStore()
    row = store.get(todo_id)
    return task_to_todo(row) if row else None


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
    *,
    store: TaskStore | None = None,
) -> dict[str, Any] | None:
    store = store or TaskStore()
    row = store.get(todo_id)
    if not row:
        return None

    if project_id is not None:
        from tools.business.project import get_project_record

        if not get_project_record(project_id):
            raise ValueError(f"Project #{project_id} not found")

    kwargs: dict[str, Any] = {}
    if title is not None:
        kwargs["title"] = title
    if description is not None:
        kwargs["content"] = description
    if due_date is not None:
        kwargs["due_at"] = due_date or None
    if completed is not None:
        kwargs["status"] = "done" if completed else "pending"
    if clear_reminder:
        kwargs["clear_remind"] = True
    elif remind_at is not None:
        kwargs["remind_at"] = remind_at or None

    new_tags = _user_tags(row.tags)
    new_priority = priority if priority is not None else _parse_priority(row.tags)
    new_project = _parse_project_id(row.tags)
    if clear_project:
        new_project = None
    elif project_id is not None:
        new_project = project_id
    kwargs["tags"] = _build_tags(new_priority, new_project, new_tags)

    store.update(todo_id, **kwargs)
    updated = store.get(todo_id)
    return task_to_todo(updated) if updated else None


def delete_todo_record(todo_id: int, *, store: TaskStore | None = None) -> bool:
    store = store or TaskStore()
    return store.delete(todo_id)


def get_todo_stats_for_project(project_id: int, *, store: TaskStore | None = None) -> dict[str, Any]:
    records = list_todo_records(include_completed=True, project_id=project_id, store=store)
    total = len(records)
    completed = sum(1 for r in records if r["completed"])
    by_priority: dict[str, int] = {}
    for row in records:
        if row["completed"]:
            continue
        pri = row["priority"] or "normal"
        by_priority[pri] = by_priority.get(pri, 0) + 1
    return {"total": total, "completed": completed, "by_priority": by_priority}


def list_task_reminders(*, store: TaskStore | None = None) -> list[dict[str, Any]]:
    """列出 task.db 中尚未触发的提醒时刻。"""
    from datetime import datetime

    store = store or TaskStore()
    now = datetime.now().astimezone()
    items: list[dict[str, Any]] = []
    for row in store.list_all(include_done=False):
        if row.status not in ("pending", "planned"):
            continue
        remind_times = list(row.remind_schedule or [])
        if row.remind_at and row.remind_at not in remind_times:
            remind_times.append(row.remind_at)
        for iso in remind_times:
            if not iso:
                continue
            try:
                dt = datetime.fromisoformat(iso)
                if dt.tzinfo is None:
                    dt = dt.astimezone()
            except ValueError:
                continue
            if dt <= now:
                continue
            items.append(
                {
                    "job_id": f"task-{row.id}-{iso}",
                    "run_at": iso,
                    "title": "任务提醒",
                    "message": f"#{row.id} {row.title}",
                    "entity_type": "task",
                    "entity_id": row.id,
                }
            )
    items.sort(key=lambda x: x.get("run_at", ""))
    return items


def migrate_todos_db(*, store: TaskStore | None = None) -> int:
    """一次性从 legacy todos.db 导入 task.db。"""
    import sqlite3
    from pathlib import Path

    from infra.config import get_data_dir

    legacy = get_data_dir() / "todos.db"
    if not legacy.is_file():
        return 0

    store = store or TaskStore()
    conn = sqlite3.connect(legacy)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM todos ORDER BY id").fetchall()
    except sqlite3.Error:
        return 0
    finally:
        conn.close()

    imported = 0
    for row in rows:
        title = str(row["title"] or "").strip()
        if not title:
            continue
        status = "done" if row["completed"] else "pending"
        if status not in VALID_STATUS:
            status = "pending"
        due = str(row["due_date"] or "").strip()
        due_at = due if due and "T" in due else (f"{due}T00:00:00" if due else None)
        remind = str(row["remind_at"] or "").strip() or None
        project_id = row["project_id"]
        tags = _build_tags(
            str(row["priority"] or "normal"),
            int(project_id) if project_id is not None else None,
        )
        try:
            store.add(
                title,
                str(row["description"] or ""),
                due_at=due_at,
                remind_at=remind,
                tags=tags or None,
                status=status,
                created_at=str(row["created_at"]) if row["created_at"] else None,
            )
            imported += 1
        except ValueError:
            continue

    if imported:
        backup = legacy.with_suffix(".db.migrated")
        try:
            legacy.replace(backup)
        except OSError:
            pass
    return imported
