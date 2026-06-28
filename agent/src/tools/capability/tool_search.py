from __future__ import annotations

import math
import re
from typing import Any

from tools.registry import ToolRegistry


def _tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"\W+", text.lower()) if len(t) > 1]


class _SimpleBM25:
    """Lightweight BM25 over tool metadata (no external deps)."""

    def __init__(self, documents: list[tuple[str, dict[str, Any]]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.docs = documents
        self.doc_tokens = [_tokenize(text) for text, _ in documents]
        self.doc_freq: dict[str, int] = {}
        for tokens in self.doc_tokens:
            for term in set(tokens):
                self.doc_freq[term] = self.doc_freq.get(term, 0) + 1
        self.avg_len = sum(len(t) for t in self.doc_tokens) / max(len(self.doc_tokens), 1)
        self.n_docs = len(self.doc_tokens)

    def score(self, query_terms: list[str], doc_index: int) -> float:
        tokens = self.doc_tokens[doc_index]
        if not tokens:
            return 0.0
        doc_len = len(tokens)
        tf: dict[str, int] = {}
        for term in tokens:
            tf[term] = tf.get(term, 0) + 1
        total = 0.0
        for term in query_terms:
            if term not in tf:
                continue
            df = self.doc_freq.get(term, 0)
            idf = math.log(1 + (self.n_docs - df + 0.5) / (df + 0.5))
            freq = tf[term]
            denom = freq + self.k1 * (1 - self.b + self.b * doc_len / self.avg_len)
            total += idf * (freq * (self.k1 + 1)) / denom
        return total

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        query_terms = _tokenize(query)
        if not query_terms:
            return [meta for _, meta in self.docs[:limit]]
        scored = [
            (self.score(query_terms, idx), self.docs[idx][1])
            for idx in range(len(self.docs))
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [meta for score, meta in scored if score > 0][:limit]


def search_tools(registry: ToolRegistry, query: str, limit: int = 5) -> list[dict[str, Any]]:
    enabled_items = [item for item in registry.list_all() if item.get("enabled")]
    if not enabled_items:
        return []

    documents: list[tuple[str, dict[str, Any]]] = []
    for item in enabled_items:
        haystack = " ".join(
            filter(
                None,
                [item.get("name", ""), item.get("description", ""), item.get("category", "")],
            )
        )
        documents.append((haystack, item))

    bm25 = _SimpleBM25(documents)
    results = bm25.search(query, limit)
    if results:
        return results

    query_terms = set(_tokenize(query))
    scored: list[tuple[float, dict[str, Any]]] = []
    for item in enabled_items:
        haystack = " ".join(
            filter(
                None,
                [item.get("name", ""), item.get("description", ""), item.get("category", "")],
            )
        ).lower()
        hay_terms = set(_tokenize(haystack))
        if not hay_terms:
            continue
        overlap = len(query_terms & hay_terms)
        if overlap == 0 and not any(t in haystack for t in query_terms):
            continue
        score = overlap / len(query_terms)
        scored.append((score, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:limit]]


def create_tool_search_tool(registry: ToolRegistry, config: dict[str, Any]):
    from langchain_core.tools import tool

    limit = config.get("max_results", 5)

    @tool
    def tool_search(query: str) -> str:
        """Search available tools by keyword when unsure which tool to use."""
        results = search_tools(registry, query, limit)
        if not results:
            return "No matching tools found."
        lines = []
        for r in results:
            lines.append(
                f"- {r['name']} [{r['category']}] risk={r['risk']}: {r['description'][:120]}"
            )
        return "\n".join(lines)

    return tool_search
