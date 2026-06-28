from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml


def provider_api_key_env(provider_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9]", "_", provider_id).upper()
    return f"PA_{safe}_API_KEY"


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


def load_mcp_user_config() -> dict[str, Any]:
    path = get_data_dir() / "mcp_user.yaml"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_mcp_user_config(data: dict[str, Any]) -> None:
    path = get_data_dir() / "mcp_user.yaml"
    get_data_dir().mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False)


def load_effective_tools_config() -> dict[str, Any]:
    """Merge tools.yaml with user MCP overrides from data/mcp_user.yaml."""
    cfg = load_tools_config()
    user = load_mcp_user_config()
    user_mcp = user.get("mcp_servers")
    if isinstance(user_mcp, dict) and user_mcp:
        base_mcp = cfg.setdefault("mcp_servers", {})
        for name, overrides in user_mcp.items():
            if not isinstance(overrides, dict):
                continue
            if name in base_mcp and isinstance(base_mcp[name], dict):
                base_mcp[name] = {**base_mcp[name], **overrides}
            else:
                base_mcp[name] = dict(overrides)
    return cfg


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


def _normalize_custom_providers(user: dict[str, Any]) -> list[dict[str, str]]:
    raw = user.get("custom_providers")
    items: list[dict[str, str]] = []
    if isinstance(raw, list):
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            id_ = str(entry.get("id", "")).strip()
            name = str(entry.get("name", "")).strip()
            base_url = str(entry.get("base_url", "")).strip()
            model = str(entry.get("model", "")).strip()
            if not id_ or not base_url or not model:
                continue
            items.append(
                {
                    "id": id_,
                    "name": name or id_,
                    "base_url": base_url,
                    "model": model,
                }
            )
    if items:
        return items

    legacy = user.get("custom")
    if isinstance(legacy, dict) and legacy.get("base_url") and legacy.get("model"):
        return [
            {
                "id": "custom",
                "name": str(legacy.get("name", "自定义网关")),
                "base_url": str(legacy["base_url"]).strip(),
                "model": str(legacy["model"]).strip(),
            }
        ]
    return []


def _merge_custom_providers(cfg: dict[str, Any], user: dict[str, Any]) -> list[str]:
    entries = _normalize_custom_providers(user)
    providers = cfg.setdefault("providers", {})
    custom_ids: list[str] = []
    for entry in entries:
        id_ = entry["id"]
        custom_ids.append(id_)
        providers[id_] = {
            "label": entry["name"],
            "type": "openai_compatible",
            "base_url": entry["base_url"],
            "model": entry["model"],
            "api_key_env": "CUSTOM_API_KEY" if id_ == "custom" else provider_api_key_env(id_),
            "supports_tool_call": True,
            "timeout_sec": 60,
            "max_retries": 2,
            "is_custom": True,
        }
    if custom_ids and isinstance(providers, dict):
        template = providers.get("custom")
        if isinstance(template, dict) and template.get("is_custom") is not True:
            providers.pop("custom", None)
    return custom_ids


def load_llm_providers_config() -> dict[str, Any]:
    cfg = load_yaml("llm_providers.yaml")
    user = load_user_llm_config()
    if user.get("default_provider"):
        cfg["default_provider"] = user["default_provider"]
    _merge_custom_providers(cfg, user)
    provider_models = user.get("provider_models")
    if isinstance(provider_models, dict):
        providers = cfg.setdefault("providers", {})
        for name, model in provider_models.items():
            if not isinstance(name, str) or not isinstance(model, str) or not model.strip():
                continue
            if name in providers and isinstance(providers[name], dict):
                providers[name] = {**providers[name], "model": model.strip()}
    return cfg


def get_workspace_dir() -> Path:
    """Return sandbox workspace for file tools (resolved absolute path)."""
    from infra.user_settings import load_user_settings

    raw = str(load_user_settings().get("workspace") or "").strip()
    if not raw:
        tools_cfg = load_yaml("tools.yaml")
        raw = str(
            tools_cfg.get("capability", {})
            .get("text_editor", {})
            .get("workspace", "")
        ).strip()
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

