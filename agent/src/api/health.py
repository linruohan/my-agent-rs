from __future__ import annotations

import os

from fastapi import APIRouter, Request

from infra.config import load_app_config, load_llm_providers_config
from infra.auth import auth_required, get_or_create_token

router = APIRouter()


def get_version() -> str:
    return str(load_app_config().get("version", "0.1.0"))


def get_api_version() -> str:
    return os.environ.get("AGENT_API_VERSION", get_version())


def get_expected_version() -> str:
    return os.environ.get("AGENT_EXPECTED_VERSION", get_version())


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


def build_health_payload() -> dict[str, object]:
    api_version = get_api_version()
    expected = get_expected_version()
    return {
        "status": "ok",
        "version": get_version(),
        "api_version": api_version,
        "expected_version": expected,
        "version_ok": api_version == expected,
        "auth_required": auth_required(),
        **llm_key_status(),
    }


@router.get("/health")
async def health():
    return build_health_payload()


@router.get("/metrics")
async def metrics():
    from infra.metrics import snapshot

    return snapshot()


@router.get("/metrics/prometheus")
async def metrics_prometheus():
    from fastapi.responses import PlainTextResponse
    from infra.metrics import prometheus_text

    return PlainTextResponse(prometheus_text(), media_type="text/plain; version=0.0.4")


@router.get("/auth/token")
async def auth_token(request: Request):
    host = request.client.host if request.client else request.url.hostname or ""
    if host not in ("127.0.0.1", "::1", "localhost", "testserver", "testclient"):
        return {"error": "forbidden"}
    return {"token": get_or_create_token()}
