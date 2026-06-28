from __future__ import annotations

import sys
import tempfile
from pathlib import Path

AGENT_SRC = Path(__file__).resolve().parents[1] / "agent" / "src"
if str(AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(AGENT_SRC))


def test_handle_task_command_add_and_list(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("AGENT_DATA_DIR", tmp)
        from tools.task.store import TaskStore, handle_task_command

        store = TaskStore()
        result = handle_task_command("add 写报告 @due-6.28", store)
        assert "已添加任务" in result
        listed = handle_task_command("list", store)
        assert "写报告" in listed


def test_search_tasks_tool(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("AGENT_DATA_DIR", tmp)
        from tools.task.tools import add_task, search_tasks

        add_task.invoke({"title": "Rust sidecar", "content": "FastAPI bridge"})
        found = search_tasks.invoke({"keyword": "sidecar"})
        assert "sidecar" in found
        assert "FastAPI bridge" in found
