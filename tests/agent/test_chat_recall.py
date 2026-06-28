from __future__ import annotations

from memory.chat_recall import (
    ChatHistoryStore,
    find_cached_answer,
    normalize_question,
    question_similarity,
    should_skip_history_recall,
)
from memory.learner import extract_preference_updates, learn_from_user_message, merge_user_preferences


def test_normalize_and_similarity():
    a = "什么是 LangGraph？"
    b = "什么是 langgraph"
    assert normalize_question(a) == normalize_question(b)
    assert question_similarity(a, b) >= 0.9


def test_chat_history_recall(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DATA_DIR", str(tmp_path))
    store = ChatHistoryStore(db_path=tmp_path / "chat_history.db")
    store.record("t1", "Python 是什么", "Python 是一种编程语言。")

    monkeypatch.setattr(
        "memory.chat_recall.get_memory_settings",
        lambda: {
            "history_recall": True,
            "history_similarity_min": 0.6,
            "history_max_age_days": 90,
        },
    )

    hit = find_cached_answer("python 是什么")
    assert hit is not None
    assert "编程语言" in hit["answer"]


def test_skip_fresh_info_recall():
    assert should_skip_history_recall("Python 3.13 最新版本有什么新特性")


def test_auto_learn_explicit_phrases(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        "memory.learner.get_memory_settings",
        lambda: {"auto_learn": True},
    )
    monkeypatch.setattr(
        "memory.learner.is_auto_learn_enabled",
        lambda: True,
    )

    updates = extract_preference_updates("请记住：回复请尽量简洁")
    assert "notes" in updates

    prefs = learn_from_user_message("我叫小明")
    assert prefs is not None
    assert prefs.get("name") == "小明"

    merged = merge_user_preferences({"language": "zh-CN"})
    assert merged["language"] == "zh-CN"
