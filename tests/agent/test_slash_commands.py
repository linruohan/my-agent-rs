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
        from tools.task.store import TaskStore

        created = dispatch_slash_command("/pro add 春季发布 @owner-Alice @start-6.1 @end-6.30")
        assert created is not None
        assert "已创建项目" in created

        listed = dispatch_slash_command("/pro list")
        assert listed is not None
        assert "暂无项目任务。" in listed

        sec = dispatch_slash_command("/pro sec add 1 R13B100 核心功能 @owner-Bob")
        assert sec is not None
        assert "已创建 Section" in sec

        task = dispatch_slash_command("/pro sec task add 1 写接口 @due-6.30 @owner-Bob")
        assert task is not None
        assert "已添加任务" in task
        assert "Section #1" in task

        task2 = dispatch_slash_command("/tsk add 联调测试 @pro-1 @sec-1 @due-7.1")
        assert task2 is not None
        assert "已添加任务" in task2

        summary = dispatch_slash_command(
            "/pro sec summary 1 2025-06-28 完成 API @risk-人力 @challenge-联调"
        )
        assert summary is not None
        assert "已保存" in summary

        tstore = TaskStore()
        tstore.add("写报告", project_id=1, section_id=1)
        tstore.add("临时事项", project_id=1)

        listed2 = dispatch_slash_command("/pro list")
        assert listed2 is not None
        assert "| 项目编号 | 项目名 | section编号 | section名 |" in listed2
        assert "春季发布" in listed2
        assert "R13B100" in listed2

        status = dispatch_slash_command("/pro 1")
        assert status is not None
        assert "【项目 #1】" in status
        assert "【无section】" in status
        assert "【section#1】" in status
        assert "R13B100" in status
        assert "【项目总览】" in status
        assert "| ID | 标题 |" in status
        assert "写报告" in status
        assert "临时事项" in status
        assert "风险提示" in status


def test_pro_list_includes_inbox_tasks(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("AGENT_DATA_DIR", tmp)
        from agent.slash import dispatch_slash_command

        dispatch_slash_command("/tsk add 写报告 @due-6.28 @owner-林若寒")
        dispatch_slash_command("/pro add 春季发布 @owner-Alice @start-6.1 @end-6.30")

        listed = dispatch_slash_command("/pro list")
        assert listed is not None
        assert "| 项目编号 | 项目名 | section编号 | section名 |" in listed
        assert "Inbox" in listed
        assert "写报告" in listed
        assert "春季发布" not in listed or "暂无项目任务" not in listed


def test_dispatch_unknown_slash_returns_none():
    from agent.slash import dispatch_slash_command

    assert dispatch_slash_command("/search foo") is None
    assert dispatch_slash_command("hello /tsk list") is None
