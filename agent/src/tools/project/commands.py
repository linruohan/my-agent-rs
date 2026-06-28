""" /pro 斜杠命令：项目 / Section / 每日总结本地操作。"""

from __future__ import annotations

import re
from typing import Any

from tools.project.stats import task_stats_for_project, task_stats_for_section
from tools.project.store import INBOX_PROJECT_NAME, ProjectStore, ProjectRow, SectionRow
from tools.task.parse import tokenize_task_text

_RE_OWNER = re.compile(r"^@\{([^}]+)\}$|^@owner-(.+)$", re.IGNORECASE)
_RE_START = re.compile(r"^@start-(.+)$", re.IGNORECASE)
_RE_END = re.compile(r"^@end-(.+)$", re.IGNORECASE)
_RE_STATUS = re.compile(r"^@status-(\w+)$", re.IGNORECASE)
_RE_RISK = re.compile(r"^@risk-(.+)$", re.IGNORECASE)
_RE_CHALLENGE = re.compile(r"^@challenge-(.+)$", re.IGNORECASE)
_RE_NOTE = re.compile(r"^@note-(.+)$", re.IGNORECASE)

_USAGE = (
    "用法：/pro list | add <项目名> [描述] [标记…] | mod <项目ID> [修改内容] | status <项目ID>\n"
    "      /pro sec add <项目ID> <Section名> [目标…] | sec list <项目ID> | sec mod <SectionID> …\n"
    "      /pro sec summary <SectionID> <日期> [进度…] | sec summaries <SectionID>\n"
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


def _cmd_list(store: ProjectStore, rest: str) -> str:
    status = ""
    plain, meta = _split_meta(rest)
    if meta.get("status"):
        status = meta["status"]
    elif plain:
        status = plain[0]
    rows = store.list_projects(status, include_inbox=False)
    if not rows:
        return "暂无项目。"
    lines = ["项目列表："]
    for p in rows:
        stats = task_stats_for_project(p.id)
        lines.append(_format_project_line(p, stats=stats))
    return "\n".join(lines)


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


def _cmd_status(store: ProjectStore, rest: str) -> str:
    pid_s = rest.split(None, 1)[0] if rest else ""
    if not pid_s.isdigit():
        return "用法：/pro status <项目ID>"
    pid = int(pid_s)
    project = store.get_project(pid)
    if not project:
        return f"项目 #{pid} 不存在。"
    stats = task_stats_for_project(pid)
    total = stats["total"]
    done = stats["completed"]
    pct = int(done / total * 100) if total else 0
    lines = [
        f"项目 #{pid}: {project.name} [{project.status}]",
        f"周期：{project.start_at or '—'} ~ {project.end_at or '—'}",
        f"负责人：{project.owner or '—'}",
        f"总任务：{done}/{total} ({pct}%)",
    ]
    if project.description:
        lines.append(f"描述：{project.description}")
    sections = store.list_sections(pid)
    if sections:
        lines.append("Sections：")
        for s in sections:
            sstats = task_stats_for_section(s.id)
            lines.append(f"  {_format_section_line(s, stats=sstats)}")
    docs = store.list_docs(pid)
    if docs:
        lines.append(f"文档 ({len(docs)})：")
        for d in docs[:5]:
            lines.append(f"  - #{d['id']} {d['title']}")
    return "\n".join(lines)


def _cmd_section(store: ProjectStore, rest: str) -> str:
    parts = rest.split(None, 1)
    if not parts:
        return (
            "用法：/pro sec add <项目ID> <Section名> [目标…] | list <项目ID> | "
            "mod <SectionID> … | summary <SectionID> <日期> [进度…] | summaries <SectionID>"
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
