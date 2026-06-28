from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TodoCreateBody(BaseModel):
    title: str
    due_date: str = ""
    priority: str = "normal"
    project_id: int | None = None
    description: str = ""
    remind_at: str = ""


class ReminderBody(BaseModel):
    remind_at: str = ""


class TodoPatchBody(BaseModel):
    completed: bool | None = None
    title: str | None = None
    priority: str | None = None


class ProjectCreateBody(BaseModel):
    name: str
    description: str = ""
    status: str = "active"
    due_date: str = ""
    remind_at: str = ""


class ProjectPatchBody(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    due_date: str | None = None
    remind_at: str | None = None


class ProjectDocBody(BaseModel):
    title: str
    file_path: str = ""
    note: str = ""
    auto_ingest: bool = True


@router.get("/reminders")
def list_reminders_api() -> dict[str, Any]:
    from tools.business.reminders import list_entity_reminders

    return {"reminders": list_entity_reminders()}


@router.get("/projects")
def list_projects_api(status: str = "") -> dict[str, Any]:
    from tools.business.project import list_project_docs, list_project_records
    from tools.business.todo import get_todo_stats_for_project

    projects = list_project_records(status)
    for project in projects:
        project["stats"] = get_todo_stats_for_project(project["id"])
        project["doc_count"] = len(list_project_docs(project["id"]))
    return {"projects": projects}


@router.get("/projects/{project_id}")
def get_project_api(project_id: int) -> dict[str, Any]:
    from tools.business.project import get_project_record, list_project_docs
    from tools.business.todo import get_todo_stats_for_project, list_todo_records

    project = get_project_record(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project["stats"] = get_todo_stats_for_project(project_id)
    project["docs"] = list_project_docs(project_id)
    project["todos"] = list_todo_records(include_completed=True, project_id=project_id)
    return project


@router.post("/projects")
def create_project_api(body: ProjectCreateBody) -> dict[str, Any]:
    from tools.business.project import create_project_record

    record = create_project_record(
        body.name, body.description, body.status, body.due_date, body.remind_at
    )
    return {"ok": True, "project": record}


@router.patch("/projects/{project_id}")
def patch_project_api(project_id: int, body: ProjectPatchBody) -> dict[str, Any]:
    from tools.business.project import update_project_record

    updated = update_project_record(
        project_id,
        name=body.name,
        description=body.description,
        status=body.status,
        due_date=body.due_date,
        remind_at=body.remind_at,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"ok": True, "project": updated}


@router.post("/projects/{project_id}/docs")
def add_project_doc_api(project_id: int, body: ProjectDocBody) -> dict[str, Any]:
    from tools.business.project import add_project_doc_record

    doc = add_project_doc_record(
        project_id,
        body.title,
        body.file_path,
        body.note,
        auto_ingest=body.auto_ingest,
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"ok": True, "doc": doc}


@router.get("/todos")
def list_todos_api(
    project_id: int | None = None,
    include_completed: bool = False,
    sort_by: str = "priority",
) -> dict[str, Any]:
    from tools.business.todo import list_todo_records

    todos = list_todo_records(include_completed, project_id, sort_by)
    return {"todos": todos}


@router.post("/todos")
def create_todo_api(body: TodoCreateBody) -> dict[str, Any]:
    from tools.business.todo import create_todo_record

    try:
        record = create_todo_record(
            body.title,
            body.due_date,
            body.priority,
            body.project_id,
            body.description,
            body.remind_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "todo": record}


@router.patch("/todos/{todo_id}")
def patch_todo_api(todo_id: int, body: TodoPatchBody) -> dict[str, Any]:
    from tools.business.todo import update_todo_record

    updated = update_todo_record(
        todo_id,
        title=body.title,
        priority=body.priority,
        completed=body.completed,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Todo not found")
    return {"ok": True, "todo": updated}


@router.delete("/todos/{todo_id}")
def delete_todo_api(todo_id: int) -> dict[str, Any]:
    from tools.business.todo import delete_todo_record, get_todo_record

    todo = get_todo_record(todo_id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    delete_todo_record(todo_id)
    return {"ok": True, "deleted_id": todo_id}


@router.put("/todos/{todo_id}/reminder")
def set_todo_reminder_api(todo_id: int, body: ReminderBody) -> dict[str, Any]:
    from tools.business.todo import update_todo_record

    if body.remind_at.strip():
        updated = update_todo_record(todo_id, remind_at=body.remind_at.strip())
    else:
        updated = update_todo_record(todo_id, clear_reminder=True)
    if not updated:
        raise HTTPException(status_code=404, detail="Todo not found")
    return {"ok": True, "todo": updated}


@router.put("/projects/{project_id}/reminder")
def set_project_reminder_api(project_id: int, body: ReminderBody) -> dict[str, Any]:
    from tools.business.project import update_project_record

    if body.remind_at.strip():
        updated = update_project_record(project_id, remind_at=body.remind_at.strip())
    else:
        updated = update_project_record(project_id, clear_reminder=True)
    if not updated:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"ok": True, "project": updated}
