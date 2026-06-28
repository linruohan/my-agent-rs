from __future__ import annotations

import sys
import tempfile
from pathlib import Path

AGENT_SRC = Path(__file__).resolve().parents[1] / "agent" / "src"
if str(AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(AGENT_SRC))


def _patch_data_dirs(monkeypatch, data_dir: Path) -> None:
    from infra.scheduler import shutdown_scheduler

    monkeypatch.setenv("AGENT_DATA_DIR", str(data_dir))
    monkeypatch.setattr("infra.scheduler._get_db", lambda: data_dir / "scheduler.db")
    monkeypatch.setattr("tools.business.reminders.schedule_project_reminder", lambda *_a, **_k: "")
    shutdown_scheduler()


def _cleanup_data_dirs() -> None:
    from infra.scheduler import shutdown_scheduler

    shutdown_scheduler()


def test_set_project_reminder_tool(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        _patch_data_dirs(monkeypatch, data_dir)
        try:
            from tools.project.tools import set_project_reminder
            from tools.business.project import create_project_record

            project = create_project_record("Reminder Test")
            pid = project["id"]
            result = set_project_reminder.invoke(
                {"project_id": pid, "remind_at": "2099-01-01T09:00:00"}
            )
            assert "设置提醒" in result
            cleared = set_project_reminder.invoke({"project_id": pid, "remind_at": ""})
            assert "取消" in cleared
        finally:
            _cleanup_data_dirs()


def test_project_lifecycle(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        _patch_data_dirs(monkeypatch, data_dir)
        try:
            from tools.business.project import (
                add_project_doc_record,
                create_project_record,
                get_project_record,
                list_project_records,
                update_project_record,
            )
            from tools.business.todo import create_todo_record, get_todo_stats_for_project

            project = create_project_record("Agent MVP", description="Phase 2", status="planning")
            assert project["id"] == 1

            updated = update_project_record(project["id"], status="active")
            assert updated and updated["status"] == "active"

            create_todo_record("Task A", project_id=project["id"])
            create_todo_record("Task B", project_id=project["id"], priority="high")

            stats = get_todo_stats_for_project(project["id"])
            assert stats["total"] == 2
            assert stats["by_priority"]["high"] == 1

            doc = add_project_doc_record(project["id"], "Spec", file_path="spec.md", auto_ingest=False)
            assert doc and doc["title"] == "Spec"

            active = list_project_records()
            assert len(active) == 1
            assert get_project_record(99) is None
        finally:
            _cleanup_data_dirs()


def test_project_doc_rag_ingest(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    workspace = data_dir / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("AGENT_DATA_DIR", str(data_dir))
    monkeypatch.setattr("infra.scheduler._get_db", lambda: data_dir / "scheduler.db")
    monkeypatch.setattr("infra.config.get_workspace_dir", lambda: workspace)
    _patch_data_dirs(monkeypatch, data_dir)
    try:
        doc_file = workspace / "spec.md"
        doc_file.write_text("# Spec\nProject requirements here.", encoding="utf-8")

        from tools.business.project import add_project_doc_record, create_project_record

        project = create_project_record("RAG Test")
        doc = add_project_doc_record(
            project["id"],
            "Spec",
            file_path="spec.md",
            note="inline note",
        )
        assert doc
        assert doc.get("rag_ingest")
        assert "RAG" in doc["rag_ingest"]

        from memory.rag import RagStore

        rag = RagStore()
        sources = rag.list_sources()
        assert any("project-" in s for s in sources)
    finally:
        _cleanup_data_dirs()


def test_project_tools_invoke(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        _patch_data_dirs(monkeypatch, data_dir)
        try:
            from tools.business.project import create_project_tools
            from tools.business.todo import create_todo_record, get_todo_stats_for_project

            project_tools = {t.name: t for t in create_project_tools()}

            created = project_tools["create_project"].invoke(
                {"name": "Sidecar", "status": "active"}
            )
            assert "Sidecar" in created

            create_todo_record("Build", project_id=1)
            stats = get_todo_stats_for_project(1)
            assert stats["total"] == 1
            status = project_tools["get_project_status"].invoke({"project_id": 1})
            assert "总任务" in status
            assert "0/1" in status
        finally:
            _cleanup_data_dirs()
