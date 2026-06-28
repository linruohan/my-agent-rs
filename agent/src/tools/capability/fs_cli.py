from __future__ import annotations

import fnmatch
import re
import shutil
import subprocess
from pathlib import Path

from infra.config import get_workspace_dir, resolve_workspace_path

DEFAULT_EXCLUDES = (
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "target",
    "dist",
    "build",
    ".next",
    ".cursor",
)

TEXT_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".vue",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".md",
    ".txt",
    ".rs",
    ".go",
    ".java",
    ".html",
    ".css",
    ".scss",
    ".sql",
    ".sh",
    ".ps1",
    ".xml",
    ".ini",
    ".cfg",
    ".env",
}


def find_binary(candidates: list[str]) -> str | None:
    for name in candidates:
        path = shutil.which(name)
        if path:
            return path
    return None


def resolve_search_root(path: str) -> Path:
    raw = (path or ".").strip() or "."
    if raw in (".", "./"):
        return get_workspace_dir()
    target = resolve_workspace_path(raw)
    if not target.exists():
        raise FileNotFoundError(f"Path not found: {raw}")
    return target


def _run_command(args: list[str], *, cwd: Path, timeout: int) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd),
            encoding="utf-8",
            errors="replace",
        )
        return result.returncode, result.stdout or "", result.stderr or ""
    except subprocess.TimeoutExpired:
        return 124, "", f"[TIMEOUT] Command exceeded {timeout}s"
    except FileNotFoundError:
        return 127, "", "[ERROR] Command not found"
    except Exception as exc:
        return 1, "", f"[ERROR] {exc}"


def _format_cli_output(code: int, stdout: str, stderr: str) -> str:
    lines: list[str] = []
    if stdout.strip():
        lines.append(stdout.rstrip())
    if stderr.strip():
        lines.append(f"[stderr]\n{stderr.rstrip()}")
    if code not in (0, 1) and not lines:
        lines.append(f"[exit code {code}]")
    return "\n".join(lines).strip() or "(no matches)"


def _should_skip_dir(name: str) -> bool:
    return name in DEFAULT_EXCLUDES or name.startswith(".")


def _is_probably_text(path: Path) -> bool:
    if path.suffix.lower() in TEXT_SUFFIXES:
        return True
    if not path.suffix:
        return True
    return False


def run_fd_glob(
    root: Path,
    pattern: str,
    *,
    max_results: int,
    timeout: int,
    excludes: list[str] | None = None,
) -> str | None:
    fd = find_binary(["fd"])
    if not fd:
        return None

    args = [
        fd,
        "--glob",
        pattern,
        "--type",
        "f",
        "--max-results",
        str(max_results),
    ]
    for name in excludes or DEFAULT_EXCLUDES:
        args.extend(["--exclude", name])
    args.append(".")

    code, stdout, stderr = _run_command(args, cwd=root, timeout=timeout)
    if code == 127:
        return None
    return _format_cli_output(code, stdout, stderr)


def glob_fallback(
    root: Path,
    pattern: str,
    *,
    max_results: int,
    excludes: list[str] | None = None,
) -> str:
    skip = set(excludes or DEFAULT_EXCLUDES)
    matches: list[str] = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if len(matches) >= max_results:
            break
        rel_parts = path.relative_to(root).parts
        if any(part in skip for part in rel_parts):
            continue
        rel = path.relative_to(root).as_posix()
        if (
            (hasattr(path, "full_match") and path.full_match(pattern))
            or fnmatch.fnmatch(rel, pattern)
            or fnmatch.fnmatch(path.name, pattern.lstrip("**/"))
        ):
            matches.append(rel)

    if not matches:
        return "(no matches)"
    suffix = f"\n... (truncated at {max_results} results)" if len(matches) >= max_results else ""
    return "\n".join(sorted(set(matches))) + suffix


def run_rg_search(
    root: Path,
    pattern: str,
    *,
    file_glob: str,
    case_insensitive: bool,
    max_results: int,
    max_line_length: int,
    timeout: int,
    excludes: list[str] | None = None,
) -> str | None:
    rg = find_binary(["rg", "rg.exe"])
    if not rg:
        return None

    args = [
        rg,
        "-n",
        "--color",
        "never",
        "--max-count",
        str(max_results),
        "--max-columns",
        str(max_line_length),
    ]
    if case_insensitive:
        args.append("-i")
    if file_glob:
        args.extend(["--glob", file_glob])
    for name in excludes or DEFAULT_EXCLUDES:
        args.extend(["--glob", f"!{name}/**"])
    args.extend([pattern, "."])

    search_cwd = root if root.is_dir() else root.parent
    if root.is_file():
        args = [rg, "-n", "--color", "never", "--max-count", str(max_results)]
        if case_insensitive:
            args.append("-i")
        args.extend([pattern, str(root.name)])
        search_cwd = root.parent

    code, stdout, stderr = _run_command(args, cwd=search_cwd, timeout=timeout)
    if code == 127:
        return None
    return _format_cli_output(code, stdout, stderr)


def grep_fallback(
    root: Path,
    pattern: str,
    *,
    file_glob: str,
    case_insensitive: bool,
    max_results: int,
    max_line_length: int,
    excludes: list[str] | None = None,
) -> str:
    skip = set(excludes or DEFAULT_EXCLUDES)
    flags = re.IGNORECASE if case_insensitive else 0
    try:
        regex = re.compile(pattern, flags)
    except re.error as exc:
        return f"Invalid regex pattern: {exc}"

    workspace = get_workspace_dir()
    base = root if root.is_dir() else root.parent
    lines_out: list[str] = []
    files: list[Path]
    if root.is_file():
        files = [root]
    else:
        files = [p for p in root.rglob("*") if p.is_file()]

    for file_path in files:
        if len(lines_out) >= max_results:
            break
        try:
            file_path.relative_to(workspace)
        except ValueError:
            continue
        rel_parts = file_path.relative_to(base).parts
        if any(part in skip for part in rel_parts):
            continue
        if file_glob and not fnmatch.fnmatch(file_path.name, file_glob):
            continue
        if not _is_probably_text(file_path):
            continue
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line_no, line in enumerate(content.splitlines(), start=1):
            if len(lines_out) >= max_results:
                break
            if regex.search(line):
                clipped = line if len(line) <= max_line_length else line[: max_line_length - 3] + "..."
                display = file_path.relative_to(base).as_posix()
                lines_out.append(f"{display}:{line_no}:{clipped}")

    if not lines_out:
        return "(no matches)"
    suffix = f"\n... (truncated at {max_results} matches)" if len(lines_out) >= max_results else ""
    return "\n".join(lines_out) + suffix


def list_dir_entries(
    root: Path,
    *,
    recursive: bool,
    max_entries: int,
    excludes: list[str] | None = None,
) -> str:
    skip = set(excludes or DEFAULT_EXCLUDES)
    entries: list[str] = []

    def add_entry(path: Path) -> None:
        if len(entries) >= max_entries:
            return
        rel = path.relative_to(root).as_posix()
        prefix = "d" if path.is_dir() else "f"
        entries.append(f"{prefix} {rel}")

    if recursive:
        for path in sorted(root.rglob("*")):
            if any(part in skip for part in path.relative_to(root).parts):
                continue
            add_entry(path)
            if len(entries) >= max_entries:
                break
    else:
        for path in sorted(root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if path.name in skip:
                continue
            add_entry(path)

    if not entries:
        return "(empty)"
    suffix = f"\n... (truncated at {max_entries} entries)" if len(entries) >= max_entries else ""
    return "\n".join(entries) + suffix
