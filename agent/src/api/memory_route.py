from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.deps import require_auth


class MemoryValueBody(BaseModel):
    value: dict[str, Any] = {}


def create_memory_router() -> APIRouter:
    router = APIRouter(prefix="/memory", tags=["memory"])

    @router.get("/{namespace}/{key}")
    async def memory_get(
        namespace: str,
        key: str,
        _: None = Depends(require_auth),
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
        _: None = Depends(require_auth),
    ) -> dict:
        from memory.store import MemoryStore

        store = MemoryStore()
        store.put(namespace, key, body.value)
        return {"namespace": namespace, "key": key, "ok": True}

    return router
