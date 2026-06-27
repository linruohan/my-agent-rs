from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.prebuilt import create_react_agent

from infra.config import get_data_dir
from llm.factory import create_llm, load_provider
from tools.registry import ToolRegistry


def get_checkpointer() -> SqliteSaver:
    checkpoint_dir = get_data_dir() / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    db_path = checkpoint_dir / "checkpoints.db"
    conn = __import__("sqlite3").connect(str(db_path), check_same_thread=False)
    return SqliteSaver(conn)


def create_agent_graph(
    registry: ToolRegistry,
    checkpointer: SqliteSaver | None = None,
    llm: BaseChatModel | None = None,
):
    tools = registry.get_enabled_tools()
    if llm is None:
        llm = create_llm(load_provider())
    if tools:
        llm = llm.bind_tools(tools)
    return create_react_agent(llm, tools, checkpointer=checkpointer)
