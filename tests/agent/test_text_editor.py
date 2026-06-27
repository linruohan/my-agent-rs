from __future__ import annotations

import pytest

from tools.capability.text_editor import create_text_editor_tool


@pytest.fixture
def editor_tool(monkeypatch, tmp_path):
    monkeypatch.setattr("infra.config.get_workspace_dir", lambda: tmp_path)
    monkeypatch.setattr(
        "infra.config.resolve_workspace_path",
        lambda rel: (tmp_path / rel).resolve(),
    )
    return create_text_editor_tool({})


def test_create_and_view(editor_tool):
    result = editor_tool.invoke(
        {"command": "create", "path": "notes.txt", "file_text": "line1\nline2\n"}
    )
    assert "Created" in result

    view = editor_tool.invoke({"command": "view", "path": "notes.txt"})
    assert "line1" in view
    assert "line2" in view


def test_str_replace(editor_tool):
    editor_tool.invoke(
        {"command": "create", "path": "doc.md", "file_text": "hello world"}
    )
    result = editor_tool.invoke(
        {
            "command": "str_replace",
            "path": "doc.md",
            "old_str": "world",
            "new_str": "agent",
        }
    )
    assert "Replaced" in result
    view = editor_tool.invoke({"command": "view", "path": "doc.md"})
    assert "hello agent" in view


def test_path_traversal_blocked(monkeypatch, tmp_path):
    monkeypatch.setattr("infra.config.get_workspace_dir", lambda: tmp_path)

    from infra.config import resolve_workspace_path

    with pytest.raises(ValueError, match="escapes workspace"):
        resolve_workspace_path("../../etc/passwd")
