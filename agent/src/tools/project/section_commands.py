""" /sec 斜杠命令：Section 查看 / 列表 / 任务 / 修改 / 删除。"""

from __future__ import annotations

from typing import Any

from tools.project.commands import _split_meta
from tools.project.stats import task_stats_for_section
from tools.project.store import ProjectStore
from tools.task.parse import parse_task_add_with_defaults
from tools.task.store import TaskStore, format_task_table, _finalize_task_text

_USAGE = (
    "用法：/sec list | add <SectionID> <任务名> [描述…] | mod <SectionID> [名称/目标/标记…] | "
    "del <SectionID> | <SectionID>"
)


def format_section_detail(section_id: int, store: ProjectStore | None = None) -> str:
    pstore = store or ProjectStore()
    tstore = TaskStore()
    section = pstore.get_section(section_id)
    if not section:
        return f"Section #{section_id} 不存在。"

    project = pstore.get_project(section.project_id)
    proj_label = f"#{section.project_id} {project.name}" if project else f"#{section.project_id}"

    parts = [
        f"【Section #{section_id}】：{section.name} [{section.status}]",
        f"所属项目：{proj_label}",
        f"周期：{section.start_at or '—'} ~ {section.end_at or '—'} | 负责人：{section.owner or '—'}",
        f"目标：{section.goals or '—'}",
        "",
        "【任务】",
    ]
    tasks = sorted(
        tstore.list_filtered(include_done=True, section_id=section_id),
        key=lambda r: r.id,
    )
    parts.append(format_task_table(tasks) if tasks else "暂无任务。")

    summaries = pstore.list_daily_summaries(section_id)
    if summaries:
        parts.append("")
        parts.append("【每日总结】")
        for row in summaries[-5:]:
            line = f"[{row.summary_date}]"
            if row.progress:
                line += f" 进度:{row.progress[:80]}"
            if row.risks:
                line += f" 风险:{row.risks[:40]}"
            parts.append(line)

    return "\n".join(parts)


def format_sections_list(store: ProjectStore | None = None) -> str:
    pstore = store or ProjectStore()
    tstore = TaskStore()
    lines: list[str] = ["Section 列表："]
    found = False

    for project in pstore.list_projects(include_inbox=False):
        if project.is_inbox:
            continue
        sections = pstore.list_sections(project.id)
        for section in sections:
            found = True
            stats = task_stats_for_section(section.id)
            lines.append(
                f"\n#{section.id} {section.name} | 项目 #{project.id} {project.name} | "
                f"任务 {stats.get('completed', 0)}/{stats.get('total', 0)}"
            )
            tasks = sorted(
                tstore.list_filtered(include_done=True, section_id=section.id),
                key=lambda r: r.id,
            )
            if tasks:
                lines.append(format_task_table(tasks))
            else:
                lines.append("（暂无任务）")

    if not found:
        return "暂无 Section。可用 `/pro sec add <项目ID> <Section名> [描述]` 创建。"
    return "\n".join(lines)


def _cmd_add(store: ProjectStore, rest: str) -> str:
    id_parts = rest.split(None, 1)
    if not id_parts or not id_parts[0].isdigit():
        return "用法：/sec add <SectionID> <任务名> [描述…]"
    sid = int(id_parts[0])
    text = id_parts[1].strip() if len(id_parts) > 1 else ""
    section = store.get_section(sid)
    if not section:
        return f"Section #{sid} 不存在。"
    if not text:
        return "任务名不能为空。"
    try:
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
    return f"已添加任务 #{row.id} 到 Section #{sid}（{section.name}）：{row.title}（{row.status}）"


def _cmd_mod(store: ProjectStore, rest: str) -> str:
    if not rest:
        return "用法：/sec mod <SectionID> [名称/目标/标记…]"
    id_parts = rest.split(None, 1)
    if not id_parts[0].isdigit():
        return "Section ID 须为数字。"
    sid = int(id_parts[0])
    mod_text = id_parts[1].strip() if len(id_parts) > 1 else ""
    if not mod_text:
        return f"用法：/sec mod {sid} <要修改的内容>"
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


def _cmd_del(store: ProjectStore, rest: str) -> str:
    sid_s = rest.split(None, 1)[0] if rest else ""
    if not sid_s.isdigit():
        return "用法：/sec del <SectionID>"
    sid = int(sid_s)
    section = store.get_section(sid)
    if not section:
        return f"Section #{sid} 不存在。"
    from tools.business.project import delete_section_record

    if delete_section_record(sid):
        return f"已删除 Section #{sid}：{section.name}（其中任务已变为无 Section）"
    return f"删除 Section #{sid} 失败。"


def handle_section_command(args: str, store: ProjectStore | None = None) -> str:
    store = store or ProjectStore()
    body = (args or "").strip()
    if not body:
        return _USAGE

    parts = body.split(None, 1)
    sub = parts[0].lower()
    rest = parts[1].strip() if len(parts) > 1 else ""

    if sub == "list":
        return format_sections_list(store)
    if sub == "add":
        return _cmd_add(store, rest)
    if sub == "mod":
        return _cmd_mod(store, rest)
    if sub in ("del", "rm", "delete"):
        return _cmd_del(store, rest)
    if sub.isdigit():
        return format_section_detail(int(sub), store)

    return _USAGE
