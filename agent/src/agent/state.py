from __future__ import annotations

from typing import Annotated

from langgraph.graph.message import add_messages
from langgraph.managed import RemainingSteps
from typing_extensions import NotRequired, TypedDict


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    pending_action: dict | None
    task_plan: list[str] | None
    retrieved_docs: list | None
    fresh_search_results: str | None
    metadata: dict
    remaining_steps: NotRequired[RemainingSteps]
