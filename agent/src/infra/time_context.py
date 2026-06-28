from __future__ import annotations

import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from infra.config import load_app_config

_WEEKDAYS_ZH = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")

_FRESH_INFO_PATTERNS = (
    r"新特性",
    r"新版本",
    r"最新",
    r"最近",
    r"今年",
    r"当前版本",
    r"什么时候发布",
    r"何时发布",
    r"是否发布",
    r"发布了",
    r"上市",
    r"新闻",
    r"股价",
    r"汇率",
    r"what'?s new",
    r"latest version",
    r"recent release",
    r"release date",
    r"currently available",
    r"\bpython\s*\d+(?:\.\d+)?",
    r"\b\d+\.\d+\s*(?:版|版本)",
)


def get_current_datetime() -> datetime:
    """Return now in configured timezone, else the system local timezone."""
    tz_name = os.environ.get("AGENT_TIMEZONE") or load_app_config().get("timezone")
    if tz_name:
        try:
            return datetime.now(ZoneInfo(str(tz_name)))
        except Exception:
            pass
    return datetime.now().astimezone()


def is_fresh_info_query(text: str) -> bool:
    """Detect questions that need up-to-date facts rather than training memory."""
    lower = text.lower()
    return any(re.search(pattern, lower, re.I) for pattern in _FRESH_INFO_PATTERNS)


def _format_utc_offset(now: datetime) -> str:
    offset = now.strftime("%z")
    if len(offset) == 5:
        return f"{offset[:3]}:{offset[3:]}"
    return "+00:00"


def format_current_time_context(now: datetime | None = None) -> str:
    """Build a system-prompt block with authoritative current time."""
    current = now or get_current_datetime()
    tz_name = getattr(current.tzinfo, "key", None) or current.strftime("%Z") or "local"
    utc_offset = _format_utc_offset(current)
    weekday = _WEEKDAYS_ZH[current.weekday()]

    return (
        f"【重要】当前真实日期与时间（用户系统时钟，必须以此为准）：\n"
        f"- 今天是 {current.year}年{current.month}月{current.day}日 {weekday} "
        f"{current.strftime('%H:%M:%S')}（{tz_name}，UTC{utc_offset}）\n"
        f"- ISO 8601: {current.isoformat(timespec='seconds')}\n"
        f"当前年份是 {current.year}。回答任何与时间、版本发布、新闻、价格相关的问题时，"
        f"都必须基于上述日期，禁止把训练数据中的旧时间当作“现在”。\n"
        f"若问题涉及软件版本、发布状态、新闻或价格等可能已变化的事实，"
        f"必须先使用 web_search 或下方预检索结果，再作答。"
    )


def format_user_turn_time_hint(user_text: str, now: datetime | None = None) -> str:
    """Append a short hint to the user turn (LLM-only copy) for hard-to-ignore context."""
    current = now or get_current_datetime()
    hint = (
        f"\n\n[系统上下文：当前真实时间是 {current.year}年{current.month}月{current.day}日"
        f"{current.strftime('%H:%M:%S')}，当前年份是 {current.year}。"
    )
    if is_fresh_info_query(user_text):
        hint += "本问题涉及时效性信息，请优先使用 web_search 或系统提示中的预检索结果，"
        hint += "不要凭训练数据猜测发布状态或版本信息"
    hint += "]"
    return hint
