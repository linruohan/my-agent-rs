from __future__ import annotations

from typing import Any

import yaml

from infra.config import get_data_dir

USER_SETTINGS_PATH = get_data_dir() / "user_settings.yaml"

DEFAULTS: dict[str, Any] = {
    "hitl": {
        "timeout_sec": 300,
        "on_timeout": "reject",
        "notify_before_sec": 30,
    },
    "llm": {
        "temperature": 0.7,
        "max_tokens": 4096,
    },
    "web_search": {
        "backend": "",
    },
    "conversation": {
        "max_history_messages": 50,
        "auto_title": True,
    },
    "memory": {
        "auto_learn": False,
        "history_recall": True,
        "history_similarity_min": 0.72,
        "history_max_age_days": 90,
    },
    "notifications": {
        "desktop_enabled": True,
        "sound_enabled": False,
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_user_settings() -> dict[str, Any]:
    if not USER_SETTINGS_PATH.is_file():
        return {}
    with USER_SETTINGS_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_user_settings(data: dict[str, Any]) -> None:
    USER_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with USER_SETTINGS_PATH.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False)


def get_effective_user_settings() -> dict[str, Any]:
    return _deep_merge(DEFAULTS, load_user_settings())


def get_hitl_settings() -> dict[str, Any]:
    return get_effective_user_settings().get("hitl", DEFAULTS["hitl"])


def get_llm_runtime_settings() -> dict[str, Any]:
    return get_effective_user_settings().get("llm", DEFAULTS["llm"])


def get_web_search_user_override() -> dict[str, Any]:
    return get_effective_user_settings().get("web_search", DEFAULTS["web_search"])


def get_conversation_settings() -> dict[str, Any]:
    return get_effective_user_settings().get("conversation", DEFAULTS["conversation"])


def get_memory_settings() -> dict[str, Any]:
    return get_effective_user_settings().get("memory", DEFAULTS["memory"])


def get_notification_settings() -> dict[str, Any]:
    return get_effective_user_settings().get("notifications", DEFAULTS["notifications"])
