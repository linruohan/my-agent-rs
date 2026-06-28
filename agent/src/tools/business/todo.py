"""Legacy todo API facade — backed by tools.task (task.db)."""

from __future__ import annotations

from tools.task.api_compat import (
    create_todo_record,
    delete_todo_record,
    get_todo_record,
    get_todo_stats_for_project,
    get_todo_stats_for_section,
    list_todo_records,
    update_todo_record,
)

__all__ = [
    "create_todo_record",
    "delete_todo_record",
    "get_todo_record",
    "get_todo_stats_for_project",
    "get_todo_stats_for_section",
    "list_todo_records",
    "update_todo_record",
    "create_todo_tools",
]


def create_todo_tools():
    """Deprecated: use tools.task.tools.TASK_TOOLS."""
    from tools.task.tools import TASK_TOOLS

    return list(TASK_TOOLS)
