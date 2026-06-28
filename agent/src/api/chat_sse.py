from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

EventCallback = Callable[[dict[str, Any]], Awaitable[None]]


def format_sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def stream_runner_events(
    thread_id: str,
    run: Callable[[EventCallback], Awaitable[None]],
) -> AsyncIterator[str]:
    """Bridge AgentRunner emit callbacks to SSE chunks."""
    from api.ws import clear_thread_emitter, set_thread_emitter

    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

    async def emit(msg: dict[str, Any]) -> None:
        await queue.put(msg)

    set_thread_emitter(thread_id, emit)
    task = asyncio.create_task(run(emit))

    try:
        while True:
            if task.done() and queue.empty():
                exc = task.exception()
                if exc is not None:
                    yield format_sse(
                        {
                            "type": "error",
                            "thread_id": thread_id,
                            "message": str(exc),
                            "code": "PROVIDER_ERROR",
                        }
                    )
                break
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=0.05)
            except asyncio.TimeoutError:
                continue
            if msg is None:
                break
            yield format_sse(msg)
            if msg.get("type") in ("done", "error"):
                break
        if not task.done():
            await task
        elif task.exception() is not None:
            raise task.exception()  # type: ignore[misc]
    finally:
        clear_thread_emitter(thread_id)
