from __future__ import annotations

import asyncio

import pytest

from infra.hitl import HitlTimeoutManager


@pytest.mark.asyncio
async def test_hitl_timeout_auto_reject(monkeypatch):
    monkeypatch.setattr(
        "infra.hitl.load_effective_app_config",
        lambda: {"hitl": {"timeout_sec": 1, "on_timeout": "reject", "notify_before_sec": 0}},
    )
    manager = HitlTimeoutManager()
    called = []

    async def cb(thread_id, decision, edited_args):
        called.append((thread_id, decision))

    manager.set_resume_callback(cb)
    manager.schedule("thread-1")
    await asyncio.sleep(1.2)
    assert ("thread-1", "reject") in called
    manager.cancel("thread-1")
