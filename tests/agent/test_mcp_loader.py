from __future__ import annotations

import os

import pytest

from tools.mcp_loader import (
    _normalize_server_config,
    _resolve_env_value,
    any_mcp_enabled,
    load_mcp_tools,
)


def test_resolve_env_value():
    os.environ["GITHUB_TOKEN"] = "gh-test"
    assert _resolve_env_value("${GITHUB_TOKEN}") == "gh-test"
    assert _resolve_env_value("plain") == "plain"


def test_normalize_server_config_stdio():
    os.environ["GITHUB_TOKEN"] = "gh-test"
    cfg = {
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "pkg"],
        "env": {"GITHUB_TOKEN": "${GITHUB_TOKEN}"},
    }
    normalized = _normalize_server_config("github", cfg)
    assert normalized["command"] == "npx"
    assert normalized["env"]["GITHUB_TOKEN"] == "gh-test"


def test_any_mcp_enabled():
    assert any_mcp_enabled({"github": {"enabled": False}}) is False
    assert any_mcp_enabled({"github": {"enabled": True}}) is True


@pytest.mark.asyncio
async def test_load_mcp_tools_disabled():
    tools = await load_mcp_tools({"github": {"enabled": False}})
    assert tools == []

@pytest.mark.asyncio
async def test_load_mcp_tools_invalid_config():
    tools = await load_mcp_tools({"bad": {"enabled": True, "transport": "stdio", "command": ""}})
    assert tools == []
