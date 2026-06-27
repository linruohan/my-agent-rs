from __future__ import annotations

from infra.config import resolve_workspace_path


def read_workspace_file(path: str, max_chars: int = 100000) -> str:
    target = resolve_workspace_path(path)
    if not target.exists():
        return f"File not found: {path}"
    if not target.is_file():
        return f"Not a file: {path}"
    content = target.read_text(encoding="utf-8", errors="replace")
    if len(content) > max_chars:
        return content[:max_chars] + f"\n... (truncated, total {len(content)} chars)"
    return content


def write_workspace_file(path: str, content: str, overwrite: bool = False) -> str:
    target = resolve_workspace_path(path)
    if target.exists() and not overwrite:
        return f"File already exists: {path}. Set overwrite=true to replace."
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Written {path} ({len(content)} chars)"


def create_file_tools():
    from langchain_core.tools import tool

    @tool
    def read_file(path: str) -> str:
        """Read a text file from the assistant workspace."""
        return read_workspace_file(path)

    @tool
    def write_file(path: str, content: str, overwrite: bool = False) -> str:
        """Write a text file to the assistant workspace. Requires user confirmation."""
        return write_workspace_file(path, content, overwrite)

    return [read_file, write_file]
