from __future__ import annotations

import pytest

from tools.capability.bash import create_bash_tool, run_bash
from tools.registry import build_registry


def test_bash_whitelist_blocks():
    result = run_bash("rm -rf /", ["ls", "cat"])
    assert "not in whitelist" in result or "operator" in result.lower()


def test_bash_allowed_echo(monkeypatch, tmp_path):
    monkeypatch.setattr("tools.capability.bash.get_workspace_dir", lambda: tmp_path)
    if __import__("sys").platform == "win32":
        result = run_bash("echo hello", ["echo"], timeout=10)
    else:
        result = run_bash("echo hello", ["echo"], timeout=10)
    assert "hello" in result


def test_bash_tool_registered():
    config = {
        "capability": {
            "bash": {
                "enabled": True,
                "risk": "high",
                "requires_confirmation": True,
                "allowed_commands": ["echo"],
            }
        }
    }
    registry = build_registry(config)
    assert registry.get_tool("bash") is not None
    assert registry.requires_confirmation("bash")
