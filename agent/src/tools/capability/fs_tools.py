from __future__ import annotations

from typing import Any

from tools.capability.fs_cli import (
    DEFAULT_EXCLUDES,
    glob_fallback,
    grep_fallback,
    list_dir_entries,
    resolve_search_root,
    run_fd_glob,
    run_rg_search,
)


def create_glob_tool(config: dict[str, Any]):
    from langchain_core.tools import tool

    max_results = int(config.get("max_results", 200))
    timeout = int(config.get("timeout_sec", 30))
    prefer_fd = config.get("prefer_fd", True)
    excludes = config.get("exclude_dirs", list(DEFAULT_EXCLUDES))

    @tool
    def glob(pattern: str, path: str = ".") -> str:
        """Find files by glob pattern in the workspace (uses fd when installed).

        Args:
            pattern: Glob pattern, e.g. **/*.py, src/**/*.vue, *.md
            path: Directory relative to workspace (default .)
        """
        try:
            root = resolve_search_root(path)
        except FileNotFoundError as exc:
            return str(exc)
        except ValueError as exc:
            return str(exc)

        if prefer_fd:
            fd_out = run_fd_glob(
                root,
                pattern,
                max_results=max_results,
                timeout=timeout,
                excludes=excludes,
            )
            if fd_out is not None:
                return fd_out

        return glob_fallback(root, pattern, max_results=max_results, excludes=excludes)

    return glob


def create_grep_tool(config: dict[str, Any]):
    from langchain_core.tools import tool

    max_results = int(config.get("max_results", 100))
    max_line_length = int(config.get("max_line_length", 500))
    timeout = int(config.get("timeout_sec", 30))
    prefer_rg = config.get("prefer_rg", True)
    excludes = config.get("exclude_dirs", list(DEFAULT_EXCLUDES))

    @tool
    def grep(
        pattern: str,
        path: str = ".",
        glob: str = "",
        case_insensitive: bool = False,
    ) -> str:
        """Search file contents with ripgrep (rg) or Python fallback.

        Args:
            pattern: Regex pattern to search for
            path: File or directory relative to workspace (default .)
            glob: Optional filename filter, e.g. *.py, *.ts
            case_insensitive: Ignore letter case when matching
        """
        try:
            root = resolve_search_root(path)
        except FileNotFoundError as exc:
            return str(exc)
        except ValueError as exc:
            return str(exc)

        if prefer_rg:
            rg_out = run_rg_search(
                root,
                pattern,
                file_glob=glob,
                case_insensitive=case_insensitive,
                max_results=max_results,
                max_line_length=max_line_length,
                timeout=timeout,
                excludes=excludes,
            )
            if rg_out is not None:
                return rg_out

        return grep_fallback(
            root,
            pattern,
            file_glob=glob,
            case_insensitive=case_insensitive,
            max_results=max_results,
            max_line_length=max_line_length,
            excludes=excludes,
        )

    return grep


def create_list_dir_tool(config: dict[str, Any]):
    from langchain_core.tools import tool

    max_entries = int(config.get("max_entries", 200))
    excludes = config.get("exclude_dirs", list(DEFAULT_EXCLUDES))

    @tool
    def list_dir(path: str = ".", recursive: bool = False) -> str:
        """List files and directories under a workspace path.

        Args:
            path: Directory relative to workspace (default .)
            recursive: List nested entries when true
        """
        try:
            root = resolve_search_root(path)
        except FileNotFoundError as exc:
            return str(exc)
        except ValueError as exc:
            return str(exc)
        if not root.is_dir():
            return f"Not a directory: {path}"
        return list_dir_entries(
            root,
            recursive=recursive,
            max_entries=max_entries,
            excludes=excludes,
        )

    return list_dir
