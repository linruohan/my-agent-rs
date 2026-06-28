from __future__ import annotations

import sys
import tempfile
from pathlib import Path

AGENT_SRC = Path(__file__).resolve().parents[1] / "agent" / "src"
if str(AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(AGENT_SRC))


def test_dispatch_tsk_command(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("AGENT_DATA_DIR", tmp)
        from agent.slash import dispatch_slash_command

        result = dispatch_slash_command("/tsk add 写报告 @due-6.28")
        assert result is not None
        assert "已添加任务" in result
        listed = dispatch_slash_command("/tsk list")
        assert listed is not None
        assert "写报告" in listed


def test_dispatch_pro_command(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("AGENT_DATA_DIR", tmp)
        from agent.slash import dispatch_slash_command

        created = dispatch_slash_command("/pro add 春季发布 @owner-Alice @start-6.1 @end-6.30")
        assert created is not None
        assert "已创建项目" in created

        listed = dispatch_slash_command("/pro list")
        assert listed is not None
        assert "春季发布" in listed

        sec = dispatch_slash_command("/pro sec add 1 R13B100 核心功能 @owner-Bob")
        assert sec is not None
        assert "已创建 Section" in sec

        summary = dispatch_slash_command(
            "/pro sec summary 1 2025-06-28 完成 API @risk-人力 @challenge-联调"
        )
        assert summary is not None
        assert "已保存" in summary

        status = dispatch_slash_command("/pro 1")
        assert status is not None
        assert "R13B100" in status


def test_dispatch_unknown_slash_returns_none():
    from agent.slash import dispatch_slash_command

    assert dispatch_slash_command("/search foo") is None
    assert dispatch_slash_command("hello /tsk list") is None
