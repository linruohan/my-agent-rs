from __future__ import annotations

from typing import Annotated

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    task_plan: list[str] | None
    retrieved_docs: list | None
    fresh_search_results: str | None
    metadata: dict
