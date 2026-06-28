""" /pro 斜杠命令：项目 / Section / 每日总结本地操作。"""

from __future__ import annotations

import re
from typing import Any

from tools.project.stats import task_stats_for_project, task_stats_for_section
from tools.project.store import INBOX_PROJECT_NAME, ProjectStore, ProjectRow, SectionRow
from tools.task.parse import parse_task_add_with_defaults, tokenize_task_text
from tools.task.store import (
    FLAT_PROJECT_TASK_HEADER,
    FLAT_PROJECT_TASK_SEP,
    SECTION_TASK_OVERVIEW_HEADER,
    SECTION_TASK_OVERVIEW_SEP,
    TaskStore,
    flat_project_task_row,
    format_task_table,
    section_task_overview_row,
)

_RE_OWNER = re.compile(r"^@\{([^}]+)\}$|^@owner-(.+)$", re.IGNORECASE)
_RE_START = re.compile(r"^@start-(.+)$", re.IGNORECASE)
_RE_END = re.compile(r"^@end-(.+)$", re.IGNORECASE)
_RE_STATUS = re.compile(r"^@status-(\w+)$", re.IGNORECASE)
_RE_RISK = re.compile(r"^@risk-(.+)$", re.IGNORECASE)
_RE_CHALLENGE = re.compile(r"^@challenge-(.+)$", re.IGNORECASE)
_RE_NOTE = re.compile(r"^@note-(.+)$", re.IGNORECASE)

_USAGE = (
    "用法：/pro list | add <项目名> [描述] [标记…] | mod <项目ID> [修改内容] | status <项目ID>\n"
    "      /pro sec add <项目ID> <Section名> [目标…] | sec task add <SectionID> <任务名> [标记…]\n"
    "      /pro sec list <项目ID> | sec mod <SectionID> … | sec summary <SectionID> <日期> [进度…] | sec summaries <SectionID>\n"
    "      /pro doc add <项目ID> <标题> [路径] | <项目ID> | <关键字>\n"
    "标记：@owner-姓名 @start-日期 @end-日期 @status-active @risk-… @challenge-… @note-…"
)


def _split_meta(text: str) -> tuple[list[str], dict[str, str]]:
    plain: list[str] = []
    meta: dict[str, str] = {}
    for token in tokenize_task_text(text):
        if m := _RE_OWNER.match(token):
            meta["owner"] = (m.group(1) or m.group(2) or "").strip()
        elif m := _RE_START.match(token):
            meta["start_at"] = m.group(1).strip()
        elif m := _RE_END.match(token):
            meta["end_at"] = m.group(1).strip()
        elif m := _RE_STATUS.match(token):
            meta["status"] = m.group(1).strip()
        elif m := _RE_RISK.match(token):
            meta["risk"] = m.group(1).strip()
        elif m := _RE_CHALLENGE.match(token):
            meta["challenge"] = m.group(1).strip()
        elif m := _RE_NOTE.match(token):
            meta["note"] = m.group(1).strip()
        else:
            plain.append(token)
    return plain, meta


def _format_project_line(p: ProjectRow, *, stats: dict[str, Any] | None = None) -> str:
    line = f"#{p.id} [{p.status}] {p.name}"
    if p.is_inbox:
        line += " (Inbox)"
    if p.start_at or p.end_at:
        line += f" ({p.start_at or '?'} ~ {p.end_at or '?'})"
    if p.owner:
        line += f" @{p.owner}"
    if stats and stats.get("total"):
        done, total = stats["completed"], stats["total"]
        pct = int(done / total * 100)
        line += f" 任务:{done}/{total}({pct}%)"
    if p.description:
        line += f" — {p.description[:60]}"
    return line


