from __future__ import annotations

import os
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from infra.config import load_llm_providers_config


def get_default_provider() -> str:
    cfg = load_llm_providers_config()
    return cfg.get("default_provider", "deepseek")


def load_provider(name: str | None = None) -> dict[str, Any]:
    cfg = load_llm_providers_config()
    provider_name = name or cfg.get("default_provider", "deepseek")
    providers = cfg.get("providers", {})
    if provider_name not in providers:
        raise ValueError(f"Unknown provider: {provider_name}")
    return {"name": provider_name, **providers[provider_name]}


def create_llm(provider_cfg: dict[str, Any] | None = None, **kwargs: Any) -> BaseChatModel:
    cfg = provider_cfg or load_provider()
    provider_type = cfg.get("type", "openai_compatible")
    model = cfg.get("model", "gpt-4o")
    temperature = kwargs.pop("temperature", 0.7)

    if provider_type == "anthropic":
        from langchain_anthropic import ChatAnthropic

        api_key = os.environ.get(cfg.get("api_key_env", "ANTHROPIC_API_KEY"), "")
        return ChatAnthropic(model=model, api_key=api_key, temperature=temperature, **kwargs)

    if provider_type == "ollama":
        try:
            from langchain_ollama import ChatOllama
        except ImportError:
            from langchain_community.chat_models import ChatOllama

        base_url = cfg.get("base_url", "http://localhost:11434")
        return ChatOllama(model=model, base_url=base_url, temperature=temperature, **kwargs)

    from langchain_openai import ChatOpenAI

    api_key_env = cfg.get("api_key_env", "OPENAI_API_KEY")
    api_key = os.environ.get(api_key_env, "not-needed")
    base_url = cfg.get("base_url")
    llm_kwargs: dict[str, Any] = {
        "model": model,
        "api_key": api_key,
        "temperature": temperature,
        "timeout": cfg.get("timeout_sec", 60),
        "max_retries": cfg.get("max_retries", 2),
        **kwargs,
    }
    if base_url:
        llm_kwargs["base_url"] = base_url
    return ChatOpenAI(**llm_kwargs)
