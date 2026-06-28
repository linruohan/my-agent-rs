from __future__ import annotations

from typing import Any

from loguru import logger

from agent.runner import AgentRunner


async def purge_thread_data(
    thread_id: str,
    *,
    runner: AgentRunner | None = None,
    checkpointer: Any | None = None,
) -> None:
    """Remove all persisted state for a conversation thread."""
    if runner is not None:
        await runner.stop(thread_id)
        runner.clear_thread_state(thread_id)

    if checkpointer is not None:
        try:
            await checkpointer.adelete_thread(thread_id)
        except Exception as exc:
            logger.warning("Failed to delete checkpoint for {}: {}", thread_id, exc)

    from memory.chat_recall import get_chat_history_store

    get_chat_history_store().delete_by_thread_id(thread_id)

    from api.ws import clear_thread_emitter

    clear_thread_emitter(thread_id)
