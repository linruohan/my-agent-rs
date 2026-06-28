from __future__ import annotations

import pytest
from starlette.testclient import TestClient


@pytest.fixture
def tasks_client(monkeypatch, tmp_path):
    from pathlib import Path
    from unittest.mock import MagicMock

    config_dir = Path(__file__).resolve().parents[2] / "agent" / "config"
    monkeypatch.setenv("AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AGENT_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("tools.business.reminders.schedule_project_reminder", lambda *_a, **_k: "")

    from langgraph.checkpoint.memory import MemorySaver

    monkeypatch.setattr("agent.graph.get_checkpointer", lambda: MemorySaver())
    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    monkeypatch.setattr(
        "agent.graph.create_llm_with_fallback",
        lambda *a, **k: (mock_llm, "mock"),
    )
    monkeypatch.setattr("agent.graph._provider_available", lambda _name: True)

    from main import build_app

    with TestClient(build_app(port=8765)) as client:
        yield client


def test_tasks_api_flow(tasks_client):
    proj = tasks_client.post(
        "/tasks/projects",
        json={"name": "API Test", "status": "active"},
    )
    assert proj.status_code == 200
    project_id = proj.json()["project"]["id"]

    todo = tasks_client.post(
        "/tasks/todos",
        json={"title": "From API", "project_id": project_id, "priority": "high"},
    )
    assert todo.status_code == 200
    todo_id = todo.json()["todo"]["id"]

    listed = tasks_client.get(f"/tasks/todos?project_id={project_id}")
    assert len(listed.json()["todos"]) == 1

    patched = tasks_client.patch(
        f"/tasks/todos/{todo_id}",
        json={"completed": True},
    )
    assert patched.json()["todo"]["completed"] is True

    detail = tasks_client.get(f"/tasks/projects/{project_id}")
    assert detail.status_code == 200
    assert detail.json()["stats"]["completed"] == 1

    projects = tasks_client.get("/tasks/projects")
    assert any(p["id"] == project_id for p in projects.json()["projects"])

    doc = tasks_client.post(
        f"/tasks/projects/{project_id}/docs",
        json={"title": "README", "note": "project notes"},
    )
    assert doc.status_code == 200

    patched_proj = tasks_client.patch(
        f"/tasks/projects/{project_id}",
        json={"status": "completed"},
    )
    assert patched_proj.json()["project"]["status"] == "completed"

    todo2 = tasks_client.post(
        "/tasks/todos",
        json={
            "title": "Reminder test",
            "remind_at": "2099-06-01T09:00:00+00:00",
        },
    )
    tid2 = todo2.json()["todo"]["id"]
    rem = tasks_client.put(
        f"/tasks/todos/{tid2}/reminder",
        json={"remind_at": "2099-07-01T10:00:00+00:00"},
    )
    assert rem.status_code == 200

    pending = tasks_client.get("/tasks/reminders")
    assert pending.status_code == 200
    assert any(r["entity_type"] in ("task", "todo") for r in pending.json()["reminders"])

    deleted = tasks_client.delete(f"/tasks/todos/{todo_id}")
    assert deleted.status_code == 200


def test_delete_project_and_section(tasks_client):
    proj = tasks_client.post(
        "/tasks/projects",
        json={"name": "To Delete", "status": "active"},
    )
    project_id = proj.json()["project"]["id"]

    sec = tasks_client.post(
        f"/tasks/projects/{project_id}/sections",
        json={"name": "Phase 1", "goals": "test"},
    )
    section_id = sec.json()["section"]["id"]

    todo = tasks_client.post(
        "/tasks/todos",
        json={"title": "In section", "project_id": project_id, "section_id": section_id},
    )
    todo_id = todo.json()["todo"]["id"]

    del_sec = tasks_client.delete(f"/tasks/sections/{section_id}")
    assert del_sec.status_code == 200

    patched = tasks_client.patch(f"/tasks/todos/{todo_id}", json={})
    assert patched.json()["todo"]["section_id"] is None

    del_proj = tasks_client.delete(f"/tasks/projects/{project_id}")
    assert del_proj.status_code == 200

    inbox = tasks_client.get("/tasks/inbox").json()
    inbox_id = inbox["id"]
    moved = tasks_client.get(f"/tasks/todos?project_id={inbox_id}").json()
    assert any(t["id"] == todo_id for t in moved["todos"])

    assert tasks_client.get(f"/tasks/projects/{project_id}").status_code == 404
    assert tasks_client.delete(f"/tasks/projects/{inbox_id}").status_code == 400


def test_tasks_snapshot(tasks_client):
    tasks_client.post("/tasks/projects", json={"name": "Snap", "status": "active"})
    tasks_client.post("/tasks/todos", json={"title": "Snap todo", "priority": "normal"})

    resp = tasks_client.get("/tasks/snapshot?include_completed=true")
    assert resp.status_code == 200
    data = resp.json()
    assert "projects" in data
    assert "todos" in data
    assert "reminders" in data
    assert len(data["projects"]) >= 1
    assert len(data["todos"]) >= 1
