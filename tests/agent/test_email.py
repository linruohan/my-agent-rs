from __future__ import annotations

import json

from tools.business.email import read_email_unified, send_email_unified, send_smtp_email


def test_send_email_not_configured(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.setattr("tools.business.email.sys.platform", "linux")
    result = send_email_unified("a@b.com", "Hi", "Body")
    assert "失败" in result or "not configured" in result.lower()


def test_send_smtp_only(monkeypatch):
    monkeypatch.setattr("tools.business.email.sys.platform", "linux")
    result = send_smtp_email("a@b.com", "Hi", "Body")
    assert "not configured" in result.lower()


def test_read_email_non_windows(monkeypatch):
    monkeypatch.setattr("tools.business.email.sys.platform", "linux")
    result = read_email_unified()
    assert "Windows" in result


def test_read_email_outlook_unavailable(monkeypatch):
    monkeypatch.setattr("tools.business.email.sys.platform", "win32")
    monkeypatch.setattr(
        "tools.business.outlook_adapter.outlook_available",
        lambda: False,
    )
    result = read_email_unified()
    assert "不可用" in result or "not available" in result.lower()


def test_read_email_outlook_success(monkeypatch):
    monkeypatch.setattr("tools.business.email.sys.platform", "win32")
    monkeypatch.setattr(
        "tools.business.outlook_adapter.outlook_available",
        lambda: True,
    )
    sample = [
        {
            "id": "outlook-mail-abc",
            "subject": "Hello",
            "from": "Alice",
            "from_email": "a@b.com",
            "received_time": "2026-01-01",
            "unread": True,
            "preview": "Hi",
            "folder": "inbox",
            "source": "outlook",
        }
    ]
    monkeypatch.setattr(
        "tools.business.outlook_adapter.read_outlook_inbox",
        lambda folder, limit, unread_only: (sample, ""),
    )
    result = read_email_unified(limit=5, unread_only=True)
    data = json.loads(result)
    assert data[0]["subject"] == "Hello"
