from __future__ import annotations

import re
from typing import Any

PLAN_KEYWORDS = [
    "步骤",
    "计划",
    "首先",
    "然后",
    "接着",
    "最后",
    "分步",
    "多渠道",
    "汇总",
    "一并",
    "同时",
    "workflow",
    "step by step",
]


def needs_planning(text: str) -> bool:
    hits = sum(1 for k in PLAN_KEYWORDS if k in text.lower())
    if hits >= 2:
        return True
    if len(text) < 80:
        return False
    if re.search(r"\d+[、.)]\s*\S+", text):
        return True
    verbs = len(re.findall(r"(创建|查询|搜索|发送|整理|分析|汇总|导入|导出)", text))
    return verbs >= 3


def generate_task_plan(text: str, llm=None) -> list[str]:
    """Generate a simple task plan. Uses LLM if available, else heuristic."""
    if llm is not None:
        try:
            from langchain_core.messages import HumanMessage

            prompt = (
                "Break the following user request into 3-6 concise actionable steps. "
                "Return one step per line, no numbering prefix:\n\n"
                f"{text}"
            )
            resp = llm.invoke([HumanMessage(content=prompt)])
            content = resp.content if hasattr(resp, "content") else str(resp)
            lines = [ln.strip("-• \t") for ln in str(content).splitlines() if ln.strip()]
            if lines:
                return lines[:6]
        except Exception:
            pass

    steps = []
    if re.search(r"搜索|查询|search", text, re.I):
        steps.append("检索所需信息")
    if re.search(r"待办|todo|任务", text, re.I):
        steps.append("更新待办事项")
    if re.search(r"日历|日程|calendar", text, re.I):
        steps.append("检查或更新日历")
    if re.search(r"邮件|email", text, re.I):
        steps.append("处理邮件相关操作")
    if re.search(r"文档|笔记|知识库", text, re.I):
        steps.append("检索或更新知识库")
    if not steps:
        steps = ["分析用户需求", "执行必要工具调用", "汇总结果并回复用户"]
    return steps[:6]


def format_plan_for_prompt(plan: list[str]) -> str:
    lines = ["Task plan:"] + [f"{i + 1}. {s}" for i, s in enumerate(plan)]
    return "\n".join(lines)
