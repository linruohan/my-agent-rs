from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from agent.graph import create_agent_graph
from agent.runner import AgentRunner
from api.health import get_version
from infra.config import load_effective_tools_config, load_tools_config
from tools.mcp_loader import any_mcp_enabled
from tools.registry import ToolRegistry

router = APIRouter()


def create_tools_router(registry: ToolRegistry, runner: AgentRunner) -> APIRouter:
    tools_router = APIRouter()

    async def _rebuild_graph(request: Request) -> None:
        checkpointer = getattr(request.app.state, "checkpointer", None)
        if checkpointer is not None:
            runner.graph = create_agent_graph(registry, checkpointer)

    @tools_router.get("/tools")
    async def list_tools():
        tools = registry.list_all()
        enabled = [t for t in tools if t.get("enabled")]
        return {"tools": tools, "count": len(tools), "enabled_count": len(enabled)}

    @tools_router.get("/providers")
    async def list_providers():
        from infra.config import load_llm_providers_config
        from llm.fallback import get_fallback_chain

        cfg = load_llm_providers_config()
        return {
            "default": cfg.get("default_provider"),
            "fallback_chain": get_fallback_chain(),
            "providers": list(cfg.get("providers", {}).keys()),
        }

    @tools_router.get("/mcp/status")
    async def mcp_status():
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
