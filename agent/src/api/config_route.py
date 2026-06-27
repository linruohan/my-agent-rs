from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from infra.config import load_user_llm_config, save_user_llm_config

router = APIRouter()


class CustomProviderConfig(BaseModel):
    base_url: str = Field(min_length=1)
    model: str = Field(min_length=1)


class LlmUserConfigBody(BaseModel):
    default_provider: str = Field(min_length=1)
    custom: CustomProviderConfig | None = None


@router.get("/config/llm")
async def get_llm_user_config():
    return load_user_llm_config()


@router.put("/config/llm")
async def put_llm_user_config(body: LlmUserConfigBody):
    data: dict[str, Any] = {"default_provider": body.default_provider}
    if body.default_provider == "custom" and body.custom:
        data["custom"] = body.custom.model_dump()
    save_user_llm_config(data)
    return {"ok": True, **data}
