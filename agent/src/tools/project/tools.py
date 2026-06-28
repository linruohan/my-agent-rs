"""LangChain 工具：项目 / Section / 每日总结。"""

from __future__ import annotations

from langchain_core.tools import tool

from tools.project.stats import task_stats_for_project, task_stats_for_section
from tools.project.store import ProjectStore, project_to_dict, section_to_dict, summary_to_dict


def _store() -> ProjectStore:
    return ProjectStore()


@tool
def create_project(
    name: str,
    description: str = "",
    status: str = "active",
    start_at: str = "",
    end_at: str = "",
    owner: str = "",
) -> str:
    """创建周期型项目（含起止时间与负责人）。"""
    try:
        row = _store().add_project(
            name,
            description=description,
            status=status,
            start_at=start_at or None,
            end_at=end_at or None,
            owner=owner or None,
        )
    except ValueError as exc:
        return str(exc)
    return f"已创建项目 #{row.id}: {row.name} [{row.status}]"


@tool
def list_projects(status: str = "") -> str:
    """列出项目（不含 Inbox）。可选状态：planning/active/on_hold/completed/archived。"""
    rows = _store().list_projects(status, include_inbox=False)
    if not rows:
        return "暂无项目。"
    lines = []
    for p in rows:
        line = f"#{p.id} [{p.status}] {p.name}"
        if p.start_at or p.end_at:
            line += f" ({p.start_at or '?'} ~ {p.end_at or '?'})"
        if p.owner:
            line += f" @{p.owner}"
        if p.description:
            line += f" — {p.description[:60]}"
        lines.append(line)
    return "\n".join(lines)


@tool
def update_project(
    project_id: int,
    name: str = "",
    description: str = "",
    status: str = "",
    start_at: str = "",
    end_at: str = "",
    owner: str = "",
) -> str:
    """更新项目元数据或生命周期状态。"""
    try:
        updated = _store().update_project(
            project_id,
            name=name or None,
            description=description or None,
            status=status or None,
            start_at=start_at or None,
            end_at=end_at or None,
            owner=owner or None,
        )
    except ValueError as exc:
        return str(exc)
    if not updated:
        return f"项目 #{project_id} 不存在。"
    return f"已更新项目 #{project_id}: {updated.name} [{updated.status}]"


@tool
def create_section(
    project_id: int,
    name: str,
    start_at: str = "",
    end_at: str = "",
    owner: str = "",
    goals: str = "",
) -> str:
    """在项目中创建 Section（里程碑/版本，如 R13B100）。"""
    try:
        row = _store().add_section(
            project_id,
            name,
            start_at=start_at or None,
            end_at=end_at or None,
            owner=owner or None,
            goals=goals,
        )
    except ValueError as exc:
        return str(exc)
    return f"已创建 Section #{row.id}: {row.name}（项目 #{project_id}）"


@tool
def list_sections(project_id: int, status: str = "") -> str:
    """列出项目下所有 Section 及任务进度。"""
    store = _store()
    if not store.get_project(project_id):
        return f"项目 #{project_id} 不存在。"
    sections = store.list_sections(project_id, status)
    if not sections:
        return f"项目 #{project_id} 暂无 Section。"
    lines = [f"项目 #{project_id} Sections："]
    for s in sections:
        stats = task_stats_for_section(s.id)
        pct = int(stats["completed"] / stats["total"] * 100) if stats["total"] else 0
        line = f"  #{s.id} {s.name} [{s.status}] {stats['completed']}/{stats['total']} ({pct}%)"
        if s.owner:
            line += f" @{s.owner}"
        if s.goals:
            line += f" 目标:{s.goals[:40]}"
        lines.append(line)
    return "\n".join(lines)


@tool
def add_section_daily_summary(
    section_id: int,
    summary_date: str,
    progress: str = "",
    risks: str = "",
    challenges: str = "",
    notes: str = "",
) -> str:
    """为 Section 添加或更新某日总结（进度、风险、挑战）。"""
    try:
        row = _store().upsert_daily_summary(
            section_id,
            summary_date,
            progress=progress,
            risks=risks,
            challenges=challenges,
            notes=notes,
        )
    except ValueError as exc:
        return str(exc)
    return f"已保存 Section #{section_id} {row.summary_date} 的每日总结"


@tool
def list_section_daily_summaries(section_id: int) -> str:
    """列出 Section 的全部每日总结。"""
    store = _store()
    if not store.get_section(section_id):
        return f"Section #{section_id} 不存在。"
    rows = store.list_daily_summaries(section_id)
    if not rows:
        return f"Section #{section_id} 暂无每日总结。"
    lines = [f"Section #{section_id} 每日总结："]
    for r in rows:
        parts = [f"[{r.summary_date}]"]
        if r.progress:
            parts.append(f"进度:{r.progress[:60]}")
        if r.risks:
            parts.append(f"风险:{r.risks[:40]}")
        if r.challenges:
            parts.append(f"挑战:{r.challenges[:40]}")
        lines.append(" ".join(parts))
    return "\n".join(lines)


@tool
def get_project_status(project_id: int) -> str:
    """查看项目进度：各 Section 与任务统计。"""
    store = _store()
    project = store.get_project(project_id)
    if not project:
        return f"项目 #{project_id} 不存在。"
    stats = task_stats_for_project(project_id)
    total = stats["total"]
    done = stats["completed"]
    pct = int(done / total * 100) if total else 0
    lines = [
        f"项目 #{project_id}: {project.name} [{project.status}]",
        f"总任务: {done}/{total} ({pct}%)",
    ]
    sections = store.list_sections(project_id)
    if sections:
        lines.append("Sections:")
        for s in sections:
            sstats = task_stats_for_section(s.id)
            spct = int(sstats["completed"] / sstats["total"] * 100) if sstats["total"] else 0
            lines.append(
                f"  #{s.id} {s.name}: {sstats['completed']}/{sstats['total']} ({spct}%)"
            )
    docs = store.list_docs(project_id)
    if docs:
        lines.append(f"文档 ({len(docs)}):")
        for d in docs[:5]:
            lines.append(f"  - #{d['id']} {d['title']}")
    return "\n".join(lines)


@tool
def add_project_document(
    project_id: int,
    title: str,
    file_path: str = "",
    note: str = "",
) -> str:
    """为项目附加文档引用或备注（可选 RAG 索引）。"""
    from tools.business.project import add_project_doc_record

    doc = add_project_doc_record(project_id, title, file_path, note)
    if not doc:
        return f"项目 #{project_id} 不存在。"
    msg = f"已为项目 #{project_id} 添加文档 #{doc['id']}: {title}"
    if doc.get("rag_ingest"):
        msg += f"。{doc['rag_ingest']}"
    return msg


PROJECT_TOOLS = [
    create_project,
    list_projects,
    update_project,
    create_section,
    list_sections,
    add_section_daily_summary,
    list_section_daily_summaries,
    get_project_status,
    add_project_document,
]
