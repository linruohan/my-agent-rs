from __future__ import annotations

import pytest


def test_outlook_available_false_on_non_windows(monkeypatch):
    monkeypatch.setattr("tools.business.outlook_adapter.sys.platform", "linux")
    from tools.business.outlook_adapter import outlook_available

    assert outlook_available() is False


def test_read_outlook_without_pywin32(monkeypatch):
    monkeypatch.setattr("tools.business.outlook_adapter.sys.platform", "win32")
    import builtins

    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "win32com.client":
            raise ImportError("no pywin32")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)
    from tools.business.outlook_adapter import read_outlook_events

    events, err = read_outlook_events()
    assert events == []
    assert "not available" in err.lower() or err


def test_send_outlook_unavailable(monkeypatch):
    monkeypatch.setattr("tools.business.outlook_adapter.sys.platform", "linux")
    from tools.business.outlook_adapter import send_outlook_email

    ok, msg = send_outlook_email("a@b.com", "s", "b")
    assert ok is False
    assert "not available" in msg.lower()
