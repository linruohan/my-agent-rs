from __future__ import annotations

import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

from infra.config import get_workspace_dir

_SHELL_OPERATORS = re.compile(r"[;&|`$]|>\s|<\s|\$\(|\${")
_GLOBAL_ARG_PREFIXES = ["--version", "-version", "-v", "--help", "-h", "help", "-?"]

_MAX_ARGS_TOKENS = 64


def find_binary(candidates: list[str]) -> str | None:
    for name in candidates:
        path = shutil.which(name)
        if path:
            return path
    return None


def _validate_args_string(args: str) -> str | None:
    raw = (args or "").strip()
    if not raw:
        return None
    if _SHELL_OPERATORS.search(raw):
        return "Shell operators (; && | > < ` $()) are not allowed"
    try:
        tokens = shlex.split(raw, posix=(__import__("sys").platform != "win32"))
    except ValueError as exc:
        return f"Invalid argument syntax: {exc}"
    if len(tokens) > _MAX_ARGS_TOKENS:
        return f"Too many arguments (max {_MAX_ARGS_TOKENS})"
    return None


def _first_meaningful_token(args: str) -> str:
    try:
        tokens = shlex.split(args.strip(), posix=(__import__("sys").platform != "win32"))
    except ValueError:
        return args.strip().split()[0] if args.strip() else ""
    if not tokens:
        return ""
    first = tokens[0]
    if first.startswith("-"):
        return first
    return first.lower()


def _prefix_allowed(token: str, allowed: list[str]) -> bool:
    if not allowed:
        return True
    lower = token.lower()
    for item in allowed:
        item_lower = item.lower()
        if lower == item_lower or lower.startswith(item_lower):
            return True
        if item_lower.endswith(".") and lower.startswith(item_lower):
            return True
        if item_lower in ("http://", "https://") and lower.startswith(item_lower):
            return True
    return False


def _needs_confirmation(token: str, confirm_prefixes: list[str]) -> bool:
    if not confirm_prefixes:
        return False
    lower = token.lower()
    joined = " ".join(shlex.split(token, posix=False)).lower() if token else lower
    for item in confirm_prefixes:
        item_lower = item.lower()
        if lower == item_lower or lower.startswith(item_lower + " ") or joined.startswith(item_lower):
            return True
    return False


def run_external_cli(
    binary: str,
    args: str = "",
    *,
    binary_aliases: list[str] | None = None,
    allowed_prefixes: list[str] | None = None,
    confirm_prefixes: list[str] | None = None,
    timeout: int = 60,
    max_output_chars: int = 80000,
    cwd: Path | None = None,
) -> str:
    err = _validate_args_string(args)
    if err:
        return err

    first = _first_meaningful_token(args)
    if allowed_prefixes and first:
        allowed_all = allowed_prefixes + _GLOBAL_ARG_PREFIXES
        if not _prefix_allowed(first, allowed_all):
            head = args.strip().split()[0] if args.strip() else ""
            if head and not _prefix_allowed(head, allowed_all):
                return (
                    f"Subcommand or flag `{first}` not allowed. "
                    f"Allowed prefixes: {allowed_prefixes}"
                )

    candidates = [binary, *(binary_aliases or [])]
    tokens: list[str] = []
    if args.strip():
        tokens = shlex.split(args.strip(), posix=(__import__("sys").platform != "win32"))

    resolved: str | None = None
    if tokens and tokens[0].lower() in {c.lower() for c in candidates}:
        resolved = find_binary([tokens[0]])
        if resolved:
            tokens = tokens[1:]

    if not resolved:
        resolved = find_binary(candidates)
    if not resolved:
        return f"Command not found on PATH: {binary}. Install via Scoop or add to PATH."

    workdir = cwd or get_workspace_dir()
    cmd = [resolved, *tokens]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(workdir),
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return f"[TIMEOUT] Command exceeded {timeout}s"
    except Exception as exc:
        return f"[ERROR] {exc}"

    output = result.stdout or ""
    if result.stderr:
        output += ("\n" if output else "") + f"[stderr]\n{result.stderr}"
    if result.returncode != 0:
        output += f"\n[exit code {result.returncode}]"
    output = output.strip() or "(no output)"
    if len(output) > max_output_chars:
        output = output[:max_output_chars] + f"\n... (truncated, total {len(output)} chars)"
    return output


def program_requires_confirmation(prog: dict[str, Any], args: str) -> bool:
    if prog.get("requires_confirmation"):
        return True
    first = _first_meaningful_token(args)
    return _needs_confirmation(first, prog.get("confirm_prefixes") or [])
