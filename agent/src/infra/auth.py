from __future__ import annotations

import os
import secrets
from pathlib import Path

from infra.config import get_data_dir

TOKEN_FILE = ".sidecar_token"


def get_or_create_token() -> str:
    """Return sidecar auth token from env, file, or create a new one."""
    env_token = os.environ.get("SIDECAR_AUTH_TOKEN", "").strip()
    if env_token:
        return env_token

    path = get_data_dir() / TOKEN_FILE
    if path.exists():
        token = path.read_text(encoding="utf-8").strip()
        if token:
            return token

    token = secrets.token_urlsafe(32)
    get_data_dir().mkdir(parents=True, exist_ok=True)
    path.write_text(token, encoding="utf-8")
    return token


def verify_token(provided: str) -> bool:
    if not provided:
        return False
    expected = get_or_create_token()
    return secrets.compare_digest(provided, expected)


def auth_required() -> bool:
    return bool(get_or_create_token())
