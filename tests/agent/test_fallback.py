from __future__ import annotations

import pytest

from llm.fallback import DEFAULT_FALLBACK_CHAIN, get_fallback_chain, _provider_available


def test_default_fallback_chain():
    chain = get_fallback_chain()
    assert isinstance(chain, list)
    assert len(chain) >= 1


def test_provider_available_ollama_without_key():
    assert _provider_available("ollama") is True


def test_provider_available_missing_env(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    assert _provider_available("deepseek") is False


def test_provider_available_with_key(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    assert _provider_available("deepseek") is True


def test_create_llm_with_fallback_no_keys(monkeypatch):
    monkeypatch.setattr("llm.fallback._provider_available", lambda _name: False)
    from llm.fallback import create_llm_with_fallback

    with pytest.raises(RuntimeError, match="未检测到 API Key"):
        create_llm_with_fallback()
