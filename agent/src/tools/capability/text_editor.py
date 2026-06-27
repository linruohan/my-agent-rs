from __future__ import annotations

from typing import Any

from infra.config import get_workspace_dir, resolve_workspace_path


def _view(path: str, view_range: list[int] | None = None) -> str:
    target = resolve_workspace_path(path)
    if not target.exists():
        return f"File not found: {path}"
    lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    if view_range and len(view_range) == 2:
        start, end = view_range
        lines = lines[max(0, start - 1) : end]
    numbered = [f"{i + 1:4d}| {line}" for i, line in enumerate(lines)]
    return "\n".join(numbered) if numbered else "(empty file)"


def _create(path: str, file_text: str) -> str:
    target = resolve_workspace_path(path)
    if target.exists():
        return f"File already exists: {path}. Use str_replace to edit."
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(file_text, encoding="utf-8")
    return f"Created {path} ({len(file_text)} chars)"


def _str_replace(path: str, old_str: str, new_str: str) -> str:
    target = resolve_workspace_path(path)
    if not target.exists():
        return f"File not found: {path}"
    content = target.read_text(encoding="utf-8")
    if old_str not in content:
        return f"String not found in {path}"
    count = content.count(old_str)
    if count > 1:
        return f"String appears {count} times; must be unique for str_replace"
    target.write_text(content.replace(old_str, new_str, 1), encoding="utf-8")
    return f"Replaced in {path}"


def _insert(path: str, insert_line: int, new_str: str) -> str:
    target = resolve_workspace_path(path)
    if not target.exists():
        return f"File not found: {path}"
    lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
    idx = max(0, min(insert_line, len(lines)))
    lines.insert(idx, new_str if new_str.endswith("\n") else new_str + "\n")
    target.write_text("".join(lines), encoding="utf-8")
    return f"Inserted at line {insert_line} in {path}"


def create_text_editor_tool(config: dict[str, Any] | None = None):
    from langchain_core.tools import tool

    get_workspace_dir()

    @tool
    def text_editor(
        command: str,
        path: str,
        file_text: str = "",
        old_str: str = "",
        new_str: str = "",
        insert_line: int = 0,
        view_range: list[int] | None = None,
    ) -> str:
        """View, create, or edit files in the assistant workspace.

        Args:
            command: view | create | str_replace | insert
            path: Relative path within workspace
        """
        cmd = command.strip().lower()
        if cmd == "view":
            return _view(path, view_range)
        if cmd == "create":
            return _create(path, file_text)
        if cmd == "str_replace":
            return _str_replace(path, old_str, new_str)
        if cmd == "insert":
            return _insert(path, insert_line, new_str)
        return f"Unknown command: {command}. Use view|create|str_replace|insert"

    return text_editor
