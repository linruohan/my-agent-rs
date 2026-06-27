from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from infra.config import load_app_config


class HitlTimeoutManager:
    """Auto-reject HITL interrupts after configured timeout."""

    def __init__(self):
        cfg = load_app_config().get("hitl", {})
        self.timeout_sec = int(cfg.get("timeout_sec", 300))
        self.on_timeout = cfg.get("on_timeout", "reject")
        self._tasks: dict[str, asyncio.Task] = {}
        self._resume_callback = None

    def set_resume_callback(self, cb):
        self._resume_callback = cb

    def schedule(self, thread_id: str) -> None:
        self.cancel(thread_id)

        async def _wait():
            await asyncio.sleep(self.timeout_sec)
            if self._resume_callback and self.on_timeout == "reject":
                await self._resume_callback(thread_id, "reject", None)

        self._tasks[thread_id] = asyncio.create_task(_wait())

    def cancel(self, thread_id: str) -> None:
        task = self._tasks.pop(thread_id, None)
        if task and not task.done():
            task.cancel()


hitl_timeout_manager = HitlTimeoutManager()
