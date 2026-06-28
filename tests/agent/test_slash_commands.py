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

        deleted = dispatch_slash_command("/tsk del 1")
        assert deleted is not None
        assert "已删除任务" in deleted


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
        assert "项目列表" in listed
        assert "春季发布" in listed

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


def test_pro_del_command(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("AGENT_DATA_DIR", tmp)
        from agent.slash import dispatch_slash_command
        from tools.project.store import ProjectStore

        missing = dispatch_slash_command("/pro del 99")
        assert missing is not None
        assert "不存在" in missing

        inbox = ProjectStore().ensure_inbox()
        inbox_del = dispatch_slash_command(f"/pro del {inbox.id}")
        assert inbox_del is not None
        assert "不可删除" in inbox_del
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("AGENT_DATA_DIR", tmp)
        from agent.slash import dispatch_slash_command

        dispatch_slash_command("/tsk add 写报告 @due-6.28 @owner-林若寒")
        dispatch_slash_command("/pro add 春季发布 @owner-Alice @start-6.1 @end-6.30")

        listed = dispatch_slash_command("/pro list")
        assert listed is not None
        assert "项目列表" in listed
        assert "春季发布" in listed
        assert "写报告" not in listed


def test_dispatch_sec_command(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("AGENT_DATA_DIR", tmp)
        from agent.slash import dispatch_slash_command

        dispatch_slash_command("/pro add 春季发布 发布说明")
        dispatch_slash_command("/pro sec add 1 R13B100 核心功能")

        detail = dispatch_slash_command("/sec 1")
        assert detail is not None
        assert "【Section #1】" in detail
        assert "R13B100" in detail

        task = dispatch_slash_command("/sec add 1 写接口 接口文档")
        assert task is not None
        assert "已添加任务" in task

        listed = dispatch_slash_command("/sec list")
        assert listed is not None
        assert "Section 列表" in listed
        assert "R13B100" in listed
        assert "写接口" in listed

        modified = dispatch_slash_command("/sec mod 1 R14B200 新目标")
        assert modified is not None
        assert "已更新 Section" in modified

        deleted = dispatch_slash_command("/sec del 1")
        assert deleted is not None
        assert "已删除 Section" in deleted


def test_dispatch_unknown_slash_returns_none():
    from agent.slash import dispatch_slash_command

    assert dispatch_slash_command("/search foo") is None
    assert dispatch_slash_command("hello /tsk list") is None
