from __future__ import annotations

import os
from typing import Any

from infra.config import load_rag_config


def get_embeddings():
    """Return embedding model based on rag.yaml config."""
    cfg = load_rag_config().get("embedding", {})
    provider = cfg.get("provider", "local")
    dimension = int(cfg.get("dimension", 384))
    model = cfg.get("model", "text-embedding-3-small")

    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(model=model)

    if provider == "ollama":
        try:
            from langchain_community.embeddings import OllamaEmbeddings

            base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
            return OllamaEmbeddings(model=model, base_url=base_url)
        except Exception:
            pass

    if provider in {"local", "huggingface"}:
        try:
            from langchain_community.embeddings import HuggingFaceEmbeddings

            return HuggingFaceEmbeddings(
                model_name=model,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
        except Exception:
            pass

    from langchain_community.embeddings import FakeEmbeddings

    return FakeEmbeddings(size=dimension)


class FaissVectorIndex:
    """Optional FAISS vector index persisted alongside SQLite chunks."""

    def __init__(self, store_dir):
        self.store_dir = store_dir
        self.index_path = store_dir / "faiss_index"
        self._vs = None

    @property
    def available(self) -> bool:
        try:
            import faiss  # noqa: F401
            from langchain_community.vectorstores import FAISS  # noqa: F401

            return True
        except ImportError:
            return False

    def rebuild(self, chunks: list[dict[str, Any]]) -> bool:
        if not self.available or not chunks:
            return False
        from langchain_community.vectorstores import FAISS
        from langchain_core.documents import Document

        docs = [
            Document(
                page_content=c["content"],
                metadata={
                    "source": c["source"],
                    "chunk_index": c["chunk_index"],
                },
            )
            for c in chunks
        ]
        embeddings = get_embeddings()
        self._vs = FAISS.from_documents(docs, embeddings)
        self.index_path.mkdir(parents=True, exist_ok=True)
        self._vs.save_local(str(self.index_path))
        return True

    def load(self) -> bool:
        if not self.available or not self.index_path.exists():
            return False
        from langchain_community.vectorstores import FAISS

        self._vs = FAISS.load_local(
            str(self.index_path),
            get_embeddings(),
            allow_dangerous_deserialization=True,
        )
        return True

    def search(self, query: str, top_k: int = 6) -> list[dict[str, Any]]:
        if self._vs is None and not self.load():
            return []
        results = self._vs.similarity_search_with_score(query, k=top_k)
        output = []
        for doc, distance in results:
            score = round(1.0 / (1.0 + float(distance)), 3)
            output.append(
                {
                    "content": doc.page_content,
                    "source": doc.metadata.get("source", ""),
                    "chunk_index": doc.metadata.get("chunk_index", 0),
                    "score": score,
                    "metadata": {},
                    "method": "vector",
                }
            )
        return output


def merge_search_results(
    keyword: list[dict[str, Any]],
    vector: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    """Reciprocal rank fusion for hybrid retrieval."""
    scores: dict[str, float] = {}
    items: dict[str, dict[str, Any]] = {}
    k = 60

    for rank, item in enumerate(keyword):
        key = f"{item['source']}:{item['chunk_index']}"
        scores[key] = scores.get(key, 0) + 1.0 / (k + rank + 1)
        items[key] = {**item, "methods": ["keyword"]}

    for rank, item in enumerate(vector):
        key = f"{item['source']}:{item['chunk_index']}"
        scores[key] = scores.get(key, 0) + 1.0 / (k + rank + 1)
        if key in items:
            items[key]["methods"] = ["keyword", "vector"]
            items[key]["score"] = round(scores[key], 3)
        else:
            items[key] = {**item, "methods": ["vector"]}

    for key, score in scores.items():
        items[key]["score"] = round(score, 3)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [items[key] for key, _ in ranked[:top_k]]
