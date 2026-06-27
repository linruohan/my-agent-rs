from __future__ import annotations

import re
from typing import Any

from tools.registry import ToolRegistry


def _tokenize(text: str) -> set[str]:
    return {t for t in re.split(r"\W+", text.lower()) if len(t) > 1}


def search_tools(registry: ToolRegistry, query: str, limit: int = 5) -> list[dict[str, Any]]:
    query_terms = _tokenize(query)
    if not query_terms:
        return registry.list_all()[:limit]

    scored: list[tuple[float, dict[str, Any]]] = []
    for item in registry.list_all():
        if not item.get("enabled"):
            continue
        haystack = " ".join(
            filter(
                None,
                [item.get("name", ""), item.get("description", ""), item.get("category", "")],
            )
        ).lower()
        hay_terms = _tokenize(haystack)
        if not hay_terms:
            continue
        overlap = len(query_terms & hay_terms)
        if overlap == 0 and not any(t in haystack for t in query_terms):
            continue
        score = overlap / len(query_terms)
        scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:limit]]


def create_tool_search_tool(registry: ToolRegistry, config: dict[str, Any]):
    from langchain_core.tools import tool

    limit = config.get("max_results", 5)

    @tool
    def tool_search(query: str) -> str:
        """Search available tools by keyword when unsure which tool to use."""
        results = search_tools(registry, query, limit)
        if not results:
            return "No matching tools found."
        lines = []
        for r in results:
            lines.append(
                f"- {r['name']} [{r['category']}] risk={r['risk']}: {r['description'][:120]}"
            )
        return "\n".join(lines)

    return tool_search
