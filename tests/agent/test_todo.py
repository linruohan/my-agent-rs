from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

AGENT_SRC = Path(__file__).resolve().parents[1] / "agent" / "src"
if str(AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(AGENT_SRC))


def test_create_and_list_todos(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        monkeypatch.setattr("tools.business.todo.DB_PATH", data_dir / "todos.db")
        monkeypatch.setattr("infra.config.get_data_dir", lambda: data_dir)

        from tools.business.todo import create_todo_record, list_todo_records

        record = create_todo_record("Buy milk", due_date="2026-06-28", priority="high")
        assert record["id"] == 1
        assert record["title"] == "Buy milk"

        todos = list_todo_records()
        assert len(todos) == 1
        assert todos[0]["title"] == "Buy milk"
        assert todos[0]["priority"] == "high"


def test_todo_tools_invoke(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        monkeypatch.setattr("tools.business.todo.DB_PATH", data_dir / "todos.db")

        from tools.business.todo import create_todo_tools

        tools = {t.name: t for t in create_todo_tools()}
        result = tools["create_todo"].invoke({"title": "Write tests"})
        assert "Write tests" in result

        list_result = tools["list_todos"].invoke({"include_completed": False})
        assert "Write tests" in list_result