def _format_section_line(s: SectionRow, *, stats: dict[str, Any] | None = None) -> str:
    line = f"#{s.id} {s.name} [{s.status}]"
    if s.start_at or s.end_at:
        line += f" ({s.start_at or '?'} ~ {s.end_at or '?'})"
    if s.owner:
        line += f" @{s.owner}"
    if stats is not None:
        total = stats.get("total", 0)
        done = stats.get("completed", 0)
        pct = int(done / total * 100) if total else 0
        line += f" {done}/{total} ({pct}%)"
    if s.goals:
        line += f" 目标:{s.goals[:50]}"
    return line


def _escape_md_cell(text: str) -> str:
    return (text or "—").replace("|", "\\|").replace("\n", " ")


def format_projects_list(store: ProjectStore | None = None, *, status: str = "") -> str:
    """全部项目：扁平任务大表（项目 / Section / 任务各列）。"""
    pstore = store or ProjectStore()
    tstore = TaskStore()
    projects = pstore.list_projects(status, include_inbox=False)

    if not projects:
        return "暂无项目。可用 `/pro add <名称>` 创建。"

    table_rows: list[str] = []
    for p in projects:
        sections_map = {s.id: s for s in pstore.list_sections(p.id)}
        tasks = sorted(
            tstore.list_filtered(include_done=True, project_id=p.id),
            key=lambda r: (r.section_id or 0, r.id),
        )
        for task in tasks:
            sec = sections_map.get(task.section_id) if task.section_id else None
            table_rows.append(
                flat_project_task_row(
                    p.id,
                    p.name,
                    sec.id if sec else None,
                    sec.name if sec else None,
                    task,
                )
            )

    if not table_rows:
        return "暂无项目任务。"

    return "\n".join([FLAT_PROJECT_TASK_HEADER, FLAT_PROJECT_TASK_SEP, *table_rows])


def _cmd_list(store: ProjectStore, rest: str) -> str:
    status = ""
    plain, meta = _split_meta(rest)
    if meta.get("status"):
        status = meta["status"]
    elif plain:
        status = plain[0]
    return format_projects_list(store, status=status)


def _cmd_add(store: ProjectStore, rest: str) -> str:
    plain, meta = _split_meta(rest)
    if not plain:
        return "项目名不能为空。"
    name = plain[0]
    description = " ".join(plain[1:]).strip()
    try:
        row = store.add_project(
            name,
            description=description,
            status=meta.get("status", "active"),
            start_at=meta.get("start_at"),
            end_at=meta.get("end_at"),
            owner=meta.get("owner"),
        )
    except ValueError as exc:
        return str(exc)
    return f"已创建项目 #{row.id}：{row.name} [{row.status}]"


def _cmd_mod(store: ProjectStore, rest: str) -> str:
    if not rest:
        return "用法：/pro mod <项目ID> [名称/描述/标记…]"
    id_parts = rest.split(None, 1)
    if not id_parts[0].isdigit():
        return "项目 ID 须为数字。"
    pid = int(id_parts[0])
    mod_text = id_parts[1].strip() if len(id_parts) > 1 else ""
    if not mod_text:
        return f"用法：/pro mod {pid} <要修改的内容>"
    plain, meta = _split_meta(mod_text)
    kwargs: dict[str, Any] = {}
    if plain:
        kwargs["name"] = plain[0]
        if len(plain) > 1:
            kwargs["description"] = " ".join(plain[1:])
    if "owner" in meta:
        kwargs["owner"] = meta["owner"]
    if "start_at" in meta:
        kwargs["start_at"] = meta["start_at"]
    if "end_at" in meta:
        kwargs["end_at"] = meta["end_at"]
    if "status" in meta:
        kwargs["status"] = meta["status"]
    try:
        updated = store.update_project(pid, **kwargs)
    except ValueError as exc:
        return str(exc)
    if not updated:
        return f"项目 #{pid} 不存在。"
    return f"已更新项目 #{pid}：{updated.name} [{updated.status}]"


def _pct(stats: dict[str, Any]) -> int:
    total = int(stats.get("total") or 0)
    if not total:
        return 0
    return int(int(stats.get("completed") or 0) / total * 100)


