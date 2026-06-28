from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Awaitable, Callable

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command
from loguru import logger

from agent.slash import dispatch_slash_command
from infra.config import load_tools_config
from infra.tracing import trace_span
from memory.chat_recall import find_cached_answer, record_turn
from memory.learner import learn_from_user_message
from ocr.compose import compose_user_message, try_direct_ocr_reply
from tools.registry import ToolRegistry

EventCallback = Callable[[dict[str, Any]], Awaitable[None]]


class AgentRunner:
    """Runs LangGraph agent and streams events to WebSocket."""

    def __init__(self, graph, registry: ToolRegistry):
        self.graph = graph
        self.registry = registry
        self._active: dict[str, asyncio.Task] = {}
        self._turn_usage: dict[str, dict[str, int]] = {}
        self._running_threads: set[str] = set()
        self._thread_guard = asyncio.Lock()

    def clear_thread_state(self, thread_id: str) -> None:
        self._active.pop(thread_id, None)
        self._turn_usage.pop(thread_id, None)
        self._running_threads.discard(thread_id)

    async def _try_claim_thread(self, thread_id: str) -> bool:
        async with self._thread_guard:
            if thread_id in self._running_threads:
                return False
            self._running_threads.add(thread_id)
            return True

    async def _release_thread(self, thread_id: str) -> None:
        async with self._thread_guard:
            self._running_threads.discard(thread_id)

    async def run(
        self,
        thread_id: str,
        content: str,
        emit: EventCallback,
        attachments: list[dict[str, Any]] | None = None,
    ) -> None:
        if not await self._try_claim_thread(thread_id):
            await emit(
                {
                    "type": "error",
                    "thread_id": thread_id,
                    "message": "该会话正在处理中，请稍候或停止当前任务",
                    "code": "THREAD_BUSY",
                }
            )
            return

        config = self._make_config(thread_id, emit)
        start = time.monotonic()

        task = asyncio.current_task()
        if task:
            self._active[thread_id] = task

        try:
            with trace_span("agent.run", thread_id=thread_id):
                await self._run_turn(
                    thread_id, content, emit, attachments, config, start
                )
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
            self._turn_usage.pop(thread_id, None)
            await self._release_thread(thread_id)

    async def _run_turn(
        self,
        thread_id: str,
        content: str,
        emit: EventCallback,
        attachments: list[dict[str, Any]] | None,
        config: dict[str, Any],
        start: float,
    ) -> None:
        ocr_timeout = _ocr_timeout_sec()
        self._turn_usage[thread_id] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        direct_ocr = await asyncio.to_thread(
            try_direct_ocr_reply, content, attachments, timeout=ocr_timeout
        )
        if direct_ocr is not None:
            user_text = (content or "").strip() or "[图片 OCR]"
            await self._append_local_turn(config, user_text, direct_ocr)
            await emit({"type": "token", "thread_id": thread_id, "content": direct_ocr})
            metadata = {
                "duration_ms": int((time.monotonic() - start) * 1000),
                "ocr": True,
            }
            await emit({"type": "done", "thread_id": thread_id, "metadata": metadata})
            return

        user_text = (content or "").strip()
        slash_result = dispatch_slash_command(user_text)
        if slash_result is not None:
            await self._append_local_turn(config, user_text, slash_result)
            await emit({"type": "token", "thread_id": thread_id, "content": slash_result})
            lowered = user_text.lower()
            metadata = {
                "duration_ms": int((time.monotonic() - start) * 1000),
                "slash": True,
                "task_data_changed": lowered.startswith("/tsk")
                or lowered.startswith("/pro")
                or lowered.startswith("/sec"),
            }
            await emit({"type": "done", "thread_id": thread_id, "metadata": metadata})
            return

        message_content = await asyncio.to_thread(
            compose_user_message,
            content,
            attachments,
            timeout=ocr_timeout,
        )
        if not message_content.strip():
            await emit(
                {
                    "type": "error",
                    "thread_id": thread_id,
                    "message": "消息内容不能为空",
                    "code": "INVALID_REQUEST",
                }
            )
            return

        learn_from_user_message(user_text)

        cached = await asyncio.to_thread(
            find_cached_answer,
            user_text,
            thread_id,
            has_attachments=bool(attachments),
        )
        if cached:
            await self._emit_history_recall(
                thread_id,
                config,
                user_text,
                cached,
                emit,
                start,
            )
            return

        input_state = {"messages": [HumanMessage(content=message_content)]}
        metadata: dict[str, Any] = {"duration_ms": 0}

        async for event in self.graph.astream_events(
            input_state, config, version="v2"
        ):
            await self._handle_event(event, thread_id, emit)

        if await self._emit_pending_interrupts(thread_id, config, emit):
            return

        metadata["duration_ms"] = int((time.monotonic() - start) * 1000)
        usage = self._turn_usage.pop(thread_id, {})
        if usage:
            metadata["token_usage"] = usage
        from infra.metrics import observe_turn_duration

        observe_turn_duration(metadata["duration_ms"])
        logger.info(
            "agent.turn_done thread_id={} duration_ms={} tokens={}",
            thread_id,
            metadata["duration_ms"],
            usage.get("total_tokens", 0),
        )
        await self._post_turn_index(thread_id, config, user_text)
        await emit({"type": "done", "thread_id": thread_id, "metadata": metadata})

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

        elif kind == "on_chat_model_end":
            output = event.get("data", {}).get("output")
            usage_meta = getattr(output, "usage_metadata", None) if output else None
            if isinstance(usage_meta, dict):
                bucket = self._turn_usage.setdefault(
                    thread_id, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                )
                for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                    val = usage_meta.get(key)
                    if isinstance(val, int):
                        bucket[key] = bucket.get(key, 0) + val
            elif output and hasattr(output, "response_metadata"):
                meta = output.response_metadata or {}
                token_usage = meta.get("token_usage") or meta.get("usage") or {}
                if isinstance(token_usage, dict):
                    bucket = self._turn_usage.setdefault(
                        thread_id, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                    )
                    prompt = token_usage.get("prompt_tokens") or token_usage.get("input_tokens") or 0
                    completion = (
                        token_usage.get("completion_tokens") or token_usage.get("output_tokens") or 0
                    )
                    total = token_usage.get("total_tokens") or (prompt + completion)
                    bucket["prompt_tokens"] = bucket.get("prompt_tokens", 0) + int(prompt)
                    bucket["completion_tokens"] = bucket.get("completion_tokens", 0) + int(completion)
                    bucket["total_tokens"] = bucket.get("total_tokens", 0) + int(total)

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
        if not await self._try_claim_thread(thread_id):
            await emit(
                {
                    "type": "error",
                    "thread_id": thread_id,
                    "message": "该会话正在处理中，请稍候",
                    "code": "THREAD_BUSY",
                }
            )
            return

        config = self._make_config(thread_id, emit)
        resume_value: dict[str, Any] = {"decision": decision}
        if edited_args:
            resume_value["edited_args"] = edited_args

        start = time.monotonic()
        from infra.hitl import hitl_timeout_manager

        hitl_timeout_manager.cancel(thread_id)
        try:
            with trace_span("agent.resume", thread_id=thread_id, decision=decision):
                async for event in self.graph.astream_events(
                    Command(resume=resume_value), config, version="v2"
                ):
                    await self._handle_event(event, thread_id, emit)

                if await self._emit_pending_interrupts(thread_id, config, emit):
                    return

                metadata = {"duration_ms": int((time.monotonic() - start) * 1000)}
                usage = self._turn_usage.pop(thread_id, {})
                if usage:
                    metadata["token_usage"] = usage
                user_text = await self._last_user_text(config)
                if user_text:
                    await self._post_turn_index(thread_id, config, user_text)
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
        finally:
            await self._release_thread(thread_id)


    def _make_config(self, thread_id: str, emit: EventCallback) -> dict[str, Any]:
        async def _emit(msg: dict[str, Any]) -> None:
            await emit(msg)

        return {
            "configurable": {"thread_id": thread_id, "_emit": _emit},
            "recursion_limit": 40,
        }

    async def _emit_history_recall(
        self,
        thread_id: str,
        config: dict[str, Any],
        user_text: str,
        cached: dict[str, Any],
        emit: EventCallback,
        start: float,
    ) -> None:
        from memory.chat_recall import get_chat_history_store

        answer = str(cached.get("answer", ""))
        created = str(cached.get("created_at", ""))[:10]
        sim = cached.get("similarity", "")
        header = f"📎 引用历史回答（{created}，相似度 {sim}）\n\n"
        full = header + answer

        await self._append_local_turn(config, user_text, full)
        await emit({"type": "token", "thread_id": thread_id, "content": full})

        entry_id = cached.get("id")
        if isinstance(entry_id, int):
            await asyncio.to_thread(get_chat_history_store().bump_hit, entry_id)

        metadata = {
            "duration_ms": int((time.monotonic() - start) * 1000),
            "from_history": True,
            "history_similarity": cached.get("similarity"),
            "history_created_at": cached.get("created_at"),
        }
        await emit({"type": "done", "thread_id": thread_id, "metadata": metadata})

    async def _post_turn_index(
        self, thread_id: str, config: dict[str, Any], user_text: str
    ) -> None:
        """Persist Q&A pair for future recall after a normal agent turn."""
        answer = await self._last_assistant_text(config)
        if not answer:
            return
        clean_answer = answer.strip()
        if clean_answer.startswith("📎 引用历史回答"):
            return
        await asyncio.to_thread(record_turn, thread_id, user_text, clean_answer)

    async def _last_user_text(self, config: dict[str, Any]) -> str:
        from langchain_core.messages import HumanMessage

        state = await self.graph.aget_state(config)
        if not state or not state.values:
            return ""
        for msg in reversed(state.values.get("messages", [])):
            if isinstance(msg, HumanMessage):
                content = msg.content
                if isinstance(content, list):
                    content = "".join(
                        block.get("text", "") if isinstance(block, dict) else str(block)
                        for block in content
                    )
                return str(content or "").strip()
        return ""

    async def _last_assistant_text(self, config: dict[str, Any]) -> str:
        from langchain_core.messages import AIMessage

        state = await self.graph.aget_state(config)
        if not state or not state.values:
            return ""
        for msg in reversed(state.values.get("messages", [])):
            if isinstance(msg, AIMessage):
                content = msg.content
                if isinstance(content, list):
                    content = "".join(
                        block.get("text", "") if isinstance(block, dict) else str(block)
                        for block in content
                    )
                text = str(content or "").strip()
                if not text:
                    continue
                if getattr(msg, "tool_calls", None) and len(text) < 80:
                    continue
                return text
        return ""

    async def _append_local_turn(
        self, config: dict[str, Any], user_text: str, assistant_text: str
    ) -> None:
        """Persist a local-only turn (slash / OCR) without running the LLM graph."""
        await self.graph.aupdate_state(
            config,
            {
                "messages": [
                    HumanMessage(content=user_text),
                    AIMessage(content=assistant_text),
                ]
            },
            as_node="agent",
        )

    async def _emit_pending_interrupts(
        self, thread_id: str, config: dict[str, Any], emit: EventCallback
    ) -> bool:
        """Emit interrupt events and schedule HITL timeout. Returns True if waiting for user."""
        state = await self.graph.aget_state(config)
        if not state.interrupts:
            return False

        from infra.hitl import hitl_timeout_manager

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
        hitl_timeout_manager.schedule(thread_id)
        return True

    async def get_history(self, thread_id: str) -> list[dict[str, Any]]:
        """Load conversation messages from LangGraph checkpoint."""
        from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

        config = {"configurable": {"thread_id": thread_id}}
        state = await self.graph.aget_state(config)
        if not state or not state.values:
            return []

        result: list[dict[str, Any]] = []
        for msg in state.values.get("messages", []):
            if isinstance(msg, HumanMessage):
                content = msg.content
                if isinstance(content, list):
                    content = "".join(
                        block.get("text", "") if isinstance(block, dict) else str(block)
                        for block in content
                    )
                if content:
                    result.append({"role": "user", "content": str(content)})
            elif isinstance(msg, AIMessage):
                content = msg.content
                if isinstance(content, list):
                    content = "".join(
                        block.get("text", "") if isinstance(block, dict) else str(block)
                        for block in content
                    )
                if content:
                    result.append({"role": "assistant", "content": str(content)})
            elif isinstance(msg, ToolMessage):
                result.append(
                    {
                        "role": "tool",
                        "content": str(msg.content)[:2000],
                        "tool_name": getattr(msg, "name", "") or "",
                    }
                )
        return result


def _ocr_timeout_sec() -> float:
    cfg = load_tools_config().get("capability", {}).get("ocr", {})
    return float(cfg.get("timeout_sec", 180))
