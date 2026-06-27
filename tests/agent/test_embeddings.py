from __future__ import annotations

from unittest.mock import patch

from memory.rag_vector import get_embeddings


def test_get_embeddings_fake_fallback():
    cfg = {"embedding": {"provider": "local", "dimension": 128, "model": "missing-model"}}
    with patch("memory.rag_vector.load_rag_config", return_value=cfg):
        emb = get_embeddings()
        vec = emb.embed_query("hello")
        assert len(vec) == 128


def test_get_embeddings_openai(monkeypatch):
    cfg = {"embedding": {"provider": "openai", "model": "text-embedding-3-small"}}
    with patch("memory.rag_vector.load_rag_config", return_value=cfg):
        with patch("langchain_openai.OpenAIEmbeddings") as mock_cls:
            mock_cls.return_value.embed_query.return_value = [0.1, 0.2]
            emb = get_embeddings()
            assert emb is mock_cls.return_value
            mock_cls.assert_called_once_with(model="text-embedding-3-small")
