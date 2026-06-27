from __future__ import annotations

from tools.business.email import send_smtp_email


def test_send_email_not_configured(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_USER", raising=False)
    result = send_smtp_email("a@b.com", "Hi", "Body")
    assert "not configured" in result.lower()
