from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool


class ToolRegistry:
    """统一工具注册与解析中心。所有工具本地执行，与 LLM Provider 解耦。"""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self._tools: dict[str, BaseTool] = {}
        self._meta: dict[str, dict[str, Any]] = {}
        self._lock = __import__("asyncio").Lock()

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

    def _tool_entry(self, name: str, tool: BaseTool) -> dict[str, Any]:
        meta = self._meta.get(name, {})
        category = meta.get("category", "")
        if category == "mcp":
            cfg = {"enabled": True, "risk": meta.get("risk", "medium")}
        else:
            cfg = self._find_config(name)
        return {
            "name": name,
            "description": tool.description or "",
            "category": category,
            "enabled": cfg.get("enabled", False),
            "risk": meta.get("risk", cfg.get("risk", "low")),
        }

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
        return [self._tool_entry(name, tool) for name, tool in self._tools.items()]

    def reload(self, config: dict[str, Any] | None = None) -> None:
        """Hot-reload tools from config (capability + business, not MCP)."""
        if config is not None:
            self.config = config
        self._tools.clear()
        self._meta.clear()
        _register_capability(self, self.config)
        _register_business(self, self.config)


def _register_capability(registry: ToolRegistry, config: dict[str, Any]) -> None:
    cap = config.get("capability", {})

    if cap.get("web_search", {}).get("enabled"):
        from tools.capability.web_search import create_web_search_tool

        cfg = cap["web_search"]
        registry.register(
            create_web_search_tool(cfg), "capability", {"risk": cfg.get("risk", "low")}
        )

    if cap.get("web_fetch", {}).get("enabled"):
        from tools.capability.web_fetch import create_web_fetch_tool

        cfg = cap["web_fetch"]
        registry.register(
            create_web_fetch_tool(cfg), "capability", {"risk": cfg.get("risk", "low")}
        )

    if cap.get("text_editor", {}).get("enabled"):
        from tools.capability.text_editor import create_text_editor_tool

        cfg = cap["text_editor"]
        registry.register(
            create_text_editor_tool(cfg),
            "capability",
            {"risk": cfg.get("risk", "medium")},
        )

    if cap.get("code_execution", {}).get("enabled"):
        from tools.capability.code_sandbox import create_code_execution_tool

        cfg = cap["code_execution"]
        registry.register(
            create_code_execution_tool(cfg),
            "capability",
            {"risk": cfg.get("risk", "high")},
        )

    if cap.get("bash", {}).get("enabled"):
        from tools.capability.bash import create_bash_tool

        cfg = cap["bash"]
        registry.register(
            create_bash_tool(cfg), "capability", {"risk": cfg.get("risk", "high")}
        )

    if cap.get("computer", {}).get("enabled"):
        from tools.capability.computer import create_computer_tool

        cfg = cap["computer"]
        registry.register(
            create_computer_tool(cfg), "capability", {"risk": cfg.get("risk", "high")}
        )

    if cap.get("tool_search", {}).get("enabled"):
        from tools.capability.tool_search import create_tool_search_tool

        cfg = cap["tool_search"]
        registry.register(
            create_tool_search_tool(registry, cfg),
            "capability",
            {"risk": cfg.get("risk", "low")},
        )


def _register_business(registry: ToolRegistry, config: dict[str, Any]) -> None:
    from tools.business.calendar import create_calendar_tools
    from tools.business.email import create_email_tools
    from tools.business.file import create_file_tools
    from tools.business.notes import create_notes_tools
    from tools.business.todo import create_todo_tools

    factories = [
        create_todo_tools,
        create_calendar_tools,
        create_file_tools,
        create_notes_tools,
        create_email_tools,
    ]
    for factory in factories:
        for tool in factory():
            cfg = config.get("business", {}).get(tool.name, {})
            registry.register(tool, "business", {"risk": cfg.get("risk", "low")})


def build_registry(config: dict[str, Any]) -> ToolRegistry:
    registry = ToolRegistry(config)
    _register_capability(registry, config)
    _register_business(registry, config)
    return registry
