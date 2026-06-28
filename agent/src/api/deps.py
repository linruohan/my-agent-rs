from __future__ import annotations

from typing import Annotated

from fastapi import Header, HTTPException

from infra.auth import auth_required, verify_token


def require_auth(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Bearer token auth for REST routes; no-op when auth is disabled."""
    if not auth_required():
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization[7:].strip()
    if not verify_token(token):
        raise HTTPException(status_code=401, detail="Unauthorized")
