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


def load_tools_user_config() -> dict[str, Any]:
    path = get_data_dir() / "tools_user.yaml"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_tools_user_config(data: dict[str, Any]) -> None:
    path = get_data_dir() / "tools_user.yaml"
    get_data_dir().mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False)


def _merge_tool_category(
    base_cat: dict[str, Any], user_cat: dict[str, Any] | None
) -> dict[str, Any]:
    import copy

    merged = copy.deepcopy(base_cat)
    if not isinstance(user_cat, dict):
        return merged
    for name, overrides in user_cat.items():
        if not isinstance(overrides, dict):
            continue
        if name in merged and isinstance(merged[name], dict):
            merged[name] = {**merged[name], **overrides}
        else:
            merged[name] = dict(overrides)
    return merged


def list_configurable_tools() -> list[dict[str, Any]]:
    """Return all user-configurable tools with effective enabled state."""
    base = load_tools_config()
    effective = load_effective_tools_config()
    user = load_tools_user_config()

    from tools.registry import build_registry

    registry = build_registry(effective)
    desc_map = {t["name"]: t for t in registry.list_all()}

    tools: list[dict[str, Any]] = []
    seen: set[str] = set()

    for category in ("capability", "business"):
        base_cat = base.get(category, {}) if isinstance(base.get(category), dict) else {}
        eff_cat = (
            effective.get(category, {}) if isinstance(effective.get(category), dict) else {}
        )
        user_cat = user.get(category, {}) if isinstance(user.get(category), dict) else {}
        names = set(base_cat) | set(user_cat)
        for name in sorted(names):
            if name == "cli_tools" or name in seen:
                continue
            if not isinstance(base_cat.get(name), dict) and name not in user_cat:
                continue
            eff_cfg = eff_cat.get(name, {}) if isinstance(eff_cat.get(name), dict) else {}
            base_cfg = (
                base_cat.get(name, {}) if isinstance(base_cat.get(name), dict) else {}
            )
            enabled = bool(eff_cfg.get("enabled", base_cfg.get("enabled", False)))
            meta = desc_map.get(name, {})
            tools.append(
                {
                    "name": name,
                    "description": meta.get("description", ""),
                    "category": category,
                    "enabled": enabled,
                    "risk": eff_cfg.get("risk", base_cfg.get("risk", "low")),
                    "has_user_override": name in user_cat,
                }
            )
            seen.add(name)

    eff_cap = (
        effective.get("capability", {})
        if isinstance(effective.get("capability"), dict)
        else {}
    )
    bundle_on = bool(eff_cap.get("cli_tools", {}).get("enabled", False))
    if bundle_on or isinstance(user.get("capability"), dict):
        from tools.capability.cli_tools import load_cli_tools_config

        cli_cfg = load_cli_tools_config()
        programs = cli_cfg.get("programs", {})
        user_cap = user.get("capability", {}) if isinstance(user.get("capability"), dict) else {}
        if isinstance(programs, dict):
            for prog in programs.values():
                if not isinstance(prog, dict):
                    continue
                tool_name = str(prog.get("tool_name") or "").strip()
                if not tool_name or tool_name in seen:
                    continue
                per = (
                    eff_cap.get(tool_name, {})
                    if isinstance(eff_cap.get(tool_name), dict)
                    else {}
                )
                prog_enabled = bool(prog.get("enabled", True))
                tool_enabled = bundle_on and prog_enabled and bool(
                    per.get("enabled", True)
                )
                meta = desc_map.get(tool_name, {})
                tools.append(
                    {
                        "name": tool_name,
                        "description": meta.get("description")
                        or str(prog.get("description", "")),
                        "category": "capability",
                        "enabled": tool_enabled,
                        "risk": per.get("risk", prog.get("risk", "low")),
                        "has_user_override": tool_name in user_cap,
                    }
                )
                seen.add(tool_name)

    tools.sort(key=lambda t: (t["category"], t["name"]))
    return tools


def load_effective_tools_config() -> dict[str, Any]:
    """Merge tools.yaml with user overrides from data/tools_user.yaml and mcp_user.yaml."""
    import copy

    cfg = copy.deepcopy(load_tools_config())
    user_tools = load_tools_user_config()
    for cat in ("capability", "business"):
        base_cat = cfg.get(cat, {}) if isinstance(cfg.get(cat), dict) else {}
        user_cat = user_tools.get(cat) if isinstance(user_tools.get(cat), dict) else {}
        if user_cat:
            cfg[cat] = _merge_tool_category(base_cat, user_cat)

    user_mcp = load_mcp_user_config().get("mcp_servers")
    if isinstance(user_mcp, dict) and user_mcp:
        base_mcp = cfg.setdefault("mcp_servers", {})
        for name, overrides in user_mcp.items():
            if not isinstance(overrides, dict):
                continue
            if name in base_mcp and isinstance(base_mcp[name], dict):
                base_mcp[name] = {**base_mcp[name], **overrides}
            else:
                base_mcp[name] = dict(overrides)

    from infra.user_settings import get_web_search_user_override

    ws_override = get_web_search_user_override().get("backend", "")
    if isinstance(ws_override, str) and ws_override.strip():
        cap = cfg.setdefault("capability", {})
        ws_cfg = cap.setdefault("web_search", {})
        if isinstance(ws_cfg, dict):
            ws_cfg["backend"] = ws_override.strip()
    return cfg


def load_effective_app_config() -> dict[str, Any]:
    """Merge app.yaml with user_settings.yaml (hitl, etc.)."""
    import copy

    from infra.user_settings import get_effective_user_settings

    cfg = copy.deepcopy(load_app_config())
    user = get_effective_user_settings()
    if user.get("hitl"):
        cfg["hitl"] = {**cfg.get("hitl", {}), **user["hitl"]}
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


def _resolve_default_provider(cfg: dict[str, Any], custom_ids: list[str]) -> None:
    """Map stale default_provider (e.g. legacy ``custom``) to an existing entry."""
    default = str(cfg.get("default_provider", "deepseek"))
    providers = cfg.get("providers", {})
    if not isinstance(providers, dict) or default in providers:
        return
    if custom_ids:
        cfg["default_provider"] = custom_ids[0]


def load_llm_providers_config() -> dict[str, Any]:
    cfg = load_yaml("llm_providers.yaml")
    user = load_user_llm_config()
    if user.get("default_provider"):
        cfg["default_provider"] = user["default_provider"]
    custom_ids = _merge_custom_providers(cfg, user)
    _resolve_default_provider(cfg, custom_ids)
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

