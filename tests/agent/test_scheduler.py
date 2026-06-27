from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from infra.scheduler import list_pending_jobs, schedule_reminder, shutdown_scheduler


@pytest.fixture(autouse=True)
def cleanup_scheduler():
    yield
    shutdown_scheduler()


def test_schedule_reminder(tmp_path, monkeypatch):
    monkeypatch.setattr("infra.scheduler._get_db", lambda: tmp_path / "scheduler.db")
    run_at = datetime.now(timezone.utc) + timedelta(seconds=60)
    result = schedule_reminder("job-1", "Test", "Reminder body", run_at)
    assert "Scheduled reminder" in result
    jobs = list_pending_jobs()
    assert any(j["id"] == "job-1" for j in jobs)
