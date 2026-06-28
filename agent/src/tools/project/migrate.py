"""从 legacy projects.db 迁移到 project.db，并同步 task 的 project_id。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from loguru import logger

from infra.config import get_data_dir
from tools.project.store import ProjectStore, project_to_dict
from tools.task.store import TaskStore

_PROJECT_TAG_PREFIX = "project:"


def migrate_legacy_projects_db(
    project_store: ProjectStore | None = None,
    task_store: TaskStore | None = None,
) -> int:
    legacy = get_data_dir() / "projects.db"
    if not legacy.is_file():
        return 0

    project_store = project_store or ProjectStore()
    task_store = task_store or TaskStore()
    project_store.ensure_inbox()

    conn = sqlite3.connect(legacy)
    conn.row_factory = sqlite3.Row
    imported = 0
    id_map: dict[int, int] = {}

    try:
        for row in conn.execute("SELECT * FROM projects ORDER BY id").fetchall():
            name = str(row["name"] or "").strip()
            if not name:
                continue
            created = project_store.add_project(
                name,
                description=str(row["description"] or ""),
                status=str(row["status"] or "active"),
                end_at=str(row["due_date"] or "").strip() or None,
                remind_at=str(row["remind_at"] or "").strip() or None,
            )
            id_map[int(row["id"])] = created.id
            imported += 1

        for row in conn.execute("SELECT * FROM project_docs ORDER BY id").fetchall():
            old_pid = int(row["project_id"])
            new_pid = id_map.get(old_pid)
            if not new_pid:
                continue
            project_store.add_doc(
                new_pid,
                str(row["title"] or ""),
                str(row["file_path"] or ""),
                str(row["note"] or ""),
            )
    except sqlite3.Error as exc:
        logger.warning("读取 legacy projects.db 失败: {}", exc)
        return 0
    finally:
        conn.close()

    _migrate_task_project_tags(task_store, id_map)

    if imported >= 0:
        backup = legacy.with_suffix(".db.migrated")
        try:
            legacy.replace(backup)
            if imported:
                logger.info("已迁移 {} 个项目至 project.db", imported)
        except OSError as exc:
            logger.warning("迁移完成但无法重命名 projects.db: {}", exc)
    return imported


def _migrate_task_project_tags(task_store: TaskStore, id_map: dict[int, int]) -> None:
    if not id_map:
        return
    for row in task_store.list_all(include_done=True):
        if row.project_id is not None:
            continue
        old_pid: int | None = None
        for tag in row.tags:
            if tag.startswith(_PROJECT_TAG_PREFIX):
                try:
                    old_pid = int(tag[len(_PROJECT_TAG_PREFIX) :])
                except ValueError:
                    continue
                break
        if old_pid is None:
            continue
        new_pid = id_map.get(old_pid)
        if new_pid is None:
            continue
        new_tags = [t for t in row.tags if not t.startswith(_PROJECT_TAG_PREFIX)]
        task_store.update(row.id, project_id=new_pid, tags=new_tags)


def ensure_inbox_and_orphan_tasks(
    project_store: ProjectStore | None = None,
    task_store: TaskStore | None = None,
) -> int:
    """确保 Inbox 存在，并将无 project 的任务归入 Inbox。"""
    project_store = project_store or ProjectStore()
    task_store = task_store or TaskStore()
    inbox = project_store.ensure_inbox()
    fixed = 0
    for row in task_store.list_all(include_done=True):
        if row.project_id is not None:
            continue
        task_store.update(row.id, project_id=inbox.id)
        fixed += 1
    return fixed
