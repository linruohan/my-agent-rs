from __future__ import annotations

import io
from typing import Any


class RagRateLimitError(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"rate limit; retry after {retry_after}s")


def ingest_rag_payload(
    *,
    client_key: str,
    path: str = "",
    content: str = "",
    source: str = "inline",
) -> str:
    from infra.rate_limit import check_rag_ingest_allowed
    from infra.rag_paths import (
        validate_rag_ingest_path,
        validate_rag_inline_content,
        validate_rag_pdf_b64,
    )
    from memory.rag import RagStore

    allowed, retry_after = check_rag_ingest_allowed(client_key)
    if not allowed:
        raise RagRateLimitError(retry_after)

    rag = RagStore()
    if path:
        validate_rag_ingest_path(path)
        return rag.ingest_file(path)

    if not content:
        raise ValueError("path or content required")

    if content.startswith("__pdf_b64__:"):
        from pypdf import PdfReader

        raw = validate_rag_pdf_b64(content)
        reader = PdfReader(io.BytesIO(raw))
        text = "\n".join(p.extract_text() or "" for p in reader.pages)
        validate_rag_inline_content(text, source=source)
        count = rag.ingest_text(text, source=source)
        return f"Ingested {count} chunks from PDF {source}"

    validate_rag_inline_content(content, source=source)
    count = rag.ingest_text(content, source=source)
    return f"Ingested {count} chunks from {source}"


def search_rag(query: str, top_k: int = 6) -> list[dict[str, Any]]:
    from memory.rag import RagStore

    return RagStore().search(query, top_k=top_k)


def list_rag_sources() -> list[str]:
    from memory.rag import RagStore

    return RagStore().list_sources()


def delete_rag_source(source: str) -> bool:
    from memory.rag import RagStore

    if not source:
        return False
    return RagStore().delete_source(source)
