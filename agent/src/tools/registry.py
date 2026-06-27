from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.tools import BaseTool


class ToolRegistry:
    """统一工具注册与解析中心。所有工具本地执行，与 LLM Provider 解耦。"""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self._tools: dict[str, BaseTool] = {}
        self._meta: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    def register(
        self, tool: BaseTool, category: str, meta: dict[str, Any] | None = None
    ) -> None:
        self._tools[tool.name] = tool
        self._meta[tool.name] = {**(meta or {}), "category": category}

    def get_tool(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def get_meta(self, name: str) -> dict[str, Any]:
        return self._meta.get(name, {})

    def get_enabled_tools(self, categories: list[str] | None = None) -> list[BaseTool]:
        enabled = []
        for name, tool in self._tools.items():
            cfg = self._find_config(name)
            if not cfg.get("enabled", False):
                continue
            if categories and self._meta[name]["category"] not in categories:
                continue
            enabled.append(tool)
        return enabled

    def _find_config(self, name: str) -> dict[str, Any]:
        for cat in ("capability", "business"):
            if name in self.config.get(cat, {}):
                return self.config[cat][name]
        return {}

    def requires_confirmation(self, tool_name: str) -> bool:
        cfg = self._find_config(tool_name)
        if "requires_confirmation" in cfg:
            return cfg["requires_confirmation"]
        risk = self._meta.get(tool_name, {}).get("risk", "low")
        defaults = self.config.get("defaults", {})
        threshold = defaults.get("requires_confirmation_risk", "medium")
        risk_levels = {"low": 0, "medium": 1, "high": 2}
        return risk_levels.get(risk, 0) >= risk_levels.get(threshold, 1)

    async def resolve_all(self, include_mcp: bool = False) -> list[BaseTool]:
        async with self._lock:
            tools = self.get_enabled_tools()
            if include_mcp:
                from tools.mcp_loader import load_mcp_tools

                mcp_tools = await load_mcp_tools(self.config.get("mcp_servers", {}))
                for tool in mcp_tools:
                    self.register(tool, "mcp", {"risk": "medium"})
                tools = self.get_enabled_tools()
            return tools

    def list_all(self) -> list[dict[str, Any]]:
        result = []
        for name, tool in self._tools.items():
            cfg = self._find_config(name)
            meta = self._meta.get(name, {})
            result.append(
                {
                    "name": name,
                    "description": tool.description,
                    "category": meta.get("category"),
                    "enabled": cfg.get("enabled", False),
                    "risk": meta.get("risk", cfg.get("risk", "low")),
                }
            )
        return result


def build_registry(config: dict[str, Any]) -> ToolRegistry:
    from tools.capability.web_search import create_web_search_tool
    from tools.business.calendar import create_calendar_tools
    from tools.business.todo import create_todo_tools

    registry = ToolRegistry(config)

    ws_cfg = config.get("capability", {}).get("web_search", {})
    if ws_cfg.get("enabled"):
        registry.register(
            create_web_search_tool(ws_cfg),
            "capability",
            {"risk": ws_cfg.get("risk", "low")},
        )

    for tool in create_todo_tools():
        cfg = config.get("business", {}).get(tool.name, {})
        registry.register(tool, "business", {"risk": cfg.get("risk", "low")})

    for tool in create_calendar_tools():
        cfg = config.get("business", {}).get(tool.name, {})
        registry.register(tool, "business", {"risk": cfg.get("risk", "low")})

    return registry
