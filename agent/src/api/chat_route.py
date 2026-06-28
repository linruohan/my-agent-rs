from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.runner import AgentRunner
from api.chat_sse import stream_runner_events
from api.deps import require_auth
from infra.session_store import SessionStore


class ChatSendBody(BaseModel):
    content: str = ""
    attachments: list[dict[str, Any]] | None = None


class ChatResumeBody(BaseModel):
    decision: str = "reject"
    edited_args: dict[str, Any] | None = None


def _validate_chat_send(
    session_store: SessionStore,
    thread_id: str,
    content: str,
    attachments: list[dict[str, Any]] | None,
) -> None:
    if not thread_id:
        raise HTTPException(status_code=400, detail="thread_id required")
    if not content and not attachments:
        raise HTTPException(
            status_code=400,
            detail="content or attachments required",
        )
    if not session_store.exists(thread_id):
        raise HTTPException(status_code=404, detail="Thread not found")


def create_chat_router(
    runner: AgentRunner,
    session_store: SessionStore,
) -> APIRouter:
    router = APIRouter(prefix="/sessions", tags=["chat"])

    @router.post("/{thread_id}/chat")
    async def chat_send(
        thread_id: str,
        body: ChatSendBody,
        _: None = Depends(require_auth),
    ) -> StreamingResponse:
        attachments = body.attachments or None
        _validate_chat_send(session_store, thread_id, body.content, attachments)
        session_store.touch(thread_id)

        async def _run(emit):
            await runner.run(
                thread_id,
                body.content,
                emit,
                attachments=attachments,
            )

        return StreamingResponse(
            stream_runner_events(thread_id, _run),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @router.post("/{thread_id}/chat/stop")
    async def chat_stop(
        thread_id: str,
        _: None = Depends(require_auth),
    ) -> dict:
        stopped = await runner.stop(thread_id)
        return {"ok": stopped, "thread_id": thread_id}

    @router.post("/{thread_id}/chat/resume")
    async def chat_resume(
        thread_id: str,
        body: ChatResumeBody,
        _: None = Depends(require_auth),
    ) -> StreamingResponse:
        if not thread_id:
            raise HTTPException(status_code=400, detail="thread_id required")
        if not session_store.exists(thread_id):
            raise HTTPException(status_code=404, detail="Thread not found")

        async def _run(emit):
            await runner.resume(
                thread_id,
                body.decision,
                body.edited_args,
                emit,
            )

        return StreamingResponse(
            stream_runner_events(thread_id, _run),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return router
