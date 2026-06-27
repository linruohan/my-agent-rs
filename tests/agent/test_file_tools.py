from __future__ import annotations

import pytest

from tools.business.file import create_file_tools, read_workspace_file, write_workspace_file


@pytest.fixture
def workspace(monkeypatch, tmp_path):
    monkeypatch.setattr("infra.config.get_workspace_dir", lambda: tmp_path)
    monkeypatch.setattr(
        "infra.config.resolve_workspace_path",
        lambda rel: (tmp_path / rel).resolve(),
    )
    return tmp_path


def test_read_write_file(workspace):
    write_workspace_file("data.txt", "hello file")
    content = read_workspace_file("data.txt")
    assert content == "hello file"


def test_file_tools_invoke(workspace):
    tools = {t.name: t for t in create_file_tools()}
    tools["write_file"].invoke(
        {"path": "out.txt", "content": "tool write", "overwrite": True}
    )
    result = tools["read_file"].invoke({"path": "out.txt"})
    assert "tool write" in result
