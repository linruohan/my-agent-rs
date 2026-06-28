from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

from llm.factory import load_provider
from infra.config import provider_api_key_env

_LEGACY_PROVIDER_KEY_ENV: dict[str, str] = {
    "custom": "CUSTOM_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "qwen": "DASHSCOPE_API_KEY",
    "moonshot": "MOONSHOT_API_KEY",
    "zhipu": "ZHIPU_API_KEY",
    "groq": "GROQ_API_KEY",
    "siliconflow": "SILICONFLOW_API_KEY",
}


def _api_key_for_provider(cfg: dict[str, Any]) -> str:
    candidates: list[str] = []
    env_key = str(cfg.get("api_key_env", ""))
    if env_key:
        candidates.append(env_key)
    name = str(cfg.get("name", ""))
    if name:
        candidates.append(provider_api_key_env(name))
        legacy = _LEGACY_PROVIDER_KEY_ENV.get(name)
        if legacy:
            candidates.append(legacy)
    seen: set[str] = set()
    for key in candidates:
        if key in seen:
            continue
        seen.add(key)
        value = os.environ.get(key, "")
        if value and value != "not-needed":
            return value
    return ""


def _normalize_openai_base_url(base_url: str) -> str:
    url = base_url.strip().rstrip("/")
    for suffix in ("/chat/completions", "/completions"):
        if url.endswith(suffix):
            url = url[: -len(suffix)].rstrip("/")
    return url


def _parse_openai_compatible_model_ids(data: Any) -> list[str]:
    models: list[str] = []
    if isinstance(data, dict):
        items = data.get("data")
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    model_id = item.get("id") or item.get("name") or item.get("model")
                    if model_id:
                        models.append(str(model_id))
        raw_models = data.get("models")
        if isinstance(raw_models, list):
            for item in raw_models:
                if isinstance(item, dict):
                    model_id = item.get("id") or item.get("name") or item.get("model")
                    if model_id:
                        models.append(str(model_id))
                elif isinstance(item, str) and item:
                    models.append(item)
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                model_id = item.get("id") or item.get("name") or item.get("model")
                if model_id:
                    models.append(str(model_id))
            elif isinstance(item, str) and item:
                models.append(item)
    return sorted({m for m in models if m})


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


def _test_result(ok: bool, status_code: int) -> dict[str, Any]:
    return {"ok": ok, "status_code": status_code}


_CONNECT_TIMEOUT = 5.0
_READ_TIMEOUT = 25.0


def _test_http_timeout() -> httpx.Timeout:
    return httpx.Timeout(
        connect=_CONNECT_TIMEOUT,
        read=_READ_TIMEOUT,
        write=_CONNECT_TIMEOUT,
        pool=_CONNECT_TIMEOUT,
    )


async def list_ollama_models(base_url: str) -> list[str]:
    url = f"{base_url.rstrip('/')}/api/tags"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
    return [m["name"] for m in data.get("models", []) if m.get("name")]


async def list_openai_compatible_models(base_url: str, api_key: str) -> list[str]:
    url = f"{_normalize_openai_base_url(base_url)}/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    return _parse_openai_compatible_model_ids(data)


async def test_openai_compatible_models(
    base_url: str, api_key: str, models: list[str], *, concurrency: int = 4
) -> dict[str, dict[str, Any]]:
    normalized = _normalize_openai_base_url(base_url)
    sem = asyncio.Semaphore(concurrency)
    results: dict[str, dict[str, Any]] = {}

    async def run_one(name: str) -> None:
        async with sem:
            results[name] = await _test_openai_compatible_model(normalized, api_key, name)

    await asyncio.gather(*(run_one(m) for m in models))
    return results


async def _test_openai_compatible_model(
    base_url: str, api_key: str, model: str
) -> dict[str, Any]:
    url = f"{_normalize_openai_base_url(base_url)}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Hi"}],
    }
    try:
        async with httpx.AsyncClient(timeout=_test_http_timeout()) as client:
            resp = await client.post(url, headers=headers, json=payload)
            return _test_result(resp.status_code == 200, resp.status_code)
    except httpx.TimeoutException:
        return _test_result(False, 408)
    except httpx.HTTPStatusError as exc:
        return _test_result(False, exc.response.status_code)
    except Exception:
        return _test_result(False, 0)


