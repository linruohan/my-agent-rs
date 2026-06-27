from __future__ import annotations

import pytest
import sys
from pathlib import Path

AGENT_SRC = Path(__file__).resolve().parents[1] / "agent" / "src"
if str(AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(AGENT_SRC))

from tools.registry import ToolRegistry, build_registry
from langchain_core.tools import tool


@pytest.fixture
def tools_config():
    return {
        "defaults": {"requires_confirmation_risk": "medium"},
        "capability": {
            "web_search": {"enabled": True, "risk": "low", "backend": "mock", "max_results": 3},
        },
        "business": {
            "create_todo": {"enabled": True, "risk": "low"},
            "list_todos": {"enabled": True, "risk": "low"},
            "read_calendar": {"enabled": True, "risk": "low"},
            "create_calendar_event": {"enabled": True, "risk": "medium", "requires_confirmation": True},
        },
    }


def test_register_and_get_enabled(tools_config):
    registry = build_registry(tools_config)
    enabled = registry.get_enabled_tools()
    names = {t.name for t in enabled}
    assert "web_search" in names
    assert "create_todo" in names
    assert "list_todos" in names
    assert "read_calendar" in names
    assert "create_calendar_event" in names


def test_requires_confirmation(tools_config):
    registry = build_registry(tools_config)
    assert registry.requires_confirmation("web_search") is False
    assert registry.requires_confirmation("create_calendar_event") is True


def test_get_meta_category(tools_config):
    registry = build_registry(tools_config)
    assert registry.get_meta("web_search")["category"] == "capability"
    assert registry.get_meta("create_todo")["category"] == "business"


def test_disabled_tool_excluded():
    config = {
        "capability": {"web_search": {"enabled": False}},
        "business": {"create_todo": {"enabled": True, "risk": "low"}},
    }
    registry = ToolRegistry(config)

    @tool
    def create_todo(title: str) -> str:
        """test"""
        return title

    registry.register(create_todo, "business", {"risk": "low"})
    enabled = registry.get_enabled_tools()
    assert len(enabled) == 1
    assert enabled[0].name == "create_todo"
