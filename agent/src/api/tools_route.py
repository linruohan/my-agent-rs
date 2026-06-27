from __future__ import annotations

from fastapi import APIRouter

from api.health import get_version
from tools.registry import ToolRegistry

router = APIRouter()


def create_tools_router(registry: ToolRegistry) -> APIRouter:
    tools_router = APIRouter()

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
        from tools.mcp_loader import any_mcp_enabled

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
    async def reload_tools():
        from infra.config import load_tools_config

        cfg = load_tools_config()
        registry.reload(cfg)
        tools = registry.list_all()
        enabled = [t for t in tools if t.get("enabled")]
        return {
            "ok": True,
            "count": len(tools),
            "enabled_count": len(enabled),
        }

    return tools_router
