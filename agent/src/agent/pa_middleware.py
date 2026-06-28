from __future__ import annotations

import asyncio
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from loguru import logger

from agent.hitl_node import build_hitl_awrap_tool_call
from agent.state import AgentState
from llm.fallback import get_fallback_chain
from tools.registry import ToolRegistry

MAX_TOOL_ROUNDS = 6


class PersonalAssistantMiddleware(AgentMiddleware[AgentState, None]):
    """Middleware for preprocess, reflect, provider fallback, dynamic prompt, and HITL."""

    state_schema = AgentState

    def __init__(self, registry: ToolRegistry, lazy_llm: Any):
        self._registry = registry
        self._lazy_llm = lazy_llm
        from agent.graph import create_preprocess_node, create_reflect_node

        self._preprocess = create_preprocess_node(lazy_llm.get)
        self._reflect = create_reflect_node()
        self._hitl_awrap = build_hitl_awrap_tool_call(registry)

    def before_model(self, state: AgentState, runtime) -> dict[str, Any] | None:
        from agent.graph import _state_metadata

        messages = state.get("messages") or []
        updates: dict[str, Any] = {}

        if messages and isinstance(messages[-1], HumanMessage):
            updates.update(self._preprocess(state))
        elif messages and isinstance(messages[-1], ToolMessage):
            meta = _state_metadata(state)
            meta["tool_rounds"] = meta.get("tool_rounds", 0) + 1

            last_tool_msgs: list[ToolMessage] = []
            for msg in reversed(messages):
                if isinstance(msg, ToolMessage):
                    last_tool_msgs.insert(0, msg)
                elif last_tool_msgs:
                    break
            from agent.graph import _is_usable_tool_output

            for tm in last_tool_msgs:
                if _is_usable_tool_output(str(tm.content or "")):
                    meta["has_tool_content"] = True
                    break

            merged = {**state, **updates, "metadata": meta}
            updates.update(self._reflect(merged))

        return updates or None

    async def awrap_model_call(self, request: ModelRequest, handler):
        from agent.graph import (
            _build_system_prompt,
            _messages_with_time_hint,
            _provider_available,
            _state_metadata,
        )

        state = request.state
        meta = _state_metadata(state)
        force_answer = meta.get("force_answer") or meta.get("tool_rounds", 0) >= MAX_TOOL_ROUNDS
        bind_tools = bool(self._registry.get_enabled_tools()) and not force_answer

        system_message = SystemMessage(content=_build_system_prompt(state))
        messages = _messages_with_time_hint(list(state["messages"]))

        chain = get_fallback_chain()
        primary = self._lazy_llm._primary
        if primary and primary not in chain:
            chain = [primary, *[p for p in chain if p != primary]]

        last_error: Exception | None = None
        from langgraph.config import get_config

        config = get_config()
        for name in chain:
            if not _provider_available(name):
                continue
            try:
                self._lazy_llm.reset(name)
                model = self._lazy_llm.with_tools() if bind_tools else self._lazy_llm.get()
                messages_for_invoke = list(messages)
                if system_message:
                    messages_for_invoke = [system_message, *messages_for_invoke]
                coro = model.ainvoke(messages_for_invoke, config)
                if asyncio.iscoroutine(coro):
                    output = await coro
                else:
                    output = await asyncio.to_thread(
                        model.invoke, messages_for_invoke, config
                    )
                self._lazy_llm._provider_name = name
                return ModelResponse(result=[output])
            except (TimeoutError, ConnectionError, OSError) as exc:
                last_error = exc
                logger.warning("Provider {} request failed: {}", name, exc)
            except Exception as exc:
                err_name = type(exc).__name__
                if err_name in ("APITimeoutError", "RateLimitError", "APIConnectionError"):
                    last_error = exc
                    logger.warning("Provider {} API error: {}", name, exc)
                    continue
                raise

        if last_error:
            raise RuntimeError(f"All LLM providers unavailable: {last_error}") from last_error
        raise RuntimeError("All LLM providers unavailable (no API keys configured)")

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        execute,
    ) -> ToolMessage:
        return await self._hitl_awrap(request, execute)


def create_pa_middleware(registry: ToolRegistry, lazy_llm: Any) -> PersonalAssistantMiddleware:
    return PersonalAssistantMiddleware(registry, lazy_llm)
