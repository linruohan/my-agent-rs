"""Legacy project API facade — backed by tools.project (project.db)."""

from __future__ import annotations

from typing import Any

from tools.project.stats import task_stats_for_project
from tools.project.store import ProjectStore, project_to_dict, section_to_dict, summary_to_dict


def _store() -> ProjectStore:
    return ProjectStore()


def create_project_record(
    name: str,
    description: str = "",
    status: str = "active",
    due_date: str = "",
    remind_at: str = "",
    start_at: str = "",
    end_at: str = "",
    owner: str = "",
) -> dict[str, Any]:
    row = _store().add_project(
        name,
        description=description,
        status=status,
        start_at=start_at or None,
        end_at=end_at or due_date or None,
        owner=owner or None,
        remind_at=remind_at or None,
    )
    record = project_to_dict(row)
    from tools.business.reminders import schedule_project_reminder

    schedule_project_reminder(record)
    return record


def list_project_records(status: str = "", *, include_inbox: bool = False) -> list[dict[str, Any]]:
    return [project_to_dict(r) for r in _store().list_projects(status, include_inbox=include_inbox)]


def get_project_record(project_id: int) -> dict[str, Any] | None:
    row = _store().get_project(project_id)
    return project_to_dict(row) if row else None


def update_project_record(
    project_id: int,
    name: str | None = None,
    description: str | None = None,
    status: str | None = None,
    due_date: str | None = None,
    remind_at: str | None = None,
    clear_reminder: bool = False,
    start_at: str | None = None,
    end_at: str | None = None,
    owner: str | None = None,
) -> dict[str, Any] | None:
    end_val = end_at if end_at is not None else due_date
    updated = _store().update_project(
        project_id,
        name=name,
        description=description,
        status=status,
        start_at=start_at,
        end_at=end_val,
        owner=owner,
        remind_at=remind_at,
        clear_reminder=clear_reminder,
    )
    if not updated:
        return None
    record = project_to_dict(updated)
    from tools.business.reminders import schedule_project_reminder

    schedule_project_reminder(record)
    return record


def create_section_record(
    project_id: int,
    name: str,
    start_at: str = "",
    end_at: str = "",
    owner: str = "",
    goals: str = "",
    status: str = "active",
) -> dict[str, Any]:
    row = _store().add_section(
        project_id,
        name,
        start_at=start_at or None,
        end_at=end_at or None,
        owner=owner or None,
        goals=goals,
        status=status,
    )
    return section_to_dict(row)


def list_section_records(project_id: int, status: str = "") -> list[dict[str, Any]]:
    return [section_to_dict(r) for r in _store().list_sections(project_id, status)]


def get_section_record(section_id: int) -> dict[str, Any] | None:
    row = _store().get_section(section_id)
    return section_to_dict(row) if row else None


def update_section_record(
    section_id: int,
    name: str | None = None,
    start_at: str | None = None,
    end_at: str | None = None,
    owner: str | None = None,
    goals: str | None = None,
    status: str | None = None,
) -> dict[str, Any] | None:
    row = _store().update_section(
        section_id,
        name=name,
        start_at=start_at,
        end_at=end_at,
        owner=owner,
        goals=goals,
        status=status,
    )
    return section_to_dict(row) if row else None


def upsert_section_summary_record(
    section_id: int,
    summary_date: str,
    progress: str = "",
    risks: str = "",
    challenges: str = "",
    notes: str = "",
) -> dict[str, Any]:
    row = _store().upsert_daily_summary(
        section_id,
        summary_date,
        progress=progress,
        risks=risks,
        challenges=challenges,
        notes=notes,
    )
    return summary_to_dict(row)


def list_section_summary_records(section_id: int) -> list[dict[str, Any]]:
    return [summary_to_dict(r) for r in _store().list_daily_summaries(section_id)]


def ensure_inbox_project() -> dict[str, Any]:
    return project_to_dict(_store().ensure_inbox())


def get_todo_stats_for_project(project_id: int) -> dict[str, Any]:
    return task_stats_for_project(project_id)


def _resolve_doc_path(path: str):
    from pathlib import Path

    from infra.config import resolve_workspace_path

    raw = (path or "").strip()
    if not raw:
        return None
    try:
        target = resolve_workspace_path(raw)
        if target.exists():
            return target
    except ValueError:
        pass
    direct = Path(raw)
    if direct.is_file():
        return direct
    return None


def _ingest_project_doc_to_rag(
    project_id: int,
    title: str,
    file_path: str = "",
    note: str = "",
) -> str:
    from memory.rag import SUPPORTED_EXTENSIONS, RagStore, _extract_file_text

    rag = RagStore()
    source_base = f"project-{project_id}/{title}"
    parts: list[str] = []

    target = _resolve_doc_path(file_path)
    if file_path.strip() and target is None:
        parts.append(f"文件不存在或不在工作区内，未索引: {file_path.strip()}")
    elif target is not None:
        if target.suffix.lower() not in SUPPORTED_EXTENSIONS:
            parts.append(f"不支持的文件类型: {target.suffix}")
        else:
            try:
                content = _extract_file_text(target)
                count = rag.ingest_text(content, source=source_base)
                if count:
                    parts.append(f"RAG 已索引文件 ({count} chunks)")
                else:
                    parts.append("RAG 跳过（内容未变化）")
            except Exception as e:
                parts.append(f"RAG 索引失败: {e}")

    text = (note or "").strip()
    if text:
        count = rag.ingest_text(text, source=f"{source_base}:note")
        if count:
            parts.append(f"RAG 已索引备注 ({count} chunks)")

    return "；".join(parts)


def add_project_doc_record(
    project_id: int,
    title: str,
    file_path: str = "",
    note: str = "",
    auto_ingest: bool = True,
) -> dict[str, Any] | None:
    doc = _store().add_doc(project_id, title, file_path, note)
    if not doc:
        return None
    if auto_ingest and (file_path.strip() or note.strip()):
        doc["rag_ingest"] = _ingest_project_doc_to_rag(project_id, title, file_path, note)
    return doc


def list_project_docs(project_id: int) -> list[dict[str, Any]]:
    return _store().list_docs(project_id)


def create_project_tools():
    from tools.project.tools import PROJECT_TOOLS

    return list(PROJECT_TOOLS)
