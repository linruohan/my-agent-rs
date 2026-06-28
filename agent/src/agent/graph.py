from __future__ import annotations

import json
from typing import Any, Callable

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import tools_condition
from langgraph.types import interrupt, RunnableConfig

from agent.planner import format_plan_for_prompt, generate_task_plan, needs_planning
from agent.state import AgentState
from infra.config import get_data_dir, load_effective_tools_config
from infra.time_context import (
    format_current_time_context,
    format_user_turn_time_hint,
    is_fresh_info_query,
)
from llm.factory import get_default_provider
from llm.fallback import create_llm_with_fallback, invoke_with_fallback
from memory.rag import RagStore, is_knowledge_query
from memory.store import get_user_preferences
from tools.registry import ToolRegistry

MAX_TOOL_ROUNDS = 6

_TOOL_FAILURE_MARKERS = (
    "Error executing",
    "Web search failed",
    "No results found.",
    "用户拒绝了工具",
    "Tool not found",
)


def _state_metadata(state: AgentState) -> dict[str, Any]:
    return dict(state.get("metadata") or {})


def _is_usable_tool_output(content: str) -> bool:
    if not content or len(content) < 120:
        return False
    lower = content.lower()
    return not any(marker.lower() in lower for marker in _TOOL_FAILURE_MARKERS)


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
    parts = [
        format_current_time_context(),
        "You are a helpful personal assistant agent with access to local tools.",
        (
            "Tool use: Do not call the same tool with the same arguments repeatedly. "
            "If web_fetch already returned page content, answer the user immediately. "
            "If web_search failed, try web_fetch on one known official URL once, then answer. "
            "For local code/files use glob to find paths, grep to search contents, list_dir to browse, "
            "and text_editor or read_file to read or edit. "
            "External CLI tools (git, jq, tree, bat, pandoc, ffmpeg, etc.) are available when installed on PATH."
        ),
    ]

    meta = state.get("metadata") or {}
    if meta.get("force_answer"):
        parts.append(
            "IMPORTANT: Stop calling tools. Answer the user now using tool results "
            "already in this conversation."
        )

    if prefs:
        parts.append(f"User preferences:\n{json.dumps(prefs, ensure_ascii=False)}")

    task_plan = state.get("task_plan")
    if task_plan:
        parts.append(format_plan_for_prompt(task_plan))

    retrieved = state.get("retrieved_docs")
    if retrieved:
        parts.append(_get_rag_store().format_for_prompt(retrieved))

    fresh = state.get("fresh_search_results")
    if fresh:
        parts.append(
            "Pre-fetched web search results for this question (prefer over training memory). "
            "Do NOT call web_search again — answer using these results:\n"
            f"{fresh}"
        )

    return "\n\n".join(parts)


def _prefetch_web_context(query: str) -> str | None:
    from infra.weather_context import fetch_weather_for_query, is_weather_query

    if is_weather_query(query):
        weather = fetch_weather_for_query(query)
        if weather:
            return weather

    tools_cfg = load_effective_tools_config()
    ws_cfg = tools_cfg.get("capability", {}).get("web_search", {})
    if not ws_cfg.get("enabled", True):
        return None
    try:
        from tools.capability.web_search import format_results_with_citations, run_web_search

        results = run_web_search(query, ws_cfg)
        if not results:
            return None
        text, _ = format_results_with_citations(results)
        return text
    except Exception:
        return None


def _messages_for_llm(state: AgentState) -> list:
    from langchain_core.messages import SystemMessage

    messages = list(state["messages"])
    system_content = _build_system_prompt(state)
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=system_content)] + messages
    else:
        messages[0] = SystemMessage(content=system_content)

    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            raw = messages[i].content
            if isinstance(raw, str):
                messages[i] = HumanMessage(
                    content=raw + format_user_turn_time_hint(raw),
                    id=getattr(messages[i], "id", None),
                )
            break
    return messages


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

        from infra.weather_context import is_weather_query

        if is_weather_query(content) or is_fresh_info_query(content):
            if is_weather_query(content):
                updates["task_plan"] = [
                    "确认系统提示中的当前日期",
                    "使用预抓取的中国天气网数据回答用户",
                    "若预抓取数据不足，再调用 web_fetch 补充",
                ]
            else:
                updates["task_plan"] = [
                    "确认系统提示中的当前日期",
                    "使用 web_search 或预检索结果获取最新信息",
                    "结合检索结果回答用户",
                ]
            prefetched = _prefetch_web_context(content)
            updates["fresh_search_results"] = prefetched
        else:
            updates["fresh_search_results"] = None

        meta = _state_metadata(state)
        meta.update(
            {
                "tool_rounds": 0,
                "force_answer": False,
                "has_tool_content": False,
            }
        )
        updates["metadata"] = meta
        return updates

    return preprocess


_PROGRESS_TOOLS = frozenset(
    {"code_execution", "bash", "web_fetch", "web_search", "computer"}
)


