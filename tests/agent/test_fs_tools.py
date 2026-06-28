from __future__ import annotations

import sys
from pathlib import Path

import pytest

AGENT_SRC = Path(__file__).resolve().parents[2] / "agent" / "src"
if str(AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(AGENT_SRC))

from tools.capability.fs_cli import glob_fallback, grep_fallback, list_dir_entries
from tools.capability.fs_tools import create_glob_tool, create_grep_tool, create_list_dir_tool


@pytest.fixture
def workspace(monkeypatch, tmp_path):
    monkeypatch.setattr("infra.config.get_workspace_dir", lambda: tmp_path)
    monkeypatch.setattr("tools.capability.fs_cli.get_workspace_dir", lambda: tmp_path)
    monkeypatch.setattr(
        "infra.config.resolve_workspace_path",
        lambda rel: (tmp_path / rel).resolve(),
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello agent')\n", encoding="utf-8")
    (tmp_path / "src" / "util.py").write_text("# TODO fix bug\nprint('util')\n", encoding="utf-8")
    (tmp_path / "readme.md").write_text("# docs\n", encoding="utf-8")
    return tmp_path


def test_glob_fallback(workspace):
    result = glob_fallback(workspace, "**/*.py", max_results=10)
    assert "src/main.py" in result
    assert "src/util.py" in result


def test_grep_fallback(workspace):
    result = grep_fallback(workspace, "TODO", max_results=10, max_line_length=200, file_glob="", case_insensitive=False)
    assert "src/util.py" in result
    assert "TODO" in result


def test_list_dir(workspace):
    result = list_dir_entries(workspace, recursive=False, max_entries=20)
    assert "d src" in result
    assert "f readme.md" in result


def test_glob_tool_invoke(workspace, monkeypatch):
    monkeypatch.setattr("tools.capability.fs_tools.run_fd_glob", lambda *a, **k: None)
    tool = create_glob_tool({"max_results": 20, "timeout_sec": 5, "prefer_fd": True})
    result = tool.invoke({"pattern": "**/*.py", "path": "."})
    assert "src/main.py" in result


def test_grep_tool_invoke(workspace, monkeypatch):
    monkeypatch.setattr("tools.capability.fs_tools.run_rg_search", lambda *a, **k: None)
    tool = create_grep_tool({"max_results": 20, "timeout_sec": 5, "prefer_rg": True})
    result = tool.invoke({"pattern": "hello agent", "path": "src/main.py"})
    assert "hello agent" in result


def test_list_dir_tool_invoke(workspace):
    tool = create_list_dir_tool({"max_entries": 20})
    result = tool.invoke({"path": ".", "recursive": False})
    assert "src" in result


def test_registry_includes_fs_tools(monkeypatch, tmp_path):
    from tools.registry import build_registry
    from infra.config import load_yaml

    config_dir = Path(__file__).resolve().parents[2] / "agent" / "config"
    monkeypatch.setenv("AGENT_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("AGENT_DATA_DIR", str(tmp_path))

    registry = build_registry(load_yaml("tools.yaml"))
    names = {t.name for t in registry.get_enabled_tools()}
    assert "glob" in names
    assert "grep" in names
    assert "list_dir" in names
