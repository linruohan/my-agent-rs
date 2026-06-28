"""项目 / Section / 每日总结存储与工具。"""

from tools.project.migrate import ensure_inbox_and_orphan_tasks, migrate_legacy_projects_db
from tools.project.stats import task_stats_for_project, task_stats_for_section, task_stats_inbox
from tools.project.store import (
    INBOX_PROJECT_NAME,
    ProjectStore,
    project_to_dict,
    section_to_dict,
    summary_to_dict,
)
from tools.project.commands import handle_project_command
from tools.project.tools import PROJECT_TOOLS

__all__ = [
    "handle_project_command",
    "INBOX_PROJECT_NAME",
    "PROJECT_TOOLS",
    "ProjectStore",
    "ensure_inbox_and_orphan_tasks",
    "migrate_legacy_projects_db",
    "project_to_dict",
    "section_to_dict",
    "summary_to_dict",
    "task_stats_for_project",
    "task_stats_for_section",
    "task_stats_inbox",
]
