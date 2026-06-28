from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


@pytest.fixture
def data_dirs(monkeypatch, tmp_path: Path):
    from infra.scheduler import shutdown_scheduler

    monkeypatch.setattr("tools.business.todo.DB_PATH", tmp_path / "todos.db")
    monkeypatch.setattr("tools.business.project.DB_PATH", tmp_path / "projects.db")
    monkeypatch.setattr("infra.scheduler._get_db", lambda: tmp_path / "scheduler.db")
    monkeypatch.setattr("infra.config.get_data_dir", lambda: tmp_path)
    yield tmp_path
    shutdown_scheduler()


def test_todo_reminder_scheduled(data_dirs):
    from infra.scheduler import list_pending_jobs, shutdown_scheduler
    from tools.business.todo import create_todo_record

    shutdown_scheduler()
    run_at = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    record = create_todo_record("Call client", remind_at=run_at)
    jobs = list_pending_jobs()
    assert any(j["id"] == f"todo-{record['id']}" for j in jobs)


def test_todo_reminder_cancelled_on_complete(data_dirs):
    from infra.scheduler import list_pending_jobs, shutdown_scheduler
    from tools.business.todo import create_todo_record, update_todo_record

    shutdown_scheduler()
    run_at = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    record = create_todo_record("Finish report", remind_at=run_at)
    update_todo_record(record["id"], completed=True)
    jobs = list_pending_jobs()
    assert not any(j["id"] == f"todo-{record['id']}" and j["status"] == "pending" for j in jobs)


def test_project_reminder_scheduled(data_dirs):
    from infra.scheduler import list_pending_jobs, shutdown_scheduler
    from tools.business.project import create_project_record

    shutdown_scheduler()
    run_at = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    project = create_project_record("Launch", due_date=run_at)
    jobs = list_pending_jobs()
    assert any(j["id"] == f"project-{project['id']}" for j in jobs)


def test_list_entity_reminders(data_dirs):
    from tools.business.project import create_project_record
    from tools.business.reminders import list_entity_reminders
    from tools.business.todo import create_todo_record

    run_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    create_todo_record("A", remind_at=run_at)
    create_project_record("P", remind_at=run_at)
    items = list_entity_reminders()
    assert len(items) >= 2
    assert any(i["entity_type"] == "todo" for i in items)
    assert any(i["entity_type"] == "project" for i in items)
