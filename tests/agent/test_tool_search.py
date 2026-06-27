from __future__ import annotations

from tools.capability.tool_search import search_tools
from tools.registry import build_registry


def test_tool_search_finds_web_tools():
    config = {
        "capability": {
            "web_search": {"enabled": True, "risk": "low", "backend": "mock"},
            "tool_search": {"enabled": True, "risk": "low"},
        },
        "business": {
            "create_todo": {"enabled": True, "risk": "low"},
        },
    }
    registry = build_registry(config)
    results = search_tools(registry, "search web internet", limit=3)
    names = [r["name"] for r in results]
    assert "web_search" in names


def test_tool_search_invoke():
    config = {
        "capability": {
            "web_search": {"enabled": True, "risk": "low", "backend": "mock"},
            "tool_search": {"enabled": True, "risk": "low", "max_results": 5},
        },
    }
    registry = build_registry(config)
    tool = registry.get_tool("tool_search")
    assert tool is not None
    result = tool.invoke({"query": "todo task"})
    assert isinstance(result, str)
