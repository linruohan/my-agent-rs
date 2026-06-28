from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

TODO_JOB_PREFIX = "todo-"
PROJECT_JOB_PREFIX = "project-"


def parse_remind_time(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (ValueError, TypeError):
        return None


def todo_job_id(todo_id: int) -> str:
    return f"{TODO_JOB_PREFIX}{todo_id}"


def project_job_id(project_id: int) -> str:
    return f"{PROJECT_JOB_PREFIX}{project_id}"


def effective_todo_remind_at(todo: dict[str, Any]) -> str:
    remind = (todo.get("remind_at") or "").strip()
    if remind:
        return remind
    return (todo.get("due_date") or "").strip()


def schedule_todo_reminder(todo: dict[str, Any]) -> str:
    from infra.scheduler import cancel_reminder, schedule_reminder

    todo_id = int(todo["id"])
    job_id = todo_job_id(todo_id)

    if todo.get("completed"):
        cancel_reminder(job_id)
        return ""

    when = parse_remind_time(effective_todo_remind_at(todo))
    if not when:
        cancel_reminder(job_id)
        return ""

    now = datetime.now(timezone.utc)
    if when <= now:
        cancel_reminder(job_id)
        return "提醒时间已过，未调度"

    title = "待办提醒"
    due = (todo.get("due_date") or "").strip()
    msg = f"待办 #{todo_id}: {todo['title']}"
    if due and due != effective_todo_remind_at(todo):
        msg += f"（截止: {due}）"
    if todo.get("project_id"):
        msg += f" [项目 #{todo['project_id']}]"

    schedule_reminder(job_id, title, msg, when)
    return when.isoformat()


def schedule_project_reminder(project: dict[str, Any]) -> str:
    from infra.scheduler import cancel_reminder, schedule_reminder
    from tools.business.todo import get_todo_stats_for_project

    project_id = int(project["id"])
    job_id = project_job_id(project_id)
    status = project.get("status", "active")

    if status in ("completed", "archived"):
        cancel_reminder(job_id)
        return ""

    when = parse_remind_time(
        (project.get("remind_at") or project.get("due_date") or "").strip()
    )
    if not when:
        cancel_reminder(job_id)
        return ""

    now = datetime.now(timezone.utc)
    if when <= now:
        cancel_reminder(job_id)
        return "提醒时间已过，未调度"

    stats = get_todo_stats_for_project(project_id)
    pending = stats["total"] - stats["completed"]
    msg = f"项目 #{project_id}: {project['name']}"
    if pending:
        msg += f"（剩余 {pending} 项待办）"
    else:
        msg += "（所有任务已完成）"

    schedule_reminder(job_id, "项目提醒", msg, when)
    return when.isoformat()


def cancel_todo_reminder(todo_id: int) -> None:
    from infra.scheduler import cancel_reminder

    cancel_reminder(todo_job_id(todo_id))


def cancel_project_reminder(project_id: int) -> None:
    from infra.scheduler import cancel_reminder

    cancel_reminder(project_job_id(project_id))


def resync_all_reminders() -> int:
    """Re-register future project reminders (task reminders use TaskReminderService)."""
    from tools.business.project import list_project_records

    count = 0
    for project in list_project_records(""):
        if schedule_project_reminder(project):
            count += 1
    return count


def list_entity_reminders() -> list[dict[str, Any]]:
    from infra.scheduler import list_pending_jobs
    from tools.task.api_compat import list_task_reminders

    items: list[dict[str, Any]] = list_task_reminders()
    seen = {item["job_id"] for item in items}
    for job in list_pending_jobs():
        job_id = job.get("id", "")
        if job_id in seen:
            continue
        payload = job.get("payload", "")
        title, _, message = payload.partition("|")
        entry: dict[str, Any] = {
            "job_id": job_id,
            "run_at": job.get("run_at", ""),
            "title": title,
            "message": message or payload,
        }
        if job_id.startswith(TODO_JOB_PREFIX):
            entry["entity_type"] = "todo"
            entry["entity_id"] = int(job_id[len(TODO_JOB_PREFIX) :])
        elif job_id.startswith(PROJECT_JOB_PREFIX):
            entry["entity_type"] = "project"
            entry["entity_id"] = int(job_id[len(PROJECT_JOB_PREFIX) :])
        else:
            entry["entity_type"] = "other"
        items.append(entry)
    items.sort(key=lambda x: x.get("run_at", ""))
    return items
