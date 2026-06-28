from __future__ import annotations

import sys
import tempfile
from pathlib import Path

AGENT_SRC = Path(__file__).resolve().parents[1] / "agent" / "src"
if str(AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(AGENT_SRC))


def _patch_data_dirs(monkeypatch, data_dir: Path) -> None:
    from infra.scheduler import shutdown_scheduler

    monkeypatch.setattr("tools.business.project.DB_PATH", data_dir / "projects.db")
    monkeypatch.setattr("infra.config.get_data_dir", lambda: data_dir)
    shutdown_scheduler()


def test_create_and_list_todos(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        _patch_data_dirs(monkeypatch, data_dir)

        from tools.business.todo import create_todo_record, list_todo_records

        record = create_todo_record("Buy milk", due_date="2026-06-28", priority="high")
        assert record["id"] == 1
        assert record["title"] == "Buy milk"

        todos = list_todo_records()
        assert len(todos) == 1
        assert todos[0]["title"] == "Buy milk"
        assert todos[0]["priority"] == "high"


def test_todo_crud_and_project_link(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        _patch_data_dirs(monkeypatch, data_dir)

        from tools.business.project import create_project_record
        from tools.business.todo import (
            create_todo_record,
            delete_todo_record,
            get_todo_stats_for_project,
            list_todo_records,
            update_todo_record,
        )

        project = create_project_record("Website", status="active")
        todo = create_todo_record("Deploy", project_id=project["id"], priority="high")
        update_todo_record(todo["id"], description="Production deploy")
        updated = update_todo_record(todo["id"], completed=True)
        assert updated and updated["completed"] is True

        stats = get_todo_stats_for_project(project["id"])
        assert stats["total"] == 1
        assert stats["completed"] == 1

        assert delete_todo_record(todo["id"])
        assert list_todo_records(include_completed=True) == []


def test_task_tools_invoke(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        _patch_data_dirs(monkeypatch, data_dir)

        from tools.task.tools import TASK_TOOLS

        tools = {t.name: t for t in TASK_TOOLS}
        result = tools["add_task"].invoke({"title": "Write tests"})
        assert "Write tests" in result

        list_result = tools["list_tasks"].invoke({"include_done": False})
        assert "Write tests" in list_result

        complete_result = tools["complete_task"].invoke({"task_id": 1})
        assert "完成" in complete_result
