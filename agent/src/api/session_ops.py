from __future__ import annotations

from agent.runner import AgentRunner
from infra.session_lifecycle import purge_thread_data
from infra.session_store import SessionStore


def create_session_record(
    session_store: SessionStore,
    title: str | None = None,
) -> dict:
    return session_store.create(title)


async def delete_session_record(
    thread_id: str,
    *,
    session_store: SessionStore,
    runner: AgentRunner,
) -> bool:
    if not thread_id:
        return False
    ok = session_store.delete(thread_id)
    if not ok:
        return False
    checkpointer = getattr(getattr(runner, "graph", None), "checkpointer", None)
    await purge_thread_data(
        thread_id,
        runner=runner,
        checkpointer=checkpointer,
    )
    return True


def set_session_archived(
    session_store: SessionStore,
    thread_id: str,
    archived: bool,
) -> bool:
    if not thread_id:
        return False
    return session_store.set_archived(thread_id, archived)
