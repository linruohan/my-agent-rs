from __future__ import annotations

import json
import time

from langchain_core.messages import ToolMessage
from langgraph.prebuilt import ToolNode
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import interrupt
from loguru import logger

from tools.registry import ToolRegistry

_PROGRESS_TOOLS = frozenset(
    {
        "code_execution",
        "bash",
        "web_fetch",
        "web_search",
        "baidu_image_search",
        "computer",
    }
)


def _extract_tool_citations(tool_name: str, output: str) -> list[dict[str, str]]:
    if tool_name not in ("web_search", "baidu_image_search"):
        return []
    citations = []
    for line in output.split("\n"):
        if line.strip().startswith("Source:"):
            url = line.split("Source:", 1)[1].strip()
            citations.append({"url": url, "title": url})
    return citations


def build_hitl_awrap_tool_call(registry: ToolRegistry):
    """Build awrap_tool_call handler for HITL, WS events, and metrics."""

    async def awrap_tool_call(
        request: ToolCallRequest,
        execute,
    ) -> ToolMessage:
        call = request.tool_call
        name = call["name"]
        args = dict(call.get("args") or {})
        tool_id = call.get("id") or name
        config = request.runtime.config
        emit = config.get("configurable", {}).get("_emit")
        thread_id = config.get("configurable", {}).get("thread_id", "")
        meta = registry.get_meta(name)

        if emit:
            await emit(
                {
                    "type": "tool_start",
                    "thread_id": thread_id,
                    "tool_call_id": tool_id,
                    "name": name,
                    "args": args,
                    "category": meta.get("category", "capability"),
                }
            )

        if registry.requires_confirmation(name):
            response = interrupt(
                {
                    "action": name,
                    "preview": (
                        f"确认执行工具 `{name}`？\n"
                        f"参数: {json.dumps(args, ensure_ascii=False, indent=2)}"
                    ),
                    "args": args,
                }
            )
            if isinstance(response, dict):
                decision = response.get("decision", "reject")
                if decision == "reject":
                    content = f"用户拒绝了工具 `{name}` 的执行。"
                    if emit:
                        await emit(
                            {
                                "type": "tool_end",
                                "thread_id": thread_id,
                                "tool_call_id": tool_id,
                                "name": name,
                                "result": content,
                                "category": meta.get("category", "capability"),
                                "citations": [],
                            }
                        )
                    return ToolMessage(content=content, tool_call_id=tool_id)
                if decision == "edit" and response.get("edited_args"):
                    args = response["edited_args"]
                    call = {**call, "args": args}
                    request = request.override(tool_call=call)

        if not registry.get_tool(name):
            err = f"Tool not found: {name}"
            if emit:
                await emit(
                    {
                        "type": "tool_end",
                        "thread_id": thread_id,
                        "tool_call_id": tool_id,
                        "name": name,
                        "result": err,
                        "category": meta.get("category", "capability"),
                        "citations": [],
                    }
                )
            return ToolMessage(content=err, tool_call_id=tool_id)

        if emit and name in _PROGRESS_TOOLS:
            await emit(
                {
                    "type": "tool_progress",
                    "thread_id": thread_id,
                    "tool_call_id": tool_id,
                    "tool_name": name,
                    "status": "executing",
                }
            )

        tool_start = time.monotonic()
        try:
            from infra.tracing import trace_span

            with trace_span("tool.invoke", tool=name, thread_id=thread_id):
                result = await execute(request)
            if isinstance(result, ToolMessage):
                output_str = str(result.content or "")
            else:
                output_str = str(result)
            tool_ms = int((time.monotonic() - tool_start) * 1000)
            from infra.metrics import observe_tool_duration

            observe_tool_duration(tool_ms, success=True)
            logger.info(
                "tool_end name={} duration_ms={} thread_id={}",
                name,
                tool_ms,
                thread_id,
            )
            citations = _extract_tool_citations(name, output_str)
            if emit:
                await emit(
                    {
                        "type": "tool_end",
                        "thread_id": thread_id,
                        "tool_call_id": tool_id,
                        "name": name,
                        "result": output_str[:2000],
                        "category": meta.get("category", "capability"),
                        "citations": citations,
                    }
                )
            if isinstance(result, ToolMessage):
                return result
            return ToolMessage(content=output_str, tool_call_id=tool_id)
        except Exception as exc:
            err = f"Error executing {name}: {exc}"
            from infra.metrics import observe_tool_duration

            observe_tool_duration(0, success=False)
            if emit:
                await emit(
                    {
                        "type": "tool_end",
                        "thread_id": thread_id,
                        "tool_call_id": tool_id,
                        "name": name,
                        "result": err,
                        "category": meta.get("category", "capability"),
                        "citations": [],
                    }
                )
            return ToolMessage(content=err, tool_call_id=tool_id)

    return awrap_tool_call


def create_hitl_tool_node(registry: ToolRegistry) -> ToolNode:
    """ToolNode with HITL confirmation, WS events, and metrics."""
    return ToolNode(
        registry.get_enabled_tools(),
        awrap_tool_call=build_hitl_awrap_tool_call(registry),
    )
