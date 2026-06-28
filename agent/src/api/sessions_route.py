from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from agent.runner import AgentRunner
from api.session_ops import (
    create_session_record,
    delete_session_record,
    set_session_archived,
)
from infra.auth import auth_required, verify_token
from infra.session_store import SessionStore


class SessionCreateBody(BaseModel):
    title: str | None = None


def _auth_dependency(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    if not auth_required():
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization[7:].strip()
    if not verify_token(token):
        raise HTTPException(status_code=401, detail="Unauthorized")


def create_sessions_router(
    runner: AgentRunner,
    session_store: SessionStore,
) -> APIRouter:
    router = APIRouter(prefix="/sessions", tags=["sessions"])

    @router.get("")
    async def list_sessions(
        include_archived: bool = False,
        _: None = Depends(_auth_dependency),
    ) -> dict:
        sessions = session_store.list_sessions(include_archived=include_archived)
        return {"sessions": sessions}

    @router.get("/archived")
    async def list_archived_sessions(_: None = Depends(_auth_dependency)) -> dict:
        archived = session_store.list_archived_sessions()
        return {"sessions": archived}

    @router.post("")
    async def create_session(
        body: SessionCreateBody,
        _: None = Depends(_auth_dependency),
    ) -> dict:
        session = create_session_record(session_store, body.title)
        return {"ok": True, **session}

    @router.get("/{thread_id}/history")
    async def session_history(
        thread_id: str,
        _: None = Depends(_auth_dependency),
    ) -> dict:
        if not session_store.exists(thread_id):
            raise HTTPException(status_code=404, detail="Thread not found")
        messages = await runner.get_history(thread_id)
        return {"thread_id": thread_id, "messages": messages}

    @router.delete("/{thread_id}")
    async def delete_session(
        thread_id: str,
        _: None = Depends(_auth_dependency),
    ) -> dict:
        ok = await delete_session_record(
            thread_id,
            session_store=session_store,
            runner=runner,
        )
        if not ok:
            raise HTTPException(status_code=404, detail="Thread not found")
        return {"ok": True, "thread_id": thread_id}

    @router.post("/{thread_id}/archive")
    async def archive_session(
        thread_id: str,
        _: None = Depends(_auth_dependency),
    ) -> dict:
        if not session_store.exists(thread_id):
            raise HTTPException(status_code=404, detail="Thread not found")
        ok = set_session_archived(session_store, thread_id, True)
        return {"ok": ok, "thread_id": thread_id}

    @router.post("/{thread_id}/unarchive")
    async def unarchive_session(
        thread_id: str,
        _: None = Depends(_auth_dependency),
    ) -> dict:
        if not session_store.exists(thread_id):
            raise HTTPException(status_code=404, detail="Thread not found")
        ok = set_session_archived(session_store, thread_id, False)
        return {"ok": ok, "thread_id": thread_id}

    return router
