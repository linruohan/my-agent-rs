from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from agent.runner import AgentRunner
from infra.session_store import SessionStore

from infra.hitl import hitl_timeout_manager
from infra.auth import auth_required, verify_token

router = APIRouter()
VERSION = "0.1.0"

_thread_emitters: dict[str, Any] = {}
_authenticated_ws: set[int] = set()
_hitl_callbacks_registered = False


def set_thread_emitter(thread_id: str, emit: Any) -> None:
    _thread_emitters[thread_id] = emit


def clear_thread_emitter(thread_id: str) -> None:
    _thread_emitters.pop(thread_id, None)


def _register_hitl_callbacks(runner: AgentRunner) -> None:
    global _hitl_callbacks_registered
    if _hitl_callbacks_registered:
        return
    _hitl_callbacks_registered = True

    async def auto_hitl_resume(thread_id: str, decision: str, edited_args: dict | None):
        emitter = _thread_emitters.get(thread_id)
        if emitter is None:
            return
        await runner.resume(thread_id, decision, edited_args, emitter)

    async def hitl_notify(thread_id: str, seconds_left: int):
        emitter = _thread_emitters.get(thread_id)
        if emitter is None:
            return
        await emitter(
            {
                "type": "interrupt_timeout_warning",
                "thread_id": thread_id,
                "seconds_left": seconds_left,
            }
        )

    hitl_timeout_manager.set_resume_callback(auto_hitl_resume)
    hitl_timeout_manager.set_notify_callback(hitl_notify)

PROTECTED_MSG_TYPES = frozenset(
    {
        "chat.send",
        "chat.stop",
        "chat.resume",
        "session.create",
        "session.delete",
        "session.archive",
        "session.unarchive",
        "rag.ingest",
        "rag.delete",
        "memory.set",
    }
)


