from __future__ import annotations

import os
import sys
from pathlib import Path

AGENT_SRC = Path(__file__).resolve().parents[1] / "agent" / "src"
if str(AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(AGENT_SRC))

from infra.auth import auth_required, get_or_create_token, verify_token


def test_get_or_create_token():
    token = get_or_create_token()
    assert isinstance(token, str)
    assert len(token) >= 16


def test_verify_token():
    token = get_or_create_token()
    assert verify_token(token) is True
    assert verify_token("invalid-token") is False


def test_auth_required():
    assert auth_required() is True


def test_auth_disabled(monkeypatch):
    monkeypatch.setenv("SIDECAR_AUTH_DISABLED", "true")
    assert auth_required() is False
    monkeypatch.delenv("SIDECAR_AUTH_DISABLED", raising=False)
