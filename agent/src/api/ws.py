from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from agent.runner import AgentRunner
from infra.session_store import SessionStore

from infra.hitl import hitl_timeout_manager

router = APIRouter()
VERSION = "0.1.0"

_thread_emitters: dict[str, Any] = {}


class ConnectionManager:
    def __init__(self):
        self._connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.add(ws)

    def disconnect(self, ws: WebSocket):
        self._connections.discard(ws)


manager = ConnectionManager()


def create_ws_router(
    runner: AgentRunner,
    session_store: SessionStore,
    port: int,
) -> APIRouter:
    ws_router = APIRouter()

    @ws_router.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await manager.connect(ws)
        await ws.send_json({"type": "connected", "port": port, "version": VERSION})

        async def emit(msg: dict[str, Any]):
            await ws.send_json(msg)

        async def auto_hitl_resume(thread_id: str, decision: str, edited_args: dict | None):
            emitter = _thread_emitters.get(thread_id, emit)
            await runner.resume(thread_id, decision, edited_args, emitter)

        hitl_timeout_manager.set_resume_callback(auto_hitl_resume)

        try:
            while True:
                raw = await ws.receive_text()
                data = json.loads(raw)
                msg_type = data.get("type")

                if msg_type == "ping":
                    await ws.send_json({"type": "pong"})
                    continue

                if msg_type == "session.list":
                    sessions = session_store.list_sessions()
                    await ws.send_json({"type": "session.list", "sessions": sessions})
                    continue

                if msg_type == "session.create":
                    session = session_store.create(data.get("title"))
                    await ws.send_json({"type": "session.created", **session})
                    continue

                if msg_type == "session.delete":
                    thread_id = data.get("thread_id", "")
                    ok = session_store.delete(thread_id)
                    await ws.send_json(
                        {"type": "session.deleted", "thread_id": thread_id, "ok": ok}
                    )
                    continue

                if msg_type == "chat.send":
                    thread_id = data.get("thread_id", "")
                    content = data.get("content", "")
                    if not thread_id or not content:
                        await ws.send_json(
                            {
                                "type": "error",
                                "message": "thread_id and content required",
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
                    _thread_emitters[thread_id] = emit
                    asyncio.create_task(runner.run(thread_id, content, emit))
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
                    from memory.rag import RagStore

                    rag = RagStore()
                    path = data.get("path", "")
                    content = data.get("content", "")
                    if path:
                        result = rag.ingest_file(path)
                    elif content:
                        source = data.get("source", "inline")
                        count = rag.ingest_text(content, source=source)
                        result = f"Ingested {count} chunks from {source}"
                    else:
                        result = "path or content required"
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
            manager.disconnect(ws)

    return ws_router
