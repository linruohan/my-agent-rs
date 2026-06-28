"""HTTP API 与旧版 todos 前端的 TaskStore 适配层。"""

from __future__ import annotations

from typing import Any

from tools.project.stats import task_stats_for_project, task_stats_for_section
from tools.project.store import ProjectStore
from tools.task.store import TaskRow, TaskStore, VALID_STATUS

PROJECT_TAG_PREFIX = "project:"
PRIORITY_TAGS = frozenset({"high", "normal", "low"})


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


def task_to_todo(row: TaskRow, *, inbox_project_id: int | None = None) -> dict[str, Any]:
    pid = row.project_id
    if pid is None and inbox_project_id is not None:
        pid = inbox_project_id
    return {
        "id": row.id,
        "title": row.title,
        "due_date": row.due_at or "",
        "priority": _parse_priority(row.tags),
        "completed": row.status == "done",
        "project_id": pid,
        "section_id": row.section_id,
        "description": row.content,
        "remind_at": row.remind_at or "",
        "status": row.status,
        "owner": row.owner,
        "tags": _user_tags(row.tags),
    }


def _build_tags(priority: str = "normal", extra_tags: list[str] | None = None) -> list[str]:
    tags: list[str] = []
    if priority and priority != "normal":
        tags.append(priority)
    for tag in extra_tags or []:
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def _resolve_project_id(project_id: int | None, store: ProjectStore) -> int:
    if project_id is not None:
        if not store.get_project(project_id):
            raise ValueError(f"Project #{project_id} not found")
        return project_id
    return store.ensure_inbox().id


def create_todo_record(
    title: str,
    due_date: str = "",
    priority: str = "normal",
    project_id: int | None = None,
    section_id: int | None = None,
    description: str = "",
    remind_at: str = "",
    tags: list[str] | None = None,
    *,
    store: TaskStore | None = None,
) -> dict[str, Any]:
    pstore = ProjectStore()
    pid = _resolve_project_id(project_id, pstore)
    inbox_id = pstore.ensure_inbox().id
    if pid == inbox_id:
        section_id = None
    elif section_id is not None:
        section = pstore.get_section(section_id)
        if not section:
            raise ValueError(f"Section #{section_id} not found")
        if section.project_id != pid:
            raise ValueError(f"Section #{section_id} does not belong to project #{pid}")

    store = store or TaskStore()
    row = store.add(
        title,
        description,
        due_at=due_date or None,
        remind_at=remind_at or None,
        tags=_build_tags(priority, tags),
        status="pending",
        project_id=pid,
        section_id=section_id,
    )
    return task_to_todo(row, inbox_project_id=inbox_id)


def list_todo_records(
    include_completed: bool = False,
    project_id: int | None = None,
    section_id: int | None = None,
    inbox_only: bool = False,
    sort_by: str = "priority",
    *,
    store: TaskStore | None = None,
) -> list[dict[str, Any]]:
    store = store or TaskStore()
    pstore = ProjectStore()
    inbox_id = pstore.ensure_inbox().id
    rows = store.list_filtered(
        include_done=include_completed,
        project_id=project_id,
        section_id=section_id,
        inbox_only=inbox_only,
    )
    records = [task_to_todo(r, inbox_project_id=inbox_id) for r in rows]

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
    return task_to_todo(row, inbox_project_id=ProjectStore().ensure_inbox().id) if row else None


def update_todo_record(
    todo_id: int,
    title: str | None = None,
    due_date: str | None = None,
    priority: str | None = None,
    description: str | None = None,
    completed: bool | None = None,
    project_id: int | None = None,
    section_id: int | None = None,
    clear_project: bool = False,
    clear_section: bool = False,
    remind_at: str | None = None,
    clear_reminder: bool = False,
    tags: list[str] | None = None,
    *,
    store: TaskStore | None = None,
) -> dict[str, Any] | None:
    store = store or TaskStore()
    row = store.get(todo_id)
    if not row:
        return None

    if project_id is not None:
        _resolve_project_id(project_id, ProjectStore())

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
    if clear_project:
        kwargs["project_id"] = ProjectStore().ensure_inbox().id
        kwargs["clear_section"] = True
    elif project_id is not None:
        pstore = ProjectStore()
        pid = _resolve_project_id(project_id, pstore)
        kwargs["project_id"] = pid
        if pid == pstore.ensure_inbox().id:
            kwargs["clear_section"] = True
    if clear_section:
        kwargs["clear_section"] = True
    elif section_id is not None:
        kwargs["section_id"] = section_id

    new_priority = priority if priority is not None else _parse_priority(row.tags)
    user_tags = tags if tags is not None else _user_tags(row.tags)
    kwargs["tags"] = _build_tags(new_priority, user_tags)

    store.update(todo_id, **kwargs)
    updated = store.get(todo_id)
    inbox_id = ProjectStore().ensure_inbox().id
    return task_to_todo(updated, inbox_project_id=inbox_id) if updated else None


def delete_todo_record(todo_id: int, *, store: TaskStore | None = None) -> bool:
    store = store or TaskStore()
    return store.delete(todo_id)


def get_todo_stats_for_project(project_id: int, *, store: TaskStore | None = None) -> dict[str, Any]:
    return task_stats_for_project(project_id, store=store)


def get_todo_stats_for_section(section_id: int, *, store: TaskStore | None = None) -> dict[str, Any]:
    return task_stats_for_section(section_id, store=store)


def list_task_reminders(*, store: TaskStore | None = None) -> list[dict[str, Any]]:
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
    import sqlite3

    from infra.config import get_data_dir

    legacy = get_data_dir() / "todos.db"
    if not legacy.is_file():
        return 0

    store = store or TaskStore()
    pstore = ProjectStore()
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
        raw_pid = row["project_id"]
        project_id = int(raw_pid) if raw_pid is not None else None
        try:
            store.add(
                title,
                str(row["description"] or ""),
                due_at=due_at,
                remind_at=remind,
                tags=_build_tags(str(row["priority"] or "normal")),
                status=status,
                created_at=str(row["created_at"]) if row["created_at"] else None,
                project_id=project_id or pstore.ensure_inbox().id,
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
