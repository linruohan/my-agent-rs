from __future__ import annotations

import asyncio
from typing import Any, Callable

_main_loop: asyncio.AbstractEventLoop | None = None
_broadcast: Callable[[dict[str, Any]], None] | None = None


def set_main_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _main_loop
    _main_loop = loop


def configure_broadcast(schedule: Callable[[dict[str, Any]], None]) -> None:
    global _broadcast
    _broadcast = schedule


def schedule_broadcast(msg: dict[str, Any]) -> None:
    if _broadcast is not None:
        _broadcast(msg)
        return
    if _main_loop is None:
        return
    from api.ws import manager

    asyncio.run_coroutine_threadsafe(manager.broadcast(msg), _main_loop)


def notify_tasks_changed(reason: str = "mutated") -> None:
    schedule_broadcast({"type": "tasks.changed", "reason": reason})
