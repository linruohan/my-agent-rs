from __future__ import annotations

import pytest

from agent.planner import generate_task_plan, needs_planning


def test_needs_planning_simple():
    assert not needs_planning("你好")


def test_needs_planning_complex():
    text = (
        "请帮我首先搜索最新的 Rust 版本，然后创建待办提醒更新项目，"
        "接着整理知识库文档，最后汇总发邮件给团队。"
    )
    assert needs_planning(text)


def test_generate_task_plan_heuristic():
    text = "帮我搜索资料并创建待办，同时查一下日历有没有冲突"
    plan = generate_task_plan(text, llm=None)
    assert len(plan) >= 2
