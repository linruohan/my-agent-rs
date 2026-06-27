from __future__ import annotations

import asyncio

import pytest

from infra.hitl import HitlTimeoutManager


@pytest.mark.asyncio
async def test_hitl_timeout_auto_reject():
    manager = HitlTimeoutManager()
    manager.timeout_sec = 1
    manager.on_timeout = "reject"
    called = []

    async def cb(thread_id, decision, edited_args):
        called.append((thread_id, decision))

    manager.set_resume_callback(cb)
    manager.schedule("thread-1")
    await asyncio.sleep(1.2)
    assert ("thread-1", "reject") in called
    manager.cancel("thread-1")
