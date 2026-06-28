from __future__ import annotations

import sys
from pathlib import Path

import pytest

AGENT_SRC = Path(__file__).resolve().parents[2] / "agent" / "src"
if str(AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(AGENT_SRC))

from tools.capability.external_cli import run_external_cli
from tools.capability.cli_tools import create_cli_tools, load_cli_tools_config


def test_load_cli_tools_config():
    config_dir = Path(__file__).resolve().parents[2] / "agent" / "config"
    import infra.config as cfg

    old = cfg.get_config_dir
    cfg.get_config_dir = lambda: config_dir  # type: ignore[method-assign]
    try:
        data = load_cli_tools_config()
        assert "programs" in data
        assert data["programs"]["git"]["enabled"] is True
        assert data["programs"]["fzf"]["enabled"] is False
    finally:
        cfg.get_config_dir = old  # type: ignore[method-assign]


def test_run_external_cli_blocks_shell_operators():
    result = run_external_cli("git", "status; rm -rf /")
    assert "not allowed" in result.lower()


def test_create_cli_tools_count(monkeypatch, tmp_path):
    config_dir = Path(__file__).resolve().parents[2] / "agent" / "config"
    monkeypatch.setattr("infra.config.get_config_dir", lambda: config_dir)

    tools = create_cli_tools({"enabled": True})
    names = {t.name for t in tools}
    assert "git" in names
    assert "jq" in names
    assert "tree" in names
    assert "seven_zip" in names
    assert len(tools) >= 20


def test_registry_includes_cli_tools(monkeypatch, tmp_path):
    from tools.registry import build_registry
    from infra.config import load_yaml

    config_dir = Path(__file__).resolve().parents[2] / "agent" / "config"
    monkeypatch.setenv("AGENT_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("AGENT_DATA_DIR", str(tmp_path))

    registry = build_registry(load_yaml("tools.yaml"))
    names = {t.name for t in registry.get_enabled_tools()}
    assert "git" in names
    assert "glob" in names
    assert "aria2" in names
