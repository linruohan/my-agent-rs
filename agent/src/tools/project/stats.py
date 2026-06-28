"""项目 / Section 任务完成统计。"""

from __future__ import annotations

from typing import Any

from tools.task.store import TaskStore


def _count_tasks(rows) -> dict[str, Any]:
    total = len(rows)
    completed = sum(1 for r in rows if r.status == "done")
    by_status: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    priority_tags = {"high", "normal", "low"}
    for row in rows:
        if row.status == "done":
            continue
        by_status[row.status] = by_status.get(row.status, 0) + 1
        pri = "normal"
        for tag in row.tags:
            if tag in priority_tags:
                pri = tag
                break
        by_priority[pri] = by_priority.get(pri, 0) + 1
    return {
        "total": total,
        "completed": completed,
        "by_status": by_status,
        "by_priority": by_priority,
    }


def task_stats_for_project(project_id: int, *, store: TaskStore | None = None) -> dict[str, Any]:
    store = store or TaskStore()
    rows = store.list_filtered(project_id=project_id, include_done=True)
    return _count_tasks(rows)


def task_stats_for_section(section_id: int, *, store: TaskStore | None = None) -> dict[str, Any]:
    store = store or TaskStore()
    rows = store.list_filtered(section_id=section_id, include_done=True)
    return _count_tasks(rows)


def task_stats_inbox(*, store: TaskStore | None = None) -> dict[str, Any]:
    store = store or TaskStore()
    rows = store.list_filtered(inbox_only=True, include_done=True)
    return _count_tasks(rows)
