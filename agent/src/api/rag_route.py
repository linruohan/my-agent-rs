from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from api.deps import require_auth
from api.rag_ops import (
    RagRateLimitError,
    delete_rag_source,
    ingest_rag_payload,
    list_rag_sources,
    search_rag,
)


class RagIngestBody(BaseModel):
    path: str = ""
    content: str = ""
    source: str = "inline"


class RagSearchBody(BaseModel):
    query: str = ""
    top_k: int = 6


class RagDeleteBody(BaseModel):
    source: str = ""


def _client_key(request: Request) -> str:
    host = request.client.host if request.client else "rest"
    return f"rest:{host}"


def create_rag_router() -> APIRouter:
    router = APIRouter(prefix="/rag", tags=["rag"])

    @router.get("/sources")
    async def rag_list(_: None = Depends(require_auth)) -> dict:
        return {"sources": list_rag_sources()}

    @router.post("/ingest")
    async def rag_ingest(
        body: RagIngestBody,
        request: Request,
        _: None = Depends(require_auth),
    ) -> dict:
        try:
            result = ingest_rag_payload(
                client_key=_client_key(request),
                path=body.path,
                content=body.content,
                source=body.source,
            )
        except RagRateLimitError as exc:
            raise HTTPException(
                status_code=429,
                detail={
                    "message": (
                        f"RAG ingest rate limit exceeded; retry after {exc.retry_after}s"
                    ),
                    "code": "RATE_LIMIT",
                    "retry_after_sec": exc.retry_after,
                },
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail={"message": str(exc), "code": "INVALID_REQUEST"},
            ) from exc
        return {"result": result}

    @router.post("/search")
    async def rag_search(
        body: RagSearchBody,
        _: None = Depends(require_auth),
    ) -> dict:
        results = search_rag(body.query, top_k=body.top_k)
        return {"query": body.query, "results": results}

    @router.post("/delete")
    async def rag_delete(
        body: RagDeleteBody,
        _: None = Depends(require_auth),
    ) -> dict:
        ok = delete_rag_source(body.source)
        return {"source": body.source, "ok": ok}

    return router
