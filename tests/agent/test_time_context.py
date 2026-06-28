from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from infra.time_context import (
    format_current_time_context,
    format_user_turn_time_hint,
    is_fresh_info_query,
)


def test_format_current_time_context_uses_provided_datetime():
    now = datetime(2026, 6, 28, 15, 54, 5, tzinfo=ZoneInfo("Asia/Shanghai"))
    text = format_current_time_context(now)

    assert "2026年6月28日" in text
    assert "星期日" in text
    assert "15:54:05" in text
    assert "Asia/Shanghai" in text
    assert "UTC+08:00" in text
    assert "2026-06-28T15:54:05+08:00" in text
    assert "当前年份是 2026" in text
    assert "web_search" in text


def test_is_fresh_info_query_detects_version_questions():
    assert is_fresh_info_query("python 3.14新特性")
    assert is_fresh_info_query("What is the latest version of React?")
    assert not is_fresh_info_query("帮我写一个冒泡排序")


def test_format_user_turn_time_hint_for_fresh_query():
    now = datetime(2026, 6, 28, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    hint = format_user_turn_time_hint("python 3.14新特性", now)

    assert "2026年6月28日" in hint
    assert "web_search" in hint