def format_project_detail(project_id: int, store: ProjectStore | None = None) -> str:
    """项目详情：【无section】→ 各 Section 任务表 → 【项目总览】。"""
    pstore = store or ProjectStore()
    tstore = TaskStore()
    project = pstore.get_project(project_id)
    if not project:
        return f"项目 #{project_id} 不存在。"

    parts: list[str] = [
        f"【项目 #{project_id}】：{project.name} [{project.status}]",
        f"周期：{project.start_at or '—'} ~ {project.end_at or '—'} | 负责人：{project.owner or '—'}",
        "",
    ]

    if project.is_inbox:
        tasks = sorted(
            tstore.list_filtered(include_done=True, project_id=project_id, inbox_only=True),
            key=lambda r: r.id,
        )
        parts.append("【Inbox 任务】")
        parts.append(format_task_table(tasks) if tasks else "暂无任务。")
        return "\n".join(parts)

    parts.append("【无section】")
    orphan = sorted(
        tstore.list_filtered(include_done=True, project_id=project_id, inbox_only=True),
        key=lambda r: r.id,
    )
    parts.append(format_task_table(orphan) if orphan else "暂无未归属任务。")
    parts.append("")

    sections = sorted(pstore.list_sections(project_id), key=lambda s: s.id)
    for section in sections:
        parts.append(f"【section#{section.id}】：{section.name}")
        tasks = sorted(
            tstore.list_filtered(
                include_done=True, project_id=project_id, section_id=section.id
            ),
            key=lambda r: r.id,
        )
        parts.append(format_task_table(tasks) if tasks else "暂无任务。")
        parts.append("")

    parts.append("【项目总览】")
    if sections:
        parts.append("各 Section 进度：")
        for section in sections:
            ss = task_stats_for_section(section.id)
            parts.append(f"{section.name}: {ss['completed']}/{ss['total']} ({_pct(ss)}%)")

    overview_rows: list[str] = []
    for section in sections:
        tasks = sorted(
            tstore.list_filtered(
                include_done=True, project_id=project_id, section_id=section.id
            ),
            key=lambda r: r.id,
        )
        for task in tasks:
            overview_rows.append(section_task_overview_row(section.id, section.name, task))

    if overview_rows:
        parts.append("")
        parts.extend([SECTION_TASK_OVERVIEW_HEADER, SECTION_TASK_OVERVIEW_SEP, *overview_rows])

    progress_lines: list[str] = []
    risk_lines: list[str] = []
    challenge_lines: list[str] = []
    for section in sections:
        summaries = pstore.list_daily_summaries(section.id)
        if not summaries:
            continue
        latest = max(summaries, key=lambda r: r.summary_date)
        if latest.progress:
            progress_lines.append(f"[{section.name}] {latest.summary_date}: {latest.progress[:100]}")
        if latest.risks:
            risk_lines.append(f"[{section.name}] {latest.risks[:100]}")
        if latest.challenges:
            challenge_lines.append(f"[{section.name}] {latest.challenges[:100]}")

    if progress_lines:
        parts.append("")
        parts.append("近期进度：" + "；".join(progress_lines))
    if risk_lines:
        parts.append("风险提示：" + "；".join(risk_lines))
    if challenge_lines:
        parts.append("主要挑战：" + "；".join(challenge_lines))

    return "\n".join(parts)


def _cmd_status(store: ProjectStore, rest: str) -> str:
    pid_s = rest.split(None, 1)[0] if rest else ""
    if not pid_s.isdigit():
        return "用法：/pro status <项目ID>"
    return format_project_detail(int(pid_s), store)


