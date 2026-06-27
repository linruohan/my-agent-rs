from __future__ import annotations

from fastapi import APIRouter

from infra.config import load_app_config

router = APIRouter()


def get_version() -> str:
    return str(load_app_config().get("version", "0.1.0"))


VERSION = get_version()


@router.get("/health")
async def health():
    return {"status": "ok", "version": get_version()}
