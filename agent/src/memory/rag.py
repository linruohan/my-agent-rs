from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from infra.config import get_data_dir, load_rag_config
from memory.rag_vector import FaissVectorIndex, merge_search_results

SUPPORTED_EXTENSIONS = {".md", ".txt", ".markdown", ".pdf"}


def _extract_file_text(target: Path) -> str:
    suffix = target.suffix.lower()
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(target))
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n".join(pages)
        except ImportError:
            raise RuntimeError("PDF support requires: pip install pypdf")
    return target.read_text(encoding="utf-8", errors="replace")


class RagStore:
    """RAG store: SQLite chunks + optional FAISS hybrid retrieval."""

    def __init__(self, db_path: Path | None = None):
        cfg = load_rag_config()
        self.top_k = cfg.get("retrieval", {}).get("top_k", 6)
        self.use_vector = cfg.get("index", {}).get("backend", "faiss") == "faiss"
        persist = cfg.get("index", {}).get("persist_dir", "data/vectorstore")
        self.store_dir = get_data_dir() / "vectorstore"
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path or (self.store_dir / "documents.db")
        self._vector = FaissVectorIndex(self.store_dir)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    deleted_at TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(source, content_hash, chunk_index)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_docs_source ON documents(source)"
            )
            conn.commit()

    @staticmethod
    def _chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
        if len(text) <= chunk_size:
            return [text]
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start = end - overlap
        return chunks

    @staticmethod
    def _content_hash(content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _all_active_chunks(self) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT source, chunk_index, content FROM documents
                WHERE deleted_at IS NULL ORDER BY source, chunk_index
                """
            ).fetchall()
        return [
            {"source": r["source"], "chunk_index": r["chunk_index"], "content": r["content"]}
            for r in rows
        ]

    def _rebuild_vector_index(self) -> None:
        if self.use_vector and self._vector.available:
            self._vector.rebuild(self._all_active_chunks())

    def ingest_text(
        self,
        content: str,
        source: str,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        cfg = load_rag_config()
        chunk_size = cfg.get("chunking", {}).get("chunk_size", 800)
        overlap = cfg.get("chunking", {}).get("chunk_overlap", 100)
        content_hash = self._content_hash(content)
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)
        now = datetime.now(timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            existing = conn.execute(
                "SELECT 1 FROM documents WHERE source = ? AND content_hash = ? LIMIT 1",
                (source, content_hash),
            ).fetchone()
            if existing:
                return 0

            conn.execute(
                "UPDATE documents SET deleted_at = ? WHERE source = ? AND deleted_at IS NULL",
                (now, source),
            )
            chunks = self._chunk_text(content, chunk_size, overlap)
            for i, chunk in enumerate(chunks):
                conn.execute(
                    """
                    INSERT INTO documents
                    (source, content_hash, chunk_index, content, metadata, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (source, content_hash, i, chunk, meta_json, now),
                )
            conn.commit()

        self._rebuild_vector_index()
        return len(chunks)

    def ingest_file(self, path: str) -> str:
        from infra.config import resolve_workspace_path

        target = resolve_workspace_path(path)
        if not target.exists():
            return f"File not found: {path}"
        if target.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return f"Unsupported file type: {target.suffix}. Supported: {SUPPORTED_EXTENSIONS}"
        content = _extract_file_text(target)
        count = self.ingest_text(content, source=path)
        if count == 0:
            return f"Skipped {path} (content unchanged)"
        return f"Ingested {path}: {count} chunks"

    def _keyword_search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        terms = [t for t in re.split(r"\W+", query.lower()) if len(t) > 1]
        if not terms:
            return []

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT source, chunk_index, content, metadata FROM documents WHERE deleted_at IS NULL"
            ).fetchall()

        scored: list[tuple[float, dict[str, Any]]] = []
        for row in rows:
            text = row["content"].lower()
            hits = sum(1 for t in terms if t in text)
            if hits == 0:
                continue
            score = hits / len(terms)
            scored.append(
                (
                    score,
                    {
                        "content": row["content"],
                        "source": row["source"],
                        "chunk_index": row["chunk_index"],
                        "score": round(score, 3),
                        "metadata": json.loads(row["metadata"] or "{}"),
                        "method": "keyword",
                    },
                )
            )

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:top_k]]

    def search(self, query: str, top_k: int | None = None) -> list[dict[str, Any]]:
        k = top_k or self.top_k
        keyword = self._keyword_search(query, k)

        cfg = load_rag_config()
        if self.use_vector and cfg.get("retrieval", {}).get("use_bm25", True):
            vector = self._vector.search(query, k) if self._vector.available else []
            if vector and keyword:
                return merge_search_results(keyword, vector, k)
            if vector:
                return vector

        return keyword

    def format_for_prompt(self, docs: list[dict[str, Any]]) -> str:
        if not docs:
            return ""
        lines = ["Retrieved knowledge:"]
        for i, d in enumerate(docs, 1):
            methods = d.get("methods", [d.get("method", "keyword")])
            lines.append(
                f"[{i}] source={d['source']} score={d['score']} methods={methods}\n"
                f"{d['content'][:600]}"
            )
        return "\n\n".join(lines)

    def list_sources(self) -> list[str]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT source FROM documents
                WHERE deleted_at IS NULL ORDER BY source
                """
            ).fetchall()
        return [r[0] for r in rows]

    def delete_source(self, source: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "UPDATE documents SET deleted_at = ? WHERE source = ? AND deleted_at IS NULL",
                (now, source),
            )
            conn.commit()
            deleted = cur.rowcount > 0
        if deleted:
            self._rebuild_vector_index()
        return deleted


def is_knowledge_query(text: str) -> bool:
    patterns = [
        r"知识库",
        r"文档里",
        r"笔记里",
        r"根据.*资料",
        r"我上传的",
        r"之前保存的",
        r"what does my note say",
        r"search my notes",
    ]
    lower = text.lower()
    return any(re.search(p, lower) for p in patterns)
