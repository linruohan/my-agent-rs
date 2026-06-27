from __future__ import annotations

import os
from typing import Any, Callable, TypeVar

from langchain_core.language_models.chat_models import BaseChatModel
from loguru import logger

from llm.factory import create_llm, get_default_provider, load_provider

T = TypeVar("T")

DEFAULT_FALLBACK_CHAIN = ["deepseek", "qwen", "ollama"]


def get_fallback_chain() -> list[str]:
    from infra.config import load_llm_providers_config

    cfg = load_llm_providers_config()
    chain = cfg.get("fallback_chain")
    if isinstance(chain, list) and chain:
        return chain
    default = cfg.get("default_provider", get_default_provider())
    rest = [p for p in DEFAULT_FALLBACK_CHAIN if p != default]
    return [default, *rest]


def _provider_available(name: str) -> bool:
    try:
        cfg = load_provider(name)
    except ValueError:
        return False
    if cfg.get("type") == "ollama":
        return True
    env_key = cfg.get("api_key_env", "")
    if not env_key:
        return True
    val = os.environ.get(env_key, "")
    return bool(val and val != "not-needed")


def create_llm_with_fallback(
    primary: str | None = None,
    **kwargs: Any,
) -> tuple[BaseChatModel, str]:
    """Create LLM trying primary then fallback chain. Returns (llm, provider_name)."""
    chain = get_fallback_chain()
    if primary and primary not in chain:
        chain = [primary, *chain]
    elif primary:
        chain = [primary] + [p for p in chain if p != primary]

    last_error: Exception | None = None
    for name in chain:
        if not _provider_available(name):
            logger.debug("Skipping provider {} (no API key or unknown)", name)
            continue
        try:
            cfg = load_provider(name)
            llm = create_llm(cfg, **kwargs)
            logger.info("Using LLM provider: {}", name)
            return llm, name
        except Exception as e:
            last_error = e
            logger.warning("Provider {} init failed: {}", name, e)

    if last_error:
        raise RuntimeError(f"All LLM providers unavailable: {last_error}") from last_error
    raise RuntimeError("All LLM providers unavailable (no API keys configured)")


def invoke_with_fallback(
    invoke_fn: Callable[[BaseChatModel], T],
    primary: str | None = None,
    **llm_kwargs: Any,
) -> tuple[T, str]:
    """Invoke LLM operation with provider fallback on connection/timeout errors."""
    chain = get_fallback_chain()
    if primary:
        chain = [primary] + [p for p in chain if p != primary]

    last_error: Exception | None = None
    for name in chain:
        if not _provider_available(name):
            continue
        try:
            cfg = load_provider(name)
            llm = create_llm(cfg, **llm_kwargs)
            result = invoke_fn(llm)
            return result, name
        except (TimeoutError, ConnectionError, OSError) as e:
            last_error = e
            logger.warning("Provider {} request failed: {}", name, e)
        except Exception as e:
            err_name = type(e).__name__
            if err_name in ("APITimeoutError", "RateLimitError", "APIConnectionError"):
                last_error = e
                logger.warning("Provider {} API error: {}", name, e)
                continue
            raise

    raise RuntimeError(f"All LLM providers unavailable: {last_error}")
