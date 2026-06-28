from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from agent.graph import create_agent_graph
from agent.runner import AgentRunner
from api.health import get_version
from infra.config import load_effective_tools_config, load_tools_config, list_configurable_tools
from tools.mcp_loader import any_mcp_enabled
from tools.registry import ToolRegistry

router = APIRouter()


def build_tools_payload(registry: ToolRegistry) -> dict[str, Any]:
    tools = list_configurable_tools()
    enabled = [t for t in tools if t.get("enabled")]
    return {"tools": tools, "count": len(tools), "enabled_count": len(enabled)}


def build_mcp_payload(registry: ToolRegistry) -> dict[str, Any]:
    cfg = registry.config.get("mcp_servers", {})
    mcp_tools = [t for t in registry.list_all() if t.get("category") == "mcp"]
    return {
        "version": get_version(),
        "configured": {
            name: {
                "enabled": server.get("enabled", False),
                "transport": server.get("transport", "stdio"),
            }
            for name, server in cfg.items()
        },
        "any_enabled": any_mcp_enabled(cfg),
        "loaded_count": len(mcp_tools),
        "tools": mcp_tools,
    }


def create_tools_router(registry: ToolRegistry, runner: AgentRunner) -> APIRouter:
    tools_router = APIRouter()

    async def _rebuild_graph(request: Request) -> None:
        checkpointer = getattr(request.app.state, "checkpointer", None)
        if checkpointer is not None:
            runner.graph = create_agent_graph(registry, checkpointer)

    @tools_router.get("/bootstrap")
    async def bootstrap():
        from api.health import build_health_payload

        return {
            "health": build_health_payload(),
            "tools": build_tools_payload(registry),
            "mcp": build_mcp_payload(registry),
        }

    @tools_router.get("/tools")
    async def list_tools():
        return build_tools_payload(registry)

    @tools_router.get("/providers")
    async def list_providers():
        from infra.config import load_llm_providers_config
        from llm.fallback import get_fallback_chain

        cfg = load_llm_providers_config()
        raw = cfg.get("providers", {})
        items = []
        if isinstance(raw, dict):
            for name, pcfg in raw.items():
                if not isinstance(pcfg, dict):
                    continue
                items.append(
                    {
                        "id": name,
                        "label": pcfg.get("label") or name,
                        "type": pcfg.get("type", "openai_compatible"),
                        "model": pcfg.get("model", ""),
                        "base_url": pcfg.get("base_url", ""),
                        "is_custom": bool(pcfg.get("is_custom")),
                    }
                )
        return {
            "default": cfg.get("default_provider"),
            "fallback_chain": get_fallback_chain(),
            "providers": items,
        }

    @tools_router.get("/providers/{provider_name}/models")
    async def list_provider_models_endpoint(provider_name: str, test: bool = False):
        from llm.models import list_provider_models

        return await list_provider_models(provider_name, test=test)

    class PreviewModelsBody(BaseModel):
        base_url: str = Field(min_length=1)
        api_key: str | None = None
        provider_id: str | None = None

    @tools_router.post("/providers/preview/models")
    async def preview_provider_models(body: PreviewModelsBody, test: bool = False):
        import httpx

        from llm.models import (
            list_openai_compatible_models,
            test_openai_compatible_models,
            _api_key_for_provider,
        )
        from llm.factory import load_provider

        api_key = (body.api_key or "").strip()
        if not api_key and body.provider_id:
            try:
                cfg = load_provider(body.provider_id.strip())
                api_key = _api_key_for_provider(cfg)
            except ValueError:
                api_key = ""
        if not api_key:
            raise HTTPException(status_code=400, detail="请填写 API Key 或先保存密钥")

        try:
            models = await list_openai_compatible_models(body.base_url, api_key)
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300] if exc.response else str(exc)
            raise HTTPException(
                status_code=400,
                detail=f"上游 API 错误 {exc.response.status_code}: {detail}",
            ) from exc
        except httpx.RequestError as exc:
            raise HTTPException(status_code=400, detail=f"无法连接 API: {exc}") from exc

        result: dict[str, Any] = {"models": models, "source": "api" if models else "empty"}
        if test and models:
            result["tests"] = await test_openai_compatible_models(
                body.base_url, api_key, models
            )
        return result

    @tools_router.get("/mcp/status")
    async def mcp_status():
        return build_mcp_payload(registry)

    @tools_router.post("/tools/reload")
    async def reload_tools(request: Request):
        from infra.config import load_effective_tools_config

        cfg = load_effective_tools_config()
        registry.config = cfg
        registry.reload(cfg)
        if any_mcp_enabled(cfg.get("mcp_servers", {})):
            await registry.resolve_all(include_mcp=True)
        await _rebuild_graph(request)
        tools = registry.list_all()
        enabled = [t for t in tools if t.get("enabled")]
        return {
            "ok": True,
            "count": len(tools),
            "enabled_count": len(enabled),
            "mcp_loaded": len([t for t in tools if t.get("category") == "mcp"]),
        }

    return tools_router
