from __future__ import annotations

from tools.registry import build_registry


def test_phase2_tools_registered():
    config = {
        "defaults": {"requires_confirmation_risk": "medium"},
        "capability": {
            "web_search": {"enabled": True, "risk": "low", "backend": "mock"},
            "web_fetch": {"enabled": True, "risk": "low"},
            "text_editor": {"enabled": True, "risk": "medium"},
            "code_execution": {"enabled": True, "risk": "high", "requires_confirmation": True},
        },
        "business": {
            "create_todo": {"enabled": True, "risk": "low"},
            "list_todos": {"enabled": True, "risk": "low"},
            "read_file": {"enabled": True, "risk": "low"},
            "write_file": {"enabled": True, "risk": "high", "requires_confirmation": True},
        },
    }
    registry = build_registry(config)
    names = {t.name for t in registry.get_enabled_tools()}
    expected = {
        "web_search",
        "web_fetch",
        "text_editor",
        "code_execution",
        "create_todo",
        "list_todos",
        "read_file",
        "write_file",
    }
    assert expected.issubset(names)


def test_hitl_confirmation_flags():
    config = {
        "capability": {
            "web_fetch": {"enabled": True, "risk": "low"},
            "code_execution": {"enabled": True, "risk": "high", "requires_confirmation": True},
        },
        "business": {
            "write_file": {"enabled": True, "risk": "high", "requires_confirmation": True},
        },
    }
    registry = build_registry(config)
    assert registry.requires_confirmation("web_fetch") is False
    assert registry.requires_confirmation("code_execution") is True
    assert registry.requires_confirmation("write_file") is True
