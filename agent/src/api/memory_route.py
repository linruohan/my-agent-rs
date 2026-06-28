from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from infra.auth import auth_required, verify_token


class MemoryValueBody(BaseModel):
    value: dict[str, Any] = {}


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


def create_memory_router() -> APIRouter:
    router = APIRouter(prefix="/memory", tags=["memory"])

    @router.get("/{namespace}/{key}")
    async def memory_get(
        namespace: str,
        key: str,
        _: None = Depends(_auth_dependency),
    ) -> dict:
        from memory.store import MemoryStore

        store = MemoryStore()
        value = store.get(namespace, key)
        return {"namespace": namespace, "key": key, "value": value}

    @router.put("/{namespace}/{key}")
    async def memory_set(
        namespace: str,
        key: str,
        body: MemoryValueBody,
        _: None = Depends(_auth_dependency),
    ) -> dict:
        from memory.store import MemoryStore

        store = MemoryStore()
        store.put(namespace, key, body.value)
        return {"namespace": namespace, "key": key, "ok": True}

    return router
