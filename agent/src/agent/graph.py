from __future__ import annotations

import json
from typing import Any, Callable

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import tools_condition
from langgraph.types import interrupt

from agent.planner import format_plan_for_prompt, generate_task_plan, needs_planning
from agent.state import AgentState
from infra.config import get_data_dir
from llm.factory import get_default_provider
from llm.fallback import create_llm_with_fallback
from memory.rag import RagStore, is_knowledge_query
from memory.store import get_user_preferences
from tools.registry import ToolRegistry


async def create_sqlite_checkpointer():
    """Create AsyncSqliteSaver on the running event loop (required for astream_events)."""
    import aiosqlite
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    checkpoint_dir = get_data_dir() / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    db_path = checkpoint_dir / "checkpoints.db"
    conn = await aiosqlite.connect(str(db_path))
    return AsyncSqliteSaver(conn), conn


def get_checkpointer():
    """In-memory checkpointer for unit tests only."""
    from langgraph.checkpoint.memory import MemorySaver

    return MemorySaver()


_rag_store: RagStore | None = None


def _get_rag_store() -> RagStore:
    global _rag_store
    if _rag_store is None:
        _rag_store = RagStore()
    return _rag_store


def _build_system_prompt(state: AgentState) -> str:
    prefs = get_user_preferences()
    parts = ["You are a helpful personal assistant agent with access to local tools."]

    if prefs:
        parts.append(f"User preferences:\n{json.dumps(prefs, ensure_ascii=False)}")

    task_plan = state.get("task_plan")
    if task_plan:
        parts.append(format_plan_for_prompt(task_plan))

    retrieved = state.get("retrieved_docs")
    if retrieved:
        parts.append(_get_rag_store().format_for_prompt(retrieved))

    return "\n\n".join(parts)


def create_preprocess_node(
    llm: BaseChatModel | None | Callable[[], BaseChatModel | None] = None,
):
    def _resolve_llm() -> BaseChatModel | None:
        if llm is None:
            return None
        return llm() if callable(llm) else llm

    def preprocess(state: AgentState) -> dict[str, Any]:
        messages = state["messages"]
        last_human = None
        for m in reversed(messages):
            if isinstance(m, HumanMessage):
                last_human = m
                break
        if not last_human or not isinstance(last_human.content, str):
            return {}

        content = last_human.content
        updates: dict[str, Any] = {}

        if is_knowledge_query(content):
            docs = _get_rag_store().search(content)
            if docs:
                updates["retrieved_docs"] = docs

        if needs_planning(content):
            updates["task_plan"] = generate_task_plan(content, _resolve_llm())

        return updates

    return preprocess


def create_hitl_tools_node(registry: ToolRegistry):
    def hitl_tools(state: AgentState) -> dict[str, Any]:
        messages = state["messages"]
        last = messages[-1]
        if not hasattr(last, "tool_calls") or not last.tool_calls:
            return {"messages": []}

        result_messages: list[ToolMessage] = []

        for tc in last.tool_calls:
            name = tc["name"]
            args = tc.get("args") or {}
            tool_id = tc.get("id") or name

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
                        result_messages.append(
                            ToolMessage(
                                content=f"用户拒绝了工具 `{name}` 的执行。",
                                tool_call_id=tool_id,
                            )
                        )
                        continue
                    if decision == "edit" and response.get("edited_args"):
                        args = response["edited_args"]

            tool = registry.get_tool(name)
            if not tool:
                result_messages.append(
                    ToolMessage(content=f"Tool not found: {name}", tool_call_id=tool_id)
                )
                continue

            try:
                output = tool.invoke(args)
                result_messages.append(
                    ToolMessage(content=str(output), tool_call_id=tool_id)
                )
            except Exception as e:
                result_messages.append(
                    ToolMessage(content=f"Error executing {name}: {e}", tool_call_id=tool_id)
                )

        return {"messages": result_messages}

    return hitl_tools


def create_reflect_node():
    """Lightweight reflection when tools return errors."""

    def reflect(state: AgentState) -> dict[str, Any]:
        messages = state.get("messages", [])
        for msg in reversed(messages[-4:]):
            if isinstance(msg, ToolMessage):
                content = msg.content or ""
                if content.startswith("Error") or "失败" in content:
                    return {
                        "messages": [
                            HumanMessage(
                                content=(
                                    "[Reflection] 上一步工具执行出现问题。"
                                    "请向用户说明情况并尝试替代方案。"
                                )
                            )
                        ]
                    }
        return {}

    return reflect


class _LazyLlm:
    """Defer LLM creation until first agent turn so Sidecar can start without API keys."""

    def __init__(
        self,
        registry: ToolRegistry,
        llm: BaseChatModel | None = None,
        primary: str | None = None,
    ):
        self._registry = registry
        self._llm = llm
        self._primary = primary or get_default_provider()
        self._provider_name: str | None = self._primary if llm else None
        self._llm_with_tools: BaseChatModel | None = None

    def get(self) -> BaseChatModel:
        if self._llm is None:
            self._llm, self._provider_name = create_llm_with_fallback(self._primary)
            self._llm_with_tools = None
        return self._llm

    def with_tools(self) -> BaseChatModel:
        if self._llm_with_tools is not None:
            return self._llm_with_tools
        tools = self._registry.get_enabled_tools()
        llm = self.get()
        self._llm_with_tools = llm.bind_tools(tools) if tools else llm
        return self._llm_with_tools


def create_agent_graph(
    registry: ToolRegistry,
    checkpointer: BaseCheckpointSaver | None = None,
    llm: BaseChatModel | None = None,
):
    lazy_llm = _LazyLlm(registry, llm=llm)

    def call_model(state: AgentState) -> dict[str, Any]:
        from langchain_core.messages import SystemMessage

        messages = list(state["messages"])
        system_content = _build_system_prompt(state)
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=system_content)] + messages
        else:
            messages[0] = SystemMessage(content=system_content)
        response = lazy_llm.with_tools().invoke(messages)
        return {"messages": [response]}

    workflow = StateGraph(AgentState)
    workflow.add_node("preprocess", create_preprocess_node(lazy_llm.get))
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", create_hitl_tools_node(registry))
    workflow.add_node("reflect", create_reflect_node())
    workflow.add_edge(START, "preprocess")
    workflow.add_edge("preprocess", "agent")
    workflow.add_conditional_edges(
        "agent", tools_condition, {"tools": "tools", END: END}
    )
    workflow.add_edge("tools", "reflect")
    workflow.add_edge("reflect", "agent")

    return workflow.compile(checkpointer=checkpointer)
