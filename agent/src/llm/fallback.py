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
    default = cfg.get("default_provider", get_default_provider())
    chain = cfg.get("fallback_chain")
    if isinstance(chain, list) and chain:
        rest = [p for p in chain if p != default]
    else:
        rest = [p for p in DEFAULT_FALLBACK_CHAIN if p != default]
    ordered = [default, *rest]
    # Do not silently fall back to local Ollama unless user chose it.
    if default != "ollama":
        ordered = [p for p in ordered if p != "ollama"]
    return ordered


def _missing_key_message(name: str) -> str:
    return (
        f"Provider «{name}» 不可用：未检测到 API Key。"
        "请在「设置」页填写 API Key 并保存；保存后 Sidecar 会自动重启以加载密钥。"
    )


def _unknown_provider_message(name: str) -> str:
    return (
        f"Provider «{name}» 不存在或已被删除。"
        "请在「设置 → 集成 → 提供方」中重新选择有效的提供方。"
    )


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
    explicit = primary or get_default_provider()
    chain = get_fallback_chain()
    if primary and primary not in chain:
        chain = [primary, *[p for p in chain if p != primary]]
    elif primary:
        chain = [primary, *[p for p in chain if p != primary]]

    last_error: Exception | None = None
    missing_key_providers: list[str] = []
    for name in chain:
        if not _provider_available(name):
            if name == explicit:
                missing_key_providers.append(name)
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
            if name == explicit:
                raise RuntimeError(
                    f"Provider «{explicit}» 初始化失败: {e}"
                ) from e

    if explicit in missing_key_providers:
        try:
            load_provider(explicit)
        except ValueError:
            raise RuntimeError(_unknown_provider_message(explicit)) from None
        raise RuntimeError(_missing_key_message(explicit))

    try:
        load_provider(explicit)
    except ValueError:
        raise RuntimeError(_unknown_provider_message(explicit)) from None

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
                base_url = cfg.get("base_url", "")
                logger.warning(
                    "Provider {} API error: {} (base_url={})",
                    name,
                    e,
                    base_url or "default",
                )
                continue
            raise

    explicit = primary or get_default_provider()
    try:
        load_provider(explicit)
    except ValueError:
        raise RuntimeError(_unknown_provider_message(explicit)) from None

    if not _provider_available(explicit):
        raise RuntimeError(_missing_key_message(explicit))

    hint = ""
    if explicit == "custom" or is_user_custom_provider(explicit):
        hint = " 请检查设置中的自定义 API 网关地址、模型名与密钥是否正确。"
    if last_error:
        raise RuntimeError(f"All LLM providers unavailable: {last_error}.{hint}") from last_error
    raise RuntimeError(f"All LLM providers unavailable (no API keys configured).{hint}")


def is_user_custom_provider(provider_id: str) -> bool:
    return provider_id == "custom" or provider_id.startswith("custom_")
