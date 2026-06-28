from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


@pytest.fixture
def data_dirs(monkeypatch, tmp_path: Path):
    from infra.scheduler import shutdown_scheduler

    monkeypatch.setenv("AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("infra.scheduler._get_db", lambda: tmp_path / "scheduler.db")
    yield tmp_path
    shutdown_scheduler()


def test_task_reminder_listed(data_dirs):
    from tools.business.reminders import list_entity_reminders
    from tools.business.todo import create_todo_record

    run_at = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    record = create_todo_record("Call client", remind_at=run_at)
    items = list_entity_reminders()
    assert any(i["entity_type"] == "task" and i["entity_id"] == record["id"] for i in items)


def test_task_reminder_hidden_when_done(data_dirs):
    from tools.business.reminders import list_entity_reminders
    from tools.business.todo import create_todo_record, update_todo_record

    run_at = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    record = create_todo_record("Finish report", remind_at=run_at)
    update_todo_record(record["id"], completed=True)
    items = list_entity_reminders()
    assert not any(i.get("entity_id") == record["id"] and i["entity_type"] == "task" for i in items)


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
    items = list_entity_reminders()
    assert any(i["entity_type"] == "task" for i in items)
