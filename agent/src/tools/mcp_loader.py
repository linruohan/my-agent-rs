from __future__ import annotations

import os
import re
from typing import Any

from loguru import logger

from langchain_core.tools import BaseTool

_ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")


def _resolve_env_value(value: str) -> str:
    """Replace ${VAR} placeholders with environment values."""

    def repl(match: re.Match[str]) -> str:
        return os.environ.get(match.group(1), "")

    return _ENV_PATTERN.sub(repl, value)


def _resolve_env_mapping(values: dict[str, Any]) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for key, raw in values.items():
        if raw is None:
            continue
        text = _resolve_env_value(str(raw))
        if text:
            resolved[key] = text
    return resolved


def _normalize_server_config(name: str, cfg: dict[str, Any]) -> dict[str, Any]:
    """Build MultiServerMCPClient-compatible server entry."""
    transport = cfg.get("transport", "stdio")
    entry: dict[str, Any] = {"transport": transport}

    if transport == "stdio":
        entry["command"] = cfg.get("command", "")
        entry["args"] = list(cfg.get("args") or [])
        env = _resolve_env_mapping(cfg.get("env") or {})
        if env:
            entry["env"] = env
    elif transport in {"sse", "http"}:
        entry["url"] = _resolve_env_value(str(cfg.get("url", "")))
    else:
        logger.warning("Unsupported MCP transport for {}: {}", name, transport)
        return {}

    if not entry.get("command") and not entry.get("url"):
        logger.warning("MCP server {} missing command/url", name)
        return {}

    return entry


def any_mcp_enabled(cfg: dict[str, Any]) -> bool:
    return any(v.get("enabled") for v in cfg.values())


async def load_mcp_tools(cfg: dict[str, Any]) -> list[BaseTool]:
    """Load MCP tools from configured servers. Returns empty list if none enabled."""
    enabled = {k: v for k, v in cfg.items() if v.get("enabled")}
    if not enabled:
        return []

    servers: dict[str, Any] = {}
    for name, server_cfg in enabled.items():
        normalized = _normalize_server_config(name, server_cfg)
        if normalized:
            servers[name] = normalized

    if not servers:
        return []

    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError:
        logger.warning("langchain-mcp-adapters not installed; skip MCP tools")
        return []

    try:
        client = MultiServerMCPClient(servers)
        tools = await client.get_tools()
        logger.info("Loaded {} MCP tools from {}", len(tools), list(servers.keys()))
        return tools
    except Exception as exc:
        logger.error("Failed to load MCP tools: {}", exc)
        return []