def _cmd_section(store: ProjectStore, rest: str) -> str:
    parts = rest.split(None, 1)
    if not parts:
        return (
            "用法：/pro sec add <项目ID> <Section名> [目标…] | sec task add <SectionID> <任务名> [标记…] | "
            "list <项目ID> | mod <SectionID> … | summary <SectionID> <日期> [进度…] | summaries <SectionID>"
        )
    action = parts[0].lower()
    args = parts[1].strip() if len(parts) > 1 else ""

    if action == "list":
        pid_s = args.split(None, 1)[0] if args else ""
        if not pid_s.isdigit():
            return "用法：/pro sec list <项目ID>"
        pid = int(pid_s)
        if not store.get_project(pid):
            return f"项目 #{pid} 不存在。"
        sections = store.list_sections(pid)
        if not sections:
            return f"项目 #{pid} 暂无 Section。"
        lines = [f"项目 #{pid} Sections："]
        for s in sections:
            lines.append(f"  {_format_section_line(s, stats=task_stats_for_section(s.id))}")
        return "\n".join(lines)

    if action == "add":
        chunks = args.split(None, 2)
        if len(chunks) < 2 or not chunks[0].isdigit():
            return "用法：/pro sec add <项目ID> <Section名> [目标…]"
        pid = int(chunks[0])
        name = chunks[1]
        tail = chunks[2] if len(chunks) > 2 else ""
        plain, meta = _split_meta(tail)
        goals = " ".join(plain).strip()
        try:
            row = store.add_section(
                pid,
                name,
                start_at=meta.get("start_at"),
                end_at=meta.get("end_at"),
                owner=meta.get("owner"),
                goals=goals,
                status=meta.get("status", "active"),
            )
        except ValueError as exc:
            return str(exc)
        return f"已创建 Section #{row.id}：{row.name}（项目 #{pid}）"

    if action == "task":
        subparts = args.split(None, 1)
        if not subparts or subparts[0].lower() != "add":
            return "用法：/pro sec task add <SectionID> <任务名> [内容] [@due-…] [@owner-…]"
        task_body = subparts[1].strip() if len(subparts) > 1 else ""
        id_parts = task_body.split(None, 1)
        if not id_parts or not id_parts[0].isdigit():
            return "用法：/pro sec task add <SectionID> <任务名> [标记…]"
        sid = int(id_parts[0])
        text = id_parts[1].strip() if len(id_parts) > 1 else ""
        section = store.get_section(sid)
        if not section:
            return f"Section #{sid} 不存在。"
        if not text:
            return "任务名不能为空。"
        try:
            from tools.task.store import TaskStore, _finalize_task_text

            parsed = parse_task_add_with_defaults(text)
            title, content, attachments = _finalize_task_text(
                parsed["title"],
                parsed.get("content", ""),
            )
            if not title:
                raise ValueError("任务名不能为空")
            parsed["title"] = title
            parsed["content"] = content
            parsed["attachments"] = attachments
            parsed["project_id"] = section.project_id
            parsed["section_id"] = sid
            row = TaskStore().add(**parsed)
        except ValueError as exc:
            return str(exc)
        return (
            f"已添加任务 #{row.id} 到 Section #{sid}（{section.name}）：{row.title}（{row.status}）"
        )

    if action == "mod":
        if not args:
            return "用法：/pro sec mod <SectionID> [名称/目标/标记…]"
        id_parts = args.split(None, 1)
        if not id_parts[0].isdigit():
            return "Section ID 须为数字。"
        sid = int(id_parts[0])
        mod_text = id_parts[1].strip() if len(id_parts) > 1 else ""
        if not mod_text:
            return f"用法：/pro sec mod {sid} <要修改的内容>"
        plain, meta = _split_meta(mod_text)
        kwargs: dict[str, Any] = {}
        if plain:
            kwargs["name"] = plain[0]
            if len(plain) > 1:
                kwargs["goals"] = " ".join(plain[1:])
        if "owner" in meta:
            kwargs["owner"] = meta["owner"]
        if "start_at" in meta:
            kwargs["start_at"] = meta["start_at"]
        if "end_at" in meta:
            kwargs["end_at"] = meta["end_at"]
        if "status" in meta:
            kwargs["status"] = meta["status"]
        try:
            updated = store.update_section(sid, **kwargs)
        except ValueError as exc:
            return str(exc)
        if not updated:
            return f"Section #{sid} 不存在。"
        return f"已更新 Section #{sid}：{updated.name} [{updated.status}]"

    if action == "summary":
        chunks = args.split(None, 2)
        if len(chunks) < 2 or not chunks[0].isdigit():
            return "用法：/pro sec summary <SectionID> <日期> [进度…] [@risk-…] [@challenge-…]"
        sid = int(chunks[0])
        summary_date = chunks[1]
        tail = chunks[2] if len(chunks) > 2 else ""
        plain, meta = _split_meta(tail)
        progress = " ".join(plain).strip()
        try:
            row = store.upsert_daily_summary(
                sid,
                summary_date,
                progress=progress,
                risks=meta.get("risk", ""),
                challenges=meta.get("challenge", ""),
                notes=meta.get("note", ""),
            )
        except ValueError as exc:
            return str(exc)
        return f"已保存 Section #{sid} {row.summary_date} 的每日总结"

    if action == "summaries":
        sid_s = args.split(None, 1)[0] if args else ""
        if not sid_s.isdigit():
            return "用法：/pro sec summaries <SectionID>"
        sid = int(sid_s)
        if not store.get_section(sid):
            return f"Section #{sid} 不存在。"
        rows = store.list_daily_summaries(sid)
        if not rows:
            return f"Section #{sid} 暂无每日总结。"
        lines = [f"Section #{sid} 每日总结："]
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

    return f"未知 sec 子命令：{action}"


