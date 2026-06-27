from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool


async def load_mcp_tools(cfg: dict[str, Any]) -> list[BaseTool]:
    """Load MCP tools from configured servers. Returns empty list if none enabled."""
    enabled = {k: v for k, v in cfg.items() if v.get("enabled")}
    if not enabled:
        return []
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient

        client = MultiServerMCPClient(enabled)
        return await client.get_tools()
    except ImportError:
        return []
    except Exception:
        return []
