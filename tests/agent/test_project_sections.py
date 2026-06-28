from __future__ import annotations

import sys
import tempfile
from pathlib import Path

AGENT_SRC = Path(__file__).resolve().parents[1] / "agent" / "src"
if str(AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(AGENT_SRC))


def test_section_and_inbox_tasks(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("AGENT_DATA_DIR", tmp)
        monkeypatch.setattr(
            "tools.business.reminders.schedule_project_reminder", lambda *_a, **_k: ""
        )

        from tools.business.project import (
            create_project_record,
            create_section_record,
            ensure_inbox_project,
        )
        from tools.business.todo import create_todo_record, list_todo_records

        inbox = ensure_inbox_project()
        assert inbox["is_inbox"]

        project = create_project_record("Release 2026")
        section = create_section_record(
            project["id"],
            "R13B100",
            goals="版本发布",
            owner="Alice",
        )

        create_todo_record("Build", project_id=project["id"], section_id=section["id"])
        create_todo_record("Quick fix", project_id=inbox["id"])

        section_tasks = list_todo_records(include_completed=True, section_id=section["id"])
        assert len(section_tasks) == 1
        assert section_tasks[0]["title"] == "Build"

        inbox_tasks = list_todo_records(
            include_completed=True, project_id=inbox["id"], inbox_only=True
        )
        assert len(inbox_tasks) == 1
        assert inbox_tasks[0]["title"] == "Quick fix"


def test_section_daily_summary(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("AGENT_DATA_DIR", tmp)
        monkeypatch.setattr(
            "tools.business.reminders.schedule_project_reminder", lambda *_a, **_k: ""
        )

        from tools.business.project import (
            create_project_record,
            create_section_record,
            list_section_summary_records,
            upsert_section_summary_record,
        )

        project = create_project_record("Sprint")
        section = create_section_record(project["id"], "R15C10")
        upsert_section_summary_record(
            section["id"],
            "2026-06-28",
            progress="完成 80%",
            risks="依赖延迟",
            challenges="测试环境不稳定",
        )
        rows = list_section_summary_records(section["id"])
        assert len(rows) == 1
        assert rows[0]["progress"] == "完成 80%"
        assert rows[0]["risks"] == "依赖延迟"
