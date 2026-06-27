from __future__ import annotations

import re
from typing import Any

from memory.rag import RagStore

_store: RagStore | None = None


def get_rag_store() -> RagStore:
    global _store
    if _store is None:
        _store = RagStore()
    return _store


def create_notes_tools():
    from langchain_core.tools import tool

    store = get_rag_store()

    @tool
    def search_notes(query: str, top_k: int = 5) -> str:
        """Search personal knowledge base / notes for relevant content."""
        results = store.search(query, top_k=top_k)
        if not results:
            return "知识库中未找到相关内容。可先导入 .md/.txt 文档。"
        lines = []
        for i, r in enumerate(results, 1):
            lines.append(
                f"{i}. [{r['source']}] (score={r['score']})\n{r['content'][:400]}"
            )
        return "\n\n".join(lines)

    @tool
    def ingest_notes(path: str) -> str:
        """Import a workspace document (.md/.txt) into the knowledge base."""
        return store.ingest_file(path)

    return [search_notes, ingest_notes]
