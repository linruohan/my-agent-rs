from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from apscheduler.schedulers.background import BackgroundScheduler
from loguru import logger

from infra.config import get_data_dir

_scheduler: BackgroundScheduler | None = None
_notify_callback: Callable[[str, str], None] | None = None


def _get_db() -> Path:
    return get_data_dir() / "scheduler.db"


def _init_db() -> None:
    db = _get_db()
    db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scheduled_jobs (
                id TEXT PRIMARY KEY,
                job_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                run_at TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def set_notify_callback(cb: Callable[[str, str], None]) -> None:
    global _notify_callback
    _notify_callback = cb


def _fire_reminder(title: str, message: str) -> None:
    logger.info("Reminder: {} - {}", title, message)
    if _notify_callback:
        _notify_callback(title, message)


def schedule_reminder(job_id: str, title: str, message: str, run_at: datetime) -> str:
    _init_db()
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(_get_db()) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO scheduled_jobs (id, job_type, payload, run_at, status, created_at)
            VALUES (?, 'reminder', ?, ?, 'pending', ?)
            """,
            (job_id, f"{title}|{message}", run_at.isoformat(), now),
        )
        conn.commit()

    sched = get_scheduler()
    sched.add_job(
        _fire_reminder,
        "date",
        run_date=run_at,
        id=job_id,
        args=[title, message],
        replace_existing=True,
    )
    return f"Scheduled reminder `{title}` at {run_at.isoformat()}"


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _init_db()
        _scheduler = BackgroundScheduler(timezone="UTC")
        _scheduler.start()
        logger.info("APScheduler started")
    return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def list_pending_jobs() -> list[dict[str, Any]]:
    _init_db()
    with sqlite3.connect(_get_db()) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, job_type, payload, run_at, status FROM scheduled_jobs WHERE status = 'pending'"
        ).fetchall()
    return [dict(r) for r in rows]
