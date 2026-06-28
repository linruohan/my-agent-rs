from __future__ import annotations

import asyncio
from typing import Any

from infra.config import load_effective_app_config


class HitlTimeoutManager:
    """Auto-reject HITL interrupts after configured timeout."""

    def __init__(self):
        self._reload_config()
        self._tasks: dict[str, asyncio.Task] = {}
        self._notify_callbacks: dict[str, Any] = {}
        self._resume_callback = None

    def _reload_config(self) -> None:
        cfg = load_effective_app_config().get("hitl", {})
        self.timeout_sec = int(cfg.get("timeout_sec", 300))
        self.on_timeout = cfg.get("on_timeout", "reject")
        self.notify_before_sec = int(cfg.get("notify_before_sec", 0))

    def set_resume_callback(self, cb):
        self._resume_callback = cb

    def set_notify_callback(self, cb):
        """Optional callback(thread_id) for timeout warning."""
        self._notify_callbacks["default"] = cb

    def schedule(self, thread_id: str) -> None:
        self._reload_config()
        self.cancel(thread_id)

        async def _wait():
            if self.notify_before_sec > 0 and self.timeout_sec > self.notify_before_sec:
                await asyncio.sleep(self.timeout_sec - self.notify_before_sec)
                cb = self._notify_callbacks.get("default")
                if cb and thread_id in self._tasks:
                    await cb(thread_id, self.notify_before_sec)
                await asyncio.sleep(self.notify_before_sec)
            else:
                await asyncio.sleep(self.timeout_sec)

            if self._resume_callback and self.on_timeout == "reject":
                await self._resume_callback(thread_id, "reject", None)

        self._tasks[thread_id] = asyncio.create_task(_wait())

    def cancel(self, thread_id: str) -> None:
        task = self._tasks.pop(thread_id, None)
        if task and not task.done():
            task.cancel()


hitl_timeout_manager = HitlTimeoutManager()