def _cmd_doc(store: ProjectStore, rest: str) -> str:
    parts = rest.split(None, 1)
    if not parts or parts[0].lower() != "add":
        return "用法：/pro doc add <项目ID> <标题> [文件路径]"
    args = parts[1].strip() if len(parts) > 1 else ""
    chunks = args.split(None, 2)
    if len(chunks) < 2 or not chunks[0].isdigit():
        return "用法：/pro doc add <项目ID> <标题> [文件路径]"
    pid = int(chunks[0])
    title = chunks[1]
    file_path = chunks[2].strip() if len(chunks) > 2 else ""
    doc = store.add_doc(pid, title, file_path=file_path)
    if not doc:
        return f"项目 #{pid} 不存在。"
    return f"已为项目 #{pid} 添加文档 #{doc['id']}：{title}"


def _cmd_search(store: ProjectStore, keyword: str) -> str:
    key = keyword.strip().lower()
    if not key:
        return _USAGE
    rows = [
        p
        for p in store.list_projects(include_inbox=False)
        if key in p.name.lower() or key in (p.description or "").lower()
    ]
    if not rows:
        return f"未找到与「{keyword}」相关的项目。"
    lines = [f"项目搜索「{keyword}」："]
    for p in rows:
        lines.append(_format_project_line(p, stats=task_stats_for_project(p.id)))
    return "\n".join(lines)


def handle_project_command(args: str, store: ProjectStore | None = None) -> str:
    store = store or ProjectStore()
    body = (args or "").strip()
    if not body:
        return _USAGE

    parts = body.split(None, 1)
    sub = parts[0].lower()
    rest = parts[1].strip() if len(parts) > 1 else ""

    if sub == "list":
        return _cmd_list(store, rest)
    if sub == "add":
        return _cmd_add(store, rest)
    if sub == "mod":
        return _cmd_mod(store, rest)
    if sub in ("status", "show", "get"):
        return _cmd_status(store, rest)
    if sub in ("sec", "section"):
        return _cmd_section(store, rest)
    if sub == "doc":
        return _cmd_doc(store, rest)
    if sub.isdigit():
        return _cmd_status(store, sub)
    if sub == INBOX_PROJECT_NAME.lower():
        inbox = store.ensure_inbox()
        return _cmd_status(store, str(inbox.id))

    return _cmd_search(store, body)
