from __future__ import annotations

import os

from fastapi import APIRouter

from infra.config import load_app_config, load_llm_providers_config

router = APIRouter()


def get_version() -> str:
    return str(load_app_config().get("version", "0.1.0"))


def llm_key_status() -> dict[str, object]:
    cfg = load_llm_providers_config()
    provider = str(cfg.get("default_provider", "deepseek"))
    providers = cfg.get("providers", {})
    provider_cfg = providers.get(provider, {}) if isinstance(providers, dict) else {}
    if not isinstance(provider_cfg, dict):
        provider_cfg = {}
    if provider_cfg.get("type") == "ollama":
        return {"llm_provider": provider, "llm_key_configured": True}
    env_key = str(provider_cfg.get("api_key_env", ""))
    if not env_key:
        return {"llm_provider": provider, "llm_key_configured": True}
    val = os.environ.get(env_key, "")
    configured = bool(val and val != "not-needed")
    return {
        "llm_provider": provider,
        "llm_key_configured": configured,
        "llm_key_env": env_key,
    }


VERSION = get_version()


@router.get("/health")
async def health():
    return {"status": "ok", "version": get_version(), **llm_key_status()}
