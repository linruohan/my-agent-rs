from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Awaitable, Callable

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from tools.registry import ToolRegistry

EventCallback = Callable[[dict[str, Any]], Awaitable[None]]


class AgentRunner:
    """Runs LangGraph agent and streams events to WebSocket."""

    def __init__(self, graph, registry: ToolRegistry):
        self.graph = graph
        self.registry = registry
        self._active: dict[str, asyncio.Task] = {}

    async def run(
        self,
        thread_id: str,
        content: str,
        emit: EventCallback,
    ) -> None:
        config = {"configurable": {"thread_id": thread_id}}
        start = time.monotonic()

        task = asyncio.current_task()
        if task:
            self._active[thread_id] = task

        try:
            input_state = {"messages": [HumanMessage(content=content)]}
            metadata: dict[str, Any] = {"duration_ms": 0}

            async for event in self.graph.astream_events(
                input_state, config, version="v2"
            ):
                await self._handle_event(event, thread_id, emit)

            # Check for pending interrupts after stream
            state = await self.graph.aget_state(config)
            if state.interrupts:
                for intr in state.interrupts:
                    value = intr.value if hasattr(intr, "value") else intr
                    if isinstance(value, dict):
                        await emit(
                            {
                                "type": "interrupt",
                                "thread_id": thread_id,
                                "action": value.get("action", ""),
                                "preview": value.get("preview", ""),
                                "args": value.get("args", {}),
                            }
                        )
                        from infra.hitl import hitl_timeout_manager

                        hitl_timeout_manager.schedule(thread_id)

            metadata["duration_ms"] = int((time.monotonic() - start) * 1000)
            from infra.hitl import hitl_timeout_manager

            hitl_timeout_manager.cancel(thread_id)
            await emit({"type": "done", "thread_id": thread_id, "metadata": metadata})

        except asyncio.CancelledError:
            await emit(
                {
                    "type": "error",
                    "thread_id": thread_id,
                    "message": "Generation stopped",
                    "code": "CANCELLED",
                }
            )
            raise
        except Exception as e:
            await emit(
                {
                    "type": "error",
                    "thread_id": thread_id,
                    "message": str(e),
                    "code": "PROVIDER_ERROR",
                }
            )
        finally:
            self._active.pop(thread_id, None)

    async def _handle_event(
        self, event: dict[str, Any], thread_id: str, emit: EventCallback
    ) -> None:
        kind = event.get("event")

        if kind == "on_chat_model_stream":
            chunk = event.get("data", {}).get("chunk")
            if chunk and hasattr(chunk, "content") and chunk.content:
                text = chunk.content
                if isinstance(text, list):
                    text = "".join(
                        block.get("text", "") if isinstance(block, dict) else str(block)
                        for block in text
                    )
                if text:
                    await emit(
                        {"type": "token", "thread_id": thread_id, "content": text}
                    )

        elif kind == "on_tool_start":
            tool_name = event.get("name", "")
            meta = self.registry.get_meta(tool_name)
            await emit(
                {
                    "type": "tool_start",
                    "thread_id": thread_id,
                    "name": tool_name,
                    "args": event.get("data", {}).get("input", {}),
                    "category": meta.get("category", "capability"),
                }
            )

        elif kind == "on_tool_end":
            tool_name = event.get("name", "")
            meta = self.registry.get_meta(tool_name)
            output = event.get("data", {}).get("output", "")
            if hasattr(output, "content"):
                output = output.content
            citations = []
            if tool_name == "web_search" and isinstance(output, str):
                citations = _extract_citations(output)
            await emit(
                {
                    "type": "tool_end",
                    "thread_id": thread_id,
                    "name": tool_name,
                    "result": str(output)[:2000],
                    "category": meta.get("category", "capability"),
                    "citations": citations,
                }
            )

        elif kind == "on_chain_stream":
            chunk = event.get("data", {}).get("chunk")
            if isinstance(chunk, dict) and "__interrupt__" in chunk:
                for intr in chunk["__interrupt__"]:
                    value = intr.value if hasattr(intr, "value") else intr
                    if isinstance(value, dict):
                        await emit(
                            {
                                "type": "interrupt",
                                "thread_id": thread_id,
                                "action": value.get("action", ""),
                                "preview": value.get("preview", ""),
                                "args": value.get("args", {}),
                            }
                        )
                        from infra.hitl import hitl_timeout_manager

                        hitl_timeout_manager.schedule(thread_id)

    async def stop(self, thread_id: str) -> bool:
        task = self._active.get(thread_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    async def resume(
        self,
        thread_id: str,
        decision: str,
        edited_args: dict | None,
        emit: EventCallback,
    ) -> None:
        config = {"configurable": {"thread_id": thread_id}}
        resume_value: dict[str, Any] = {"decision": decision}
        if edited_args:
            resume_value["edited_args"] = edited_args

        start = time.monotonic()
        from infra.hitl import hitl_timeout_manager

        hitl_timeout_manager.cancel(thread_id)
        try:
            async for event in self.graph.astream_events(
                Command(resume=resume_value), config, version="v2"
            ):
                await self._handle_event(event, thread_id, emit)

            state = await self.graph.aget_state(config)
            if state.interrupts:
                for intr in state.interrupts:
                    value = intr.value if hasattr(intr, "value") else intr
                    if isinstance(value, dict):
                        await emit(
                            {
                                "type": "interrupt",
                                "thread_id": thread_id,
                                "action": value.get("action", ""),
                                "preview": value.get("preview", ""),
                                "args": value.get("args", {}),
                            }
                        )
                        from infra.hitl import hitl_timeout_manager

                        hitl_timeout_manager.schedule(thread_id)
                return

            metadata = {"duration_ms": int((time.monotonic() - start) * 1000)}
            await emit({"type": "done", "thread_id": thread_id, "metadata": metadata})
        except Exception as e:
            await emit(
                {
                    "type": "error",
                    "thread_id": thread_id,
                    "message": str(e),
                    "code": "PROVIDER_ERROR",
                }
            )


def _extract_citations(text: str) -> list[dict[str, str]]:
    citations = []
    for line in text.split("\n"):
        if line.strip().startswith("Source:"):
            url = line.split("Source:", 1)[1].strip()
            citations.append({"url": url, "title": url})
    return citations
