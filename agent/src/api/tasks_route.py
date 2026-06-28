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
    section_id: int | None = None
    description: str = ""
    remind_at: str = ""
    tags: list[str] = []


class ReminderBody(BaseModel):
    remind_at: str = ""


class TodoPatchBody(BaseModel):
    completed: bool | None = None
    title: str | None = None
    priority: str | None = None
    section_id: int | None = None
    due_date: str | None = None
    description: str | None = None
    project_id: int | None = None
    remind_at: str | None = None
    tags: list[str] | None = None
    clear_reminder: bool | None = None


class ProjectCreateBody(BaseModel):
    name: str
    description: str = ""
    status: str = "active"
    start_at: str = ""
    end_at: str = ""
    due_date: str = ""
    owner: str = ""
    remind_at: str = ""


class ProjectPatchBody(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    start_at: str | None = None
    end_at: str | None = None
    due_date: str | None = None
    owner: str | None = None
    remind_at: str | None = None


class SectionCreateBody(BaseModel):
    name: str
    start_at: str = ""
    end_at: str = ""
    owner: str = ""
    goals: str = ""
    status: str = "active"


class SectionPatchBody(BaseModel):
    name: str | None = None
    start_at: str | None = None
    end_at: str | None = None
    owner: str | None = None
    goals: str | None = None
    status: str | None = None


class SectionSummaryBody(BaseModel):
    summary_date: str
    progress: str = ""
    risks: str = ""
    challenges: str = ""
    notes: str = ""


class ProjectDocBody(BaseModel):
    title: str
    file_path: str = ""
    note: str = ""
    auto_ingest: bool = True


def _enrich_project(project: dict[str, Any]) -> dict[str, Any]:
    from tools.business.project import list_project_docs
    from tools.business.todo import get_todo_stats_for_project
    from tools.project.stats import task_stats_for_project

    pid = project["id"]
    project["stats"] = get_todo_stats_for_project(pid)
    project["doc_count"] = len(list_project_docs(pid))
    return project


def _enrich_section(section: dict[str, Any]) -> dict[str, Any]:
    from tools.business.todo import get_todo_stats_for_section

    section["stats"] = get_todo_stats_for_section(section["id"])
    return section


@router.get("/inbox")
def get_inbox_api() -> dict[str, Any]:
    from tools.business.project import ensure_inbox_project
    from tools.business.todo import get_todo_stats_for_project, list_todo_records

    inbox = ensure_inbox_project()
    inbox["stats"] = get_todo_stats_for_project(inbox["id"])
    inbox["todos"] = list_todo_records(
        include_completed=True, project_id=inbox["id"], inbox_only=True
    )
    return inbox


@router.get("/reminders")
def list_reminders_api() -> dict[str, Any]:
    from tools.business.reminders import list_entity_reminders

    return {"reminders": list_entity_reminders()}


@router.get("/snapshot")
def tasks_snapshot_api(
    project_id: int | None = None,
    section_id: int | None = None,
    include_completed: bool = True,
    sort_by: str = "priority",
    status: str = "",
) -> dict[str, Any]:
    from tools.business.project import ensure_inbox_project, list_project_records, list_section_records
    from tools.business.reminders import list_entity_reminders
    from tools.business.todo import list_todo_records

    projects = [_enrich_project(p) for p in list_project_records(status, include_inbox=True)]
    inbox = ensure_inbox_project()
    sections: list[dict[str, Any]] = []
    if project_id is not None:
        sections = [_enrich_section(s) for s in list_section_records(project_id)]

    return {
        "inbox": inbox,
        "projects": projects,
        "sections": sections,
        "todos": list_todo_records(
            include_completed,
            project_id,
            section_id,
            inbox_only=project_id == inbox["id"] and section_id is None,
            sort_by=sort_by,
        ),
        "reminders": list_entity_reminders(),
    }


@router.get("/projects")
def list_projects_api(status: str = "", include_inbox: bool = False) -> dict[str, Any]:
    from tools.business.project import list_project_records

    projects = [_enrich_project(p) for p in list_project_records(status, include_inbox=include_inbox)]
    return {"projects": projects}


@router.get("/projects/{project_id}")
def get_project_api(project_id: int) -> dict[str, Any]:
    from tools.business.project import get_project_record, list_project_docs, list_section_records
    from tools.business.todo import list_todo_records

    project = get_project_record(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project = _enrich_project(project)
    project["sections"] = [_enrich_section(s) for s in list_section_records(project_id)]
    project["docs"] = list_project_docs(project_id)
    project["todos"] = list_todo_records(include_completed=True, project_id=project_id)
    return project


@router.post("/projects")
def create_project_api(body: ProjectCreateBody) -> dict[str, Any]:
    from tools.business.project import create_project_record

    record = create_project_record(
        body.name,
        body.description,
        body.status,
        due_date=body.due_date or body.end_at,
        remind_at=body.remind_at,
        start_at=body.start_at,
        end_at=body.end_at or body.due_date,
        owner=body.owner,
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
        start_at=body.start_at,
        end_at=body.end_at or body.due_date,
        due_date=body.due_date or body.end_at,
        owner=body.owner,
        remind_at=body.remind_at,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"ok": True, "project": updated}


@router.get("/projects/{project_id}/sections")
def list_sections_api(project_id: int, status: str = "") -> dict[str, Any]:
    from tools.business.project import get_project_record, list_section_records

    if not get_project_record(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    sections = [_enrich_section(s) for s in list_section_records(project_id, status)]
    return {"sections": sections}


@router.post("/projects/{project_id}/sections")
def create_section_api(project_id: int, body: SectionCreateBody) -> dict[str, Any]:
    from tools.business.project import create_section_record, get_project_record

    if not get_project_record(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        record = create_section_record(
            project_id,
            body.name,
            body.start_at,
            body.end_at,
            body.owner,
            body.goals,
            body.status,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "section": _enrich_section(record)}


@router.get("/sections/{section_id}")
def get_section_api(section_id: int) -> dict[str, Any]:
    from tools.business.project import get_section_record, list_section_summary_records
    from tools.business.todo import list_todo_records

    section = get_section_record(section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    section = _enrich_section(section)
    section["summaries"] = list_section_summary_records(section_id)
    section["todos"] = list_todo_records(include_completed=True, section_id=section_id)
    return section


@router.patch("/sections/{section_id}")
def patch_section_api(section_id: int, body: SectionPatchBody) -> dict[str, Any]:
    from tools.business.project import update_section_record

    try:
        updated = update_section_record(
            section_id,
            name=body.name,
            start_at=body.start_at,
            end_at=body.end_at,
            owner=body.owner,
            goals=body.goals,
            status=body.status,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not updated:
        raise HTTPException(status_code=404, detail="Section not found")
    return {"ok": True, "section": _enrich_section(updated)}


@router.get("/sections/{section_id}/summaries")
def list_section_summaries_api(section_id: int) -> dict[str, Any]:
    from tools.business.project import get_section_record, list_section_summary_records

    if not get_section_record(section_id):
        raise HTTPException(status_code=404, detail="Section not found")
    return {"summaries": list_section_summary_records(section_id)}


@router.post("/sections/{section_id}/summaries")
def upsert_section_summary_api(section_id: int, body: SectionSummaryBody) -> dict[str, Any]:
    from tools.business.project import get_section_record, upsert_section_summary_record

    if not get_section_record(section_id):
        raise HTTPException(status_code=404, detail="Section not found")
    try:
        record = upsert_section_summary_record(
            section_id,
            body.summary_date,
            body.progress,
            body.risks,
            body.challenges,
            body.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "summary": record}


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
    section_id: int | None = None,
    inbox_only: bool = False,
    include_completed: bool = False,
    sort_by: str = "priority",
) -> dict[str, Any]:
    from tools.business.todo import list_todo_records

    todos = list_todo_records(
        include_completed, project_id, section_id, inbox_only, sort_by
    )
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
            body.section_id,
            body.description,
            body.remind_at,
            tags=body.tags,
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
        section_id=body.section_id,
        due_date=body.due_date,
        description=body.description,
        project_id=body.project_id,
        remind_at=body.remind_at,
        tags=body.tags,
        clear_reminder=bool(body.clear_reminder),
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
