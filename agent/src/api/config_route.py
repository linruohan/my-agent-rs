from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from infra.config import (
    list_configurable_tools,
    load_effective_tools_config,
    load_mcp_user_config,
    load_tools_config,
    load_tools_user_config,
    save_mcp_user_config,
    save_tools_user_config,
    load_user_llm_config,
    save_user_llm_config,
)
from infra.user_settings import (
    get_effective_user_settings,
    load_user_settings,
    save_user_settings,
)

router = APIRouter()


class CustomProviderConfig(BaseModel):
    base_url: str = Field(min_length=1)
    model: str = Field(min_length=1)


class CustomProviderEntry(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    base_url: str = Field(min_length=1)
    model: str = Field(min_length=1)


class LlmUserConfigBody(BaseModel):
    default_provider: str = Field(min_length=1)
    custom: CustomProviderConfig | None = None
    custom_providers: list[CustomProviderEntry] | None = None
    provider_models: dict[str, str] | None = None


class McpServerOverride(BaseModel):
    enabled: bool = False


class McpConfigBody(BaseModel):
    servers: dict[str, McpServerOverride] = Field(default_factory=dict)


class ToolOverride(BaseModel):
    enabled: bool


class ToolsConfigBody(BaseModel):
    capability: dict[str, ToolOverride] = Field(default_factory=dict)
    business: dict[str, ToolOverride] = Field(default_factory=dict)


class WorkspaceConfigBody(BaseModel):
    workspace: str = Field(min_length=1)


class HitlSettingsBody(BaseModel):
    timeout_sec: int = Field(ge=30, le=3600)
    on_timeout: str = Field(default="reject")
    notify_before_sec: int = Field(default=30, ge=0, le=600)


class LlmRuntimeBody(BaseModel):
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=4096, ge=256, le=128000)


class WebSearchSettingsBody(BaseModel):
    backend: str = ""


class ConversationSettingsBody(BaseModel):
    max_history_messages: int = Field(default=50, ge=10, le=500)
    auto_title: bool = True


class MemorySettingsBody(BaseModel):
    auto_learn: bool = False
    history_recall: bool = True
    history_similarity_min: float = Field(default=0.72, ge=0.5, le=1.0)
    history_max_age_days: int = Field(default=90, ge=1, le=36500)


class NotificationSettingsBody(BaseModel):
    desktop_enabled: bool = True
    sound_enabled: bool = False


class UserSettingsBody(BaseModel):
    hitl: HitlSettingsBody | None = None
    llm: LlmRuntimeBody | None = None
    web_search: WebSearchSettingsBody | None = None
    conversation: ConversationSettingsBody | None = None
    memory: MemorySettingsBody | None = None
    notifications: NotificationSettingsBody | None = None


@router.get("/config/llm")
async def get_llm_user_config():
    return load_user_llm_config()


@router.put("/config/llm")
async def put_llm_user_config(body: LlmUserConfigBody):
    data: dict[str, Any] = {"default_provider": body.default_provider}
    if body.custom_providers:
        data["custom_providers"] = [entry.model_dump() for entry in body.custom_providers]
    elif body.default_provider == "custom" and body.custom:
        data["custom"] = body.custom.model_dump()
    if body.provider_models:
        data["provider_models"] = {
            k: v.strip()
            for k, v in body.provider_models.items()
            if isinstance(k, str) and isinstance(v, str) and v.strip()
        }
    save_user_llm_config(data)
    return {"ok": True, **data}


@router.get("/config/mcp")
async def get_mcp_config():
    base = load_tools_config().get("mcp_servers", {})
    user = load_mcp_user_config().get("mcp_servers", {})
    merged: dict[str, Any] = {}
    for name in set(base) | set(user):
        b = base.get(name, {}) if isinstance(base.get(name), dict) else {}
        u = user.get(name, {}) if isinstance(user.get(name), dict) else {}
        merged[name] = {
            "enabled": u.get("enabled", b.get("enabled", False)),
            "transport": b.get("transport", "stdio"),
            "command": b.get("command", ""),
        }
    return {"servers": merged}


@router.put("/config/mcp")
async def put_mcp_config(body: McpConfigBody):
    payload = {
        "mcp_servers": {
            name: {"enabled": server.enabled}
            for name, server in body.servers.items()
        }
    }
    save_mcp_user_config(payload)
    effective = load_effective_tools_config()
    return {
        "ok": True,
        "servers": effective.get("mcp_servers", {}),
    }


@router.get("/config/tools")
async def get_tools_config():
    tools = list_configurable_tools()
    enabled = [t for t in tools if t.get("enabled")]
    return {
        "tools": tools,
        "count": len(tools),
        "enabled_count": len(enabled),
        "user_overrides": load_tools_user_config(),
    }


@router.put("/config/tools")
async def put_tools_config(body: ToolsConfigBody):
    base = load_tools_config()
    payload: dict[str, Any] = {}
    for cat in ("capability", "business"):
        incoming = getattr(body, cat, {})
        if not incoming:
            continue
        base_cat = base.get(cat, {}) if isinstance(base.get(cat), dict) else {}
        merged_cat: dict[str, Any] = {}
        for name, override in incoming.items():
            base_cfg = base_cat.get(name, {}) if isinstance(base_cat.get(name), dict) else {}
            default_enabled = bool(base_cfg.get("enabled", True))
            if override.enabled != default_enabled:
                merged_cat[name] = {"enabled": override.enabled}
        if merged_cat:
            payload[cat] = merged_cat
    save_tools_user_config(payload)
    tools = list_configurable_tools()
    enabled = [t for t in tools if t.get("enabled")]
    return {
        "ok": True,
        "tools": tools,
        "count": len(tools),
        "enabled_count": len(enabled),
    }


@router.get("/config/workspace")
async def get_workspace_config():
    from infra.config import get_workspace_dir

    return {"workspace": str(get_workspace_dir())}


@router.put("/config/workspace")
async def put_workspace_config(body: WorkspaceConfigBody):
    from infra.config import get_workspace_dir

    settings = load_user_settings()
    settings["workspace"] = body.workspace.strip()
    save_user_settings(settings)
    return {"ok": True, "workspace": str(get_workspace_dir())}


@router.get("/config/user")
async def get_user_app_config():
    return get_effective_user_settings()


@router.put("/config/user")
async def put_user_app_config(body: UserSettingsBody):
    settings = load_user_settings()
    payload = body.model_dump(exclude_none=True)
    for key, value in payload.items():
        if isinstance(value, dict) and isinstance(settings.get(key), dict):
            settings[key] = {**settings[key], **value}
        else:
            settings[key] = value
    save_user_settings(settings)
    from infra.hitl import hitl_timeout_manager

    hitl_timeout_manager._reload_config()
    return {"ok": True, **get_effective_user_settings()}


@router.get("/memory/summary")
async def get_memory_summary():
    from memory.learner import list_learned_summary

    return list_learned_summary()