class ConnectionManager:
    def __init__(self):
        self._connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.add(ws)

    def disconnect(self, ws: WebSocket):
        self._connections.discard(ws)

    async def broadcast(self, msg: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_json(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.discard(ws)


manager = ConnectionManager()


def create_ws_router(
    runner: AgentRunner,
    session_store: SessionStore,
    port: int,
) -> APIRouter:
    ws_router = APIRouter()
    _register_hitl_callbacks(runner)

    @ws_router.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await manager.connect(ws)
        ws_id = id(ws)

        async def emit(msg: dict[str, Any]):
            await ws.send_json(msg)

        def is_authenticated() -> bool:
            return not auth_required() or ws_id in _authenticated_ws

        try:
            await ws.send_json(
                {
                    "type": "connected",
                    "port": port,
                    "version": VERSION,
                    "auth_required": auth_required(),
                }
            )

            while True:
                raw = await ws.receive_text()
                data = json.loads(raw)
                msg_type = data.get("type")

                if msg_type == "auth":
                    token = data.get("token", "")
                    if verify_token(token):
                        _authenticated_ws.add(ws_id)
                        await ws.send_json({"type": "auth.ok"})
                    else:
                        await ws.send_json(
                            {
                                "type": "error",
                                "message": "Authentication failed",
                                "code": "AUTH_FAILED",
                            }
                        )
                    continue

                if msg_type in PROTECTED_MSG_TYPES and not is_authenticated():
                    await ws.send_json(
                        {
                            "type": "error",
                            "message": "Authentication required",
                            "code": "AUTH_FAILED",
                        }
                    )
                    continue

                if msg_type == "ping":
                    await ws.send_json({"type": "pong"})
                    continue

                if msg_type == "session.list":
                    include_archived = bool(data.get("include_archived"))
                    sessions = session_store.list_sessions(include_archived=include_archived)
                    await ws.send_json({"type": "session.list", "sessions": sessions})
                    continue

                if msg_type == "session.archived":
                    archived = session_store.list_archived_sessions()
                    await ws.send_json({"type": "session.archived", "sessions": archived})
                    continue

                if msg_type == "session.archive":
                    thread_id = data.get("thread_id", "")
                    ok = session_store.set_archived(thread_id, True) if thread_id else False
                    await ws.send_json(
                        {"type": "session.archived_one", "thread_id": thread_id, "ok": ok}
                    )
                    continue

                if msg_type == "session.unarchive":
                    thread_id = data.get("thread_id", "")
                    ok = session_store.set_archived(thread_id, False) if thread_id else False
                    await ws.send_json(
                        {"type": "session.unarchived", "thread_id": thread_id, "ok": ok}
                    )
                    continue

                if msg_type == "session.create":
                    session = session_store.create(data.get("title"))
                    await ws.send_json({"type": "session.created", **session})
                    continue

                if msg_type == "session.delete":
                    thread_id = data.get("thread_id", "")
                    ok = session_store.delete(thread_id) if thread_id else False
                    if ok and thread_id:
                        checkpointer = getattr(
                            getattr(runner, "graph", None), "checkpointer", None
                        )
                        from infra.session_lifecycle import purge_thread_data

                        await purge_thread_data(
                            thread_id,
                            runner=runner,
                            checkpointer=checkpointer,
                        )
                    await ws.send_json(
                        {"type": "session.deleted", "thread_id": thread_id, "ok": ok}
                    )
                    continue

                if msg_type == "session.history":
                    thread_id = data.get("thread_id", "")
                    if not thread_id:
                        await ws.send_json(
                            {
                                "type": "error",
                                "message": "thread_id required",
                                "code": "INVALID_REQUEST",
                            }
                        )
                        continue
                    messages = await runner.get_history(thread_id)
                    await ws.send_json(
                        {
                            "type": "session.history",
                            "thread_id": thread_id,
                            "messages": messages,
                        }
                    )
                    continue

                if msg_type == "chat.send":
                    thread_id = data.get("thread_id", "")
                    content = data.get("content", "")
                    attachments = data.get("attachments") or []
                    if not thread_id or (not content and not attachments):
                        await ws.send_json(
                            {
                                "type": "error",
                                "message": "thread_id and content or attachments required",
                                "code": "INVALID_REQUEST",
                            }
                        )
                        continue
                    if not session_store.exists(thread_id):
                        await ws.send_json(
                            {
                                "type": "error",
                                "message": f"Thread {thread_id} not found",
                                "code": "THREAD_NOT_FOUND",
                            }
                        )
                        continue
                    session_store.touch(thread_id)
                    set_thread_emitter(thread_id, emit)
                    asyncio.create_task(
                        runner.run(thread_id, content, emit, attachments=attachments or None)
                    )
                    continue

                if msg_type == "chat.stop":
                    thread_id = data.get("thread_id", "")
                    stopped = await runner.stop(thread_id)
                    await ws.send_json(
                        {"type": "chat.stopped", "thread_id": thread_id, "ok": stopped}
                    )
                    continue

                if msg_type == "chat.resume":
                    thread_id = data.get("thread_id", "")
                    decision = data.get("decision", "reject")
                    edited_args = data.get("edited_args")
                    if thread_id:
                        set_thread_emitter(thread_id, emit)
                    asyncio.create_task(
                        runner.resume(thread_id, decision, edited_args, emit)
                    )
                    continue

                if msg_type == "memory.get":
                    from memory.store import MemoryStore

                    store = MemoryStore()
                    namespace = data.get("namespace", "user")
                    key = data.get("key", "preferences")
                    value = store.get(namespace, key)
                    await ws.send_json(
                        {"type": "memory.get", "namespace": namespace, "key": key, "value": value}
                    )
                    continue

                if msg_type == "memory.set":
                    from memory.store import MemoryStore

                    store = MemoryStore()
                    namespace = data.get("namespace", "user")
                    key = data.get("key", "preferences")
                    value = data.get("value", {})
                    store.put(namespace, key, value)
                    await ws.send_json(
                        {"type": "memory.set", "namespace": namespace, "key": key, "ok": True}
                    )
                    continue

                if msg_type == "rag.ingest":
                    import io

                    from infra.rate_limit import check_rag_ingest_allowed
                    from infra.rag_paths import (
                        validate_rag_ingest_path,
                        validate_rag_inline_content,
                        validate_rag_pdf_b64,
                    )
                    from memory.rag import RagStore

                    allowed, retry_after = check_rag_ingest_allowed(str(ws_id))
                    if not allowed:
                        await ws.send_json(
                            {
                                "type": "error",
                                "message": (
                                    f"RAG ingest rate limit exceeded; "
                                    f"retry after {retry_after}s"
                                ),
                                "code": "RATE_LIMIT",
                            }
                        )
                        continue

                    rag = RagStore()
                    path = data.get("path", "")
                    content = data.get("content", "")
                    try:
                        if path:
                            validate_rag_ingest_path(path)
                            result = rag.ingest_file(path)
                        elif content:
                            source = data.get("source", "inline")
                            if content.startswith("__pdf_b64__:"):
                                from pypdf import PdfReader

                                raw = validate_rag_pdf_b64(content)
                                reader = PdfReader(io.BytesIO(raw))
                                text = "\n".join(
                                    p.extract_text() or "" for p in reader.pages
                                )
                                validate_rag_inline_content(text, source=source)
                                count = rag.ingest_text(text, source=source)
                                result = f"Ingested {count} chunks from PDF {source}"
                            else:
                                validate_rag_inline_content(content, source=source)
                                count = rag.ingest_text(content, source=source)
                                result = f"Ingested {count} chunks from {source}"
                        else:
                            result = "path or content required"
                    except ValueError as exc:
                        await ws.send_json(
                            {
                                "type": "error",
                                "message": str(exc),
                                "code": "INVALID_REQUEST",
                            }
                        )
                        continue
                    await ws.send_json({"type": "rag.ingest", "result": result})
                    continue

                if msg_type == "rag.search":
                    from memory.rag import RagStore

                    rag = RagStore()
                    query = data.get("query", "")
                    results = rag.search(query, top_k=data.get("top_k", 6))
                    await ws.send_json({"type": "rag.search", "query": query, "results": results})
                    continue

                if msg_type == "rag.list":
                    from memory.rag import RagStore

                    rag = RagStore()
                    sources = rag.list_sources()
                    await ws.send_json({"type": "rag.list", "sources": sources})
                    continue

                if msg_type == "rag.delete":
                    from memory.rag import RagStore

                    rag = RagStore()
                    source = data.get("source", "")
                    ok = rag.delete_source(source) if source else False
                    await ws.send_json({"type": "rag.deleted", "source": source, "ok": ok})
                    continue

                if msg_type == "scheduler.list":
                    from infra.scheduler import list_pending_jobs

                    jobs = list_pending_jobs()
                    await ws.send_json({"type": "scheduler.list", "jobs": jobs})
                    continue

                await ws.send_json(
                    {
                        "type": "error",
                        "message": f"Unknown message type: {msg_type}",
                        "code": "INVALID_REQUEST",
                    }
                )

        except WebSocketDisconnect:
            pass
        finally:
            manager.disconnect(ws)
            _authenticated_ws.discard(ws_id)

    return ws_router
