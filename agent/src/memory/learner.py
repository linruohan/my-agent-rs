from __future__ import annotations

import re
from typing import Any

from infra.user_settings import get_memory_settings
from memory.store import MemoryStore, get_user_preferences

_EXPLICIT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"请记住[：:]\s*(.+)", re.I), "remember"),
    (re.compile(r"记住[：:]\s*(.+)", re.I), "remember"),
    (re.compile(r"以后(?:请|都)?(.+)", re.I), "habit"),
    (re.compile(r"我(?:喜欢|偏好|习惯)(.+)", re.I), "likes"),
    (re.compile(r"我不(?:喜欢|想要|希望)(.+)", re.I), "dislikes"),
    (re.compile(r"叫我(.+?)(?:吧|就好|即可)?$", re.I), "nickname"),
    (re.compile(r"我的(?:名字|姓名)(?:是|叫)\s*(.+)", re.I), "name"),
    (re.compile(r"我叫\s*(.+?)(?:[，,。]|$)", re.I), "name"),
    (re.compile(r"默认(?:使用|用)\s*(.+)", re.I), "default"),
    (re.compile(r"回复(?:请|用)?(?:使用)?\s*(中文|英文|English|Chinese)", re.I), "language"),
]


def is_auto_learn_enabled() -> bool:
    return bool(get_memory_settings().get("auto_learn", False))


def extract_preference_updates(text: str) -> dict[str, Any]:
    """Rule-based preference extraction from a user message."""
    raw = (text or "").strip()
    if not raw:
        return {}

    updates: dict[str, Any] = {}
    notes: list[str] = []

    for pattern, kind in _EXPLICIT_PATTERNS:
        match = pattern.search(raw)
        if not match:
            continue
        value = match.group(1).strip().rstrip("。.")
        if not value:
            continue
        if kind == "remember":
            notes.append(value)
        elif kind == "habit":
            notes.append(f"习惯: {value}")
        elif kind == "likes":
            likes = updates.setdefault("likes", [])
            if isinstance(likes, list) and value not in likes:
                likes.append(value)
        elif kind == "dislikes":
            dislikes = updates.setdefault("dislikes", [])
            if isinstance(dislikes, list) and value not in dislikes:
                dislikes.append(value)
        elif kind == "nickname":
            updates["nickname"] = value
        elif kind == "name":
            updates["name"] = value
        elif kind == "default":
            updates.setdefault("defaults", {})["general"] = value
        elif kind == "language":
            lang = value.lower()
            updates["language"] = "zh-CN" if lang in ("中文", "chinese") else "en-US"

    if notes:
        updates["notes"] = notes
    return updates


def merge_user_preferences(updates: dict[str, Any]) -> dict[str, Any]:
    if not updates:
        return get_user_preferences()

    store = MemoryStore()
    current = dict(get_user_preferences())

    for key, value in updates.items():
        if key == "notes" and isinstance(value, list):
            existing = current.setdefault("notes", [])
            if not isinstance(existing, list):
                existing = []
                current["notes"] = existing
            for note in value:
                if note and note not in existing:
                    existing.append(note)
        elif key == "likes" and isinstance(value, list):
            existing = current.setdefault("likes", [])
            if not isinstance(existing, list):
                existing = []
                current["likes"] = existing
            for item in value:
                if item and item not in existing:
                    existing.append(item)
        elif key == "dislikes" and isinstance(value, list):
            existing = current.setdefault("dislikes", [])
            if not isinstance(existing, list):
                existing = []
                current["dislikes"] = existing
            for item in value:
                if item and item not in existing:
                    existing.append(item)
        elif key == "defaults" and isinstance(value, dict):
            defaults = current.setdefault("defaults", {})
            if isinstance(defaults, dict):
                defaults.update(value)
        else:
            current[key] = value

    store.put("user", "preferences", current)
    return current


def learn_from_user_message(text: str) -> dict[str, Any] | None:
    """Extract and persist preferences when auto_learn is enabled."""
    if not is_auto_learn_enabled():
        return None
    updates = extract_preference_updates(text)
    if not updates:
        return None
    return merge_user_preferences(updates)


def list_learned_summary() -> dict[str, Any]:
    prefs = get_user_preferences()
    cfg = get_memory_settings()
    from memory.chat_recall import get_chat_history_store

    return {
        "auto_learn": cfg.get("auto_learn", False),
        "history_recall": cfg.get("history_recall", True),
        "preferences": prefs,
        "history_stats": get_chat_history_store().stats(),
    }
