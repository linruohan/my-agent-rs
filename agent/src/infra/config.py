from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def get_config_dir() -> Path:
    env_dir = os.environ.get("AGENT_CONFIG_DIR")
    if env_dir:
        return Path(env_dir)
    return Path(__file__).resolve().parents[2] / "config"


def get_data_dir() -> Path:
    env_dir = os.environ.get("AGENT_DATA_DIR")
    if env_dir:
        return Path(env_dir)
    return Path(__file__).resolve().parents[3] / "data"


def load_yaml(name: str) -> dict[str, Any]:
    path = get_config_dir() / name
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_app_config() -> dict[str, Any]:
    cfg = load_yaml("app.yaml")
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    cfg["data_dir"] = str(data_dir)
    return cfg


def load_tools_config() -> dict[str, Any]:
    return load_yaml("tools.yaml")


def load_user_llm_config() -> dict[str, Any]:
    path = get_data_dir() / "llm_user.yaml"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_user_llm_config(data: dict[str, Any]) -> None:
    path = get_data_dir() / "llm_user.yaml"
    get_data_dir().mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False)


def load_llm_providers_config() -> dict[str, Any]:
    cfg = load_yaml("llm_providers.yaml")
    user = load_user_llm_config()
    if user.get("default_provider"):
        cfg["default_provider"] = user["default_provider"]
    custom = user.get("custom")
    if isinstance(custom, dict) and custom:
        providers = cfg.setdefault("providers", {})
        base = providers.get("custom", {})
        if isinstance(base, dict):
            providers["custom"] = {**base, **custom}
    return cfg


def get_workspace_dir() -> Path:
    """Return sandbox workspace for file tools (resolved absolute path)."""
    tools_cfg = load_yaml("tools.yaml")
    raw = (
        tools_cfg.get("capability", {})
        .get("text_editor", {})
        .get("workspace", "")
    )
    if raw:
        path = Path(raw).expanduser()
    else:
        path = get_data_dir() / "workspace"
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def resolve_workspace_path(relative: str) -> Path:
    """Resolve a relative path within workspace; reject path traversal."""
    workspace = get_workspace_dir()
    target = (workspace / relative).resolve()
    if not str(target).startswith(str(workspace)):
        raise ValueError(f"Path escapes workspace: {relative}")
    return target


def load_rag_config() -> dict[str, Any]:
    return load_yaml("rag.yaml")

