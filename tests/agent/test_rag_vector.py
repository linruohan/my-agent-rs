from __future__ import annotations

from memory.rag_vector import merge_search_results


def test_merge_search_results_rrf():
    keyword = [
        {"source": "a.md", "chunk_index": 0, "content": "alpha", "score": 0.5, "method": "keyword"},
        {"source": "b.md", "chunk_index": 0, "content": "beta", "score": 0.3, "method": "keyword"},
    ]
    vector = [
        {"source": "a.md", "chunk_index": 0, "content": "alpha", "score": 0.9, "method": "vector"},
        {"source": "c.md", "chunk_index": 0, "content": "gamma", "score": 0.8, "method": "vector"},
    ]
    merged = merge_search_results(keyword, vector, top_k=3)
    assert len(merged) == 3
    sources = [m["source"] for m in merged]
    assert "a.md" in sources
    assert merged[0]["source"] == "a.md"
