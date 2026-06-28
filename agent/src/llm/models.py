from __future__ import annotations

import os
from typing import Any

import httpx

from llm.factory import load_provider


def _api_key_for_provider(cfg: dict[str, Any]) -> str:
    env_key = str(cfg.get("api_key_env", ""))
    if not env_key:
        return ""
    return os.environ.get(env_key, "")


def _dedupe_models(models: list[str], default_model: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    if default_model and default_model not in seen:
        seen.add(default_model)
        ordered.append(default_model)
    for model in models:
        if model and model not in seen:
            seen.add(model)
            ordered.append(model)
    return ordered


async def list_ollama_models(base_url: str) -> list[str]:
    url = f"{base_url.rstrip('/')}/api/tags"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
    return [m["name"] for m in data.get("models", []) if m.get("name")]


async def list_openai_compatible_models(base_url: str, api_key: str) -> list[str]:
    url = f"{base_url.rstrip('/')}/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    models = [m.get("id", "") for m in data.get("data", []) if m.get("id")]
    models.sort()
    return models


async def list_provider_models(provider_name: str) -> dict[str, Any]:
    cfg = load_provider(provider_name)
    provider_type = cfg.get("type", "openai_compatible")
    default_model = str(cfg.get("model", ""))
    source = "config"

    try:
        if provider_type == "ollama":
            base_url = str(cfg.get("base_url", "http://localhost:11434"))
            models = await list_ollama_models(base_url)
            source = "api" if models else "config"
            if not models and default_model:
                models = [default_model]
            return {
                "provider": provider_name,
                "models": _dedupe_models(models, default_model),
                "default_model": default_model,
                "source": source,
            }

        if provider_type == "openai_compatible":
            base_url = str(cfg.get("base_url", ""))
            api_key = _api_key_for_provider(cfg)
            if base_url and api_key and api_key != "not-needed":
                try:
                    models = await list_openai_compatible_models(base_url, api_key)
                    if models:
                        return {
                            "provider": provider_name,
                            "models": _dedupe_models(models, default_model),
                            "default_model": default_model,
                            "source": "api",
                        }
                except Exception:
                    pass

        if provider_type == "anthropic":
            fallback = [
                default_model,
                "claude-sonnet-4-20250514",
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
            ]
            return {
                "provider": provider_name,
                "models": _dedupe_models(fallback, default_model),
                "default_model": default_model,
                "source": "config",
            }

        models = [default_model] if default_model else []
        return {
            "provider": provider_name,
            "models": models,
            "default_model": default_model,
            "source": "config",
        }
    except Exception:
        models = [default_model] if default_model else []
        return {
            "provider": provider_name,
            "models": models,
            "default_model": default_model,
            "source": "fallback",
        }
