from __future__ import annotations

import re
import shlex
import subprocess
from pathlib import Path
from typing import Any

from infra.config import get_workspace_dir


def _validate_command(command: str, allowed: list[str]) -> tuple[str, list[str]] | str:
    command = command.strip()
    if not command:
        return "Empty command"
    try:
        parts = shlex.split(command, posix=(__import__("sys").platform != "win32"))
    except ValueError as e:
        return f"Invalid command syntax: {e}"
    if not parts:
        return "Empty command"
    base = Path(parts[0]).name.lower()
    allowed_lower = {c.lower() for c in allowed}
    if base not in allowed_lower and parts[0].lower() not in allowed_lower:
        return f"Command `{parts[0]}` not in whitelist: {allowed}"
    dangerous = [";", "&&", "||", "|", ">", "<", "`", "$(", "${"]
    for d in dangerous:
        if d in command:
            return f"Shell operator `{d}` is not allowed"
    return parts[0], parts


def run_bash(command: str, allowed_commands: list[str], timeout: int = 30) -> str:
    validated = _validate_command(command, allowed_commands)
    if isinstance(validated, str):
        return validated

    workspace = get_workspace_dir()
    shell = ["cmd", "/c", command] if __import__("sys").platform == "win32" else ["/bin/sh", "-c", command]

    try:
        result = subprocess.run(
            shell,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(workspace),
        )
    except subprocess.TimeoutExpired:
        return f"[TIMEOUT] Command exceeded {timeout}s"
    except Exception as e:
        return f"[ERROR] {e}"

    output = result.stdout or ""
    if result.stderr:
        output += ("\n" if output else "") + f"[stderr]\n{result.stderr}"
    if result.returncode != 0:
        output += f"\n[exit code {result.returncode}]"
    return output.strip() or "(no output)"


def create_bash_tool(config: dict[str, Any]):
    from langchain_core.tools import tool

    allowed = config.get("allowed_commands", ["ls", "cat", "grep", "find", "git", "python"])
    timeout = config.get("timeout_sec", 30)

    @tool
    def bash(command: str) -> str:
        """Run a shell command in the assistant workspace sandbox. Requires confirmation."""
        return run_bash(command, allowed, timeout)

    return bash
