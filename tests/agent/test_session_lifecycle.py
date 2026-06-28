from __future__ import annotations

import pytest

from agent.runner import AgentRunner
from tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_purge_thread_data(tmp_path, monkeypatch):
    from langgraph.checkpoint.memory import MemorySaver
    from agent.graph import create_agent_graph
    from memory.chat_recall import get_chat_history_store

    monkeypatch.setenv("AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("memory.chat_recall._store", None)

    registry = ToolRegistry({})
    checkpointer = MemorySaver()
    graph = create_agent_graph(registry, checkpointer)
    runner = AgentRunner(graph, registry)

    thread_id = "test-thread-1"
    get_chat_history_store().record(
        thread_id, "hello world question", "hello world answer text here"
    )

    from infra.session_lifecycle import purge_thread_data

    await purge_thread_data(thread_id, runner=runner, checkpointer=checkpointer)

    store = get_chat_history_store()
    assert store.delete_by_thread_id(thread_id) == 0

    config = {"configurable": {"thread_id": thread_id}}
    state = await graph.aget_state(config)
    assert not state.values


@pytest.mark.asyncio
async def test_thread_busy_rejects_concurrent_run(tmp_path, monkeypatch):
    import asyncio

    from langgraph.checkpoint.memory import MemorySaver
    from agent.graph import create_agent_graph

    registry = ToolRegistry({})
    graph = create_agent_graph(registry, MemorySaver())
    runner = AgentRunner(graph, registry)

    events: list[dict] = []

    async def emit(msg):
        events.append(msg)

    async def slow_run():
        claimed = await runner._try_claim_thread("t1")
        assert claimed
        await asyncio.sleep(0.05)
        await runner._release_thread("t1")

    task = asyncio.create_task(slow_run())
    await asyncio.sleep(0.01)
    await runner.run("t1", "hi", emit)
    await task

    assert any(e.get("code") == "THREAD_BUSY" for e in events)
