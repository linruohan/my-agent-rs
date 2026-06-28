from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from infra.config import (
    load_effective_tools_config,
    load_mcp_user_config,
    load_tools_config,
    save_mcp_user_config,
    load_user_llm_config,
    save_user_llm_config,
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


class WorkspaceConfigBody(BaseModel):
    workspace: str = Field(min_length=1)


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


@router.get("/config/workspace")
async def get_workspace_config():
    from infra.config import get_workspace_dir

    return {"workspace": str(get_workspace_dir())}


@router.put("/config/workspace")
async def put_workspace_config(body: WorkspaceConfigBody):
    from infra.config import get_workspace_dir
    from infra.user_settings import load_user_settings, save_user_settings

    settings = load_user_settings()
    settings["workspace"] = body.workspace.strip()
    save_user_settings(settings)
    return {"ok": True, "workspace": str(get_workspace_dir())}
