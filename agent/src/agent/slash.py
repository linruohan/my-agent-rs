"""本地斜杠命令：/tsk、/pro 等，不经 LLM。"""

from __future__ import annotations

import re

_SLASH_RE = re.compile(r"^/(tsk|pro)\b\s*(.*)$", re.IGNORECASE | re.DOTALL)


def dispatch_slash_command(text: str) -> str | None:
    """若文本为已支持的斜杠命令则返回执行结果，否则返回 None。"""
    body = (text or "").strip()
    match = _SLASH_RE.match(body)
    if not match:
        return None

    cmd = match.group(1).lower()
    args = (match.group(2) or "").strip()

    if cmd == "tsk":
        from tools.task import handle_task_command

        return handle_task_command(args)

    if cmd == "pro":
        from tools.project.commands import handle_project_command

        return handle_project_command(args)

    return None