def create_hitl_tools_node(registry: ToolRegistry):
    async def hitl_tools(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        emit = config.get("configurable", {}).get("_emit")
        messages = state["messages"]
        last = messages[-1]
        if not hasattr(last, "tool_calls") or not last.tool_calls:
            return {"messages": []}

        result_messages: list[ToolMessage] = []

        for tc in last.tool_calls:
            name = tc["name"]
            args = tc.get("args") or {}
            tool_id = tc.get("id") or name
            meta = registry.get_meta(name)

            if emit:
                await emit(
                    {
                        "type": "tool_start",
                        "thread_id": config.get("configurable", {}).get("thread_id", ""),
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
                        result_messages.append(
                            ToolMessage(
                                content=f"用户拒绝了工具 `{name}` 的执行。",
                                tool_call_id=tool_id,
                            )
                        )
                        if emit:
                            await emit(
                                {
                                    "type": "tool_end",
                                    "thread_id": config.get("configurable", {}).get(
                                        "thread_id", ""
                                    ),
                                    "tool_call_id": tool_id,
                                    "name": name,
                                    "result": f"用户拒绝了工具 `{name}` 的执行。",
                                    "category": meta.get("category", "capability"),
                                    "citations": [],
                                }
                            )
                        continue
                    if decision == "edit" and response.get("edited_args"):
                        args = response["edited_args"]

            tool = registry.get_tool(name)
            if not tool:
                err = f"Tool not found: {name}"
                result_messages.append(
                    ToolMessage(content=err, tool_call_id=tool_id)
                )
                if emit:
                    await emit(
                        {
                            "type": "tool_end",
                            "thread_id": config.get("configurable", {}).get(
                                "thread_id", ""
                            ),
                            "tool_call_id": tool_id,
                            "name": name,
                            "result": err,
                            "category": meta.get("category", "capability"),
                            "citations": [],
                        }
                    )
                continue

            try:
                if emit and name in _PROGRESS_TOOLS:
                    await emit(
                        {
                            "type": "tool_progress",
                            "thread_id": config.get("configurable", {}).get(
                                "thread_id", ""
                            ),
                            "tool_call_id": tool_id,
                            "tool_name": name,
                            "status": "executing",
                        }
                    )
                output = tool.invoke(args)
                output_str = str(output)
                citations = _extract_tool_citations(name, output_str)
                result_messages.append(
                    ToolMessage(content=output_str, tool_call_id=tool_id)
                )
                if emit:
                    await emit(
                        {
                            "type": "tool_end",
                            "thread_id": config.get("configurable", {}).get(
                                "thread_id", ""
                            ),
                            "tool_call_id": tool_id,
                            "name": name,
                            "result": output_str[:2000],
                            "category": meta.get("category", "capability"),
                            "citations": citations,
                        }
                    )
            except Exception as e:
                err = f"Error executing {name}: {e}"
                result_messages.append(
                    ToolMessage(content=err, tool_call_id=tool_id)
                )
                if emit:
                    await emit(
                        {
                            "type": "tool_end",
                            "thread_id": config.get("configurable", {}).get(
                                "thread_id", ""
                            ),
                            "tool_call_id": tool_id,
                            "name": name,
                            "result": err,
                            "category": meta.get("category", "capability"),
                            "citations": [],
                        }
                    )

        meta = _state_metadata(state)
        meta["tool_rounds"] = meta.get("tool_rounds", 0) + 1
        for tm in result_messages:
            if _is_usable_tool_output(str(tm.content or "")):
                meta["has_tool_content"] = True
                break

        return {"messages": result_messages, "metadata": meta}

    return hitl_tools


def _extract_tool_citations(tool_name: str, output: str) -> list[dict[str, str]]:
    if tool_name != "web_search":
        return []
    citations = []
    for line in output.split("\n"):
        if line.strip().startswith("Source:"):
            url = line.split("Source:", 1)[1].strip()
            citations.append({"url": url, "title": url})
    return citations


def create_reflect_node():
    """Update metadata after tools; avoid injecting messages that cause retry loops."""

    def reflect(state: AgentState) -> dict[str, Any]:
        meta = _state_metadata(state)
        rounds = meta.get("tool_rounds", 0)

        if meta.get("has_tool_content"):
            meta["force_answer"] = True
        elif rounds >= MAX_TOOL_ROUNDS:
            meta["force_answer"] = True

        return {"metadata": meta}

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
        messages = _messages_for_llm(state)
        meta = _state_metadata(state)
        force_answer = meta.get("force_answer") or meta.get("tool_rounds", 0) >= MAX_TOOL_ROUNDS

        tools = registry.get_enabled_tools()

        def invoke(llm: BaseChatModel):
            if force_answer or not tools:
                return llm.invoke(messages)
            return llm.bind_tools(tools).invoke(messages)

        response, provider_name = invoke_with_fallback(
            invoke, primary=lazy_llm._primary
        )
        lazy_llm._provider_name = provider_name
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