async def _test_ollama_model(base_url: str, model: str) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/api/chat"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Hi"}],
        "stream": False,
    }
    try:
        async with httpx.AsyncClient(timeout=_test_http_timeout()) as client:
            resp = await client.post(url, json=payload)
            return _test_result(resp.status_code == 200, resp.status_code)
    except httpx.TimeoutException:
        return _test_result(False, 408)
    except httpx.HTTPStatusError as exc:
        return _test_result(False, exc.response.status_code)
    except Exception:
        return _test_result(False, 0)


async def _test_anthropic_model(api_key: str, model: str) -> dict[str, Any]:
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "Hi"}],
    }
    try:
        async with httpx.AsyncClient(timeout=_test_http_timeout()) as client:
            resp = await client.post(url, headers=headers, json=payload)
            return _test_result(resp.status_code == 200, resp.status_code)
    except httpx.TimeoutException:
        return _test_result(False, 408)
    except httpx.HTTPStatusError as exc:
        return _test_result(False, exc.response.status_code)
    except Exception:
        return _test_result(False, 0)


async def test_provider_model(provider_name: str, model: str) -> dict[str, Any]:
    cfg = load_provider(provider_name)
    provider_type = cfg.get("type", "openai_compatible")

    if provider_type == "ollama":
        base_url = str(cfg.get("base_url", "http://localhost:11434"))
        return await _test_ollama_model(base_url, model)

    if provider_type == "anthropic":
        api_key = _api_key_for_provider(cfg)
        if not api_key or api_key == "not-needed":
            return _test_result(False, 401)
        return await _test_anthropic_model(api_key, model)

    base_url = str(cfg.get("base_url", ""))
    api_key = _api_key_for_provider(cfg)
    if not base_url or not api_key or api_key == "not-needed":
        return _test_result(False, 401)
    return await _test_openai_compatible_model(base_url, api_key, model)


async def test_provider_models(
    provider_name: str, models: list[str], *, concurrency: int = 4
) -> dict[str, dict[str, Any]]:
    sem = asyncio.Semaphore(concurrency)
    results: dict[str, dict[str, Any]] = {}

    async def run_one(name: str) -> None:
        async with sem:
            results[name] = await test_provider_model(provider_name, name)

    await asyncio.gather(*(run_one(m) for m in models))
    return results


async def list_provider_models(provider_name: str, *, test: bool = False) -> dict[str, Any]:
    cfg = load_provider(provider_name)
    provider_type = cfg.get("type", "openai_compatible")
    default_model = str(cfg.get("model", ""))
    source = "config"
    models: list[str] = []

    try:
        if provider_type == "ollama":
            base_url = str(cfg.get("base_url", "http://localhost:11434"))
            models = await list_ollama_models(base_url)
            source = "api" if models else "config"
            if not models and default_model:
                models = [default_model]

        elif provider_type == "openai_compatible":
            base_url = str(cfg.get("base_url", ""))
            api_key = _api_key_for_provider(cfg)
            if base_url and api_key:
                try:
                    fetched = await list_openai_compatible_models(base_url, api_key)
                    if fetched:
                        models = fetched
                        source = "api"
                except Exception:
                    pass

        elif provider_type == "anthropic":
            models = [
                default_model,
                "claude-sonnet-4-20250514",
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
            ]

        if not models and default_model:
            models = [default_model]
    except Exception:
        source = "fallback"
        models = [default_model] if default_model else []

    deduped = _dedupe_models(models, default_model)
    result: dict[str, Any] = {
        "provider": provider_name,
        "models": deduped,
        "default_model": default_model,
        "source": source,
    }
    if test and deduped:
        result["tests"] = await test_provider_models(provider_name, deduped)
    return result
