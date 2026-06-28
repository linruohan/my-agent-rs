"""WebSocket message schemas (companion to REST OpenAPI).

Exported via GET /openapi/ws-protocol.json and scripts/generate_ws_types.py.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ConnectedEvent(BaseModel):
    type: Literal["connected"] = "connected"
    port: int
    version: str = ""
    auth_required: bool = False


class AuthOkEvent(BaseModel):
    type: Literal["auth.ok"] = "auth.ok"


class PongEvent(BaseModel):
    type: Literal["pong"] = "pong"


class TokenEvent(BaseModel):
    type: Literal["token"] = "token"
    thread_id: str = ""
    content: str = ""


class ToolProgressEvent(BaseModel):
    type: Literal["tool_progress"] = "tool_progress"
    thread_id: str = ""
    tool_name: str = ""
    tool_call_id: str | None = None
    status: str = ""


class ToolStartEvent(BaseModel):
    type: Literal["tool_start"] = "tool_start"
    thread_id: str = ""
    name: str = ""
    args: dict[str, Any] = Field(default_factory=dict)
    category: str | None = None
    tool_call_id: str | None = None


class ToolEndEvent(BaseModel):
    type: Literal["tool_end"] = "tool_end"
    thread_id: str = ""
    name: str = ""
    result: str = ""
    category: str | None = None
    tool_call_id: str | None = None
    citations: list[dict[str, str]] | None = None


class InterruptEvent(BaseModel):
    type: Literal["interrupt"] = "interrupt"
    thread_id: str = ""
    action: str = ""
    preview: str = ""
    args: dict[str, Any] = Field(default_factory=dict)


class InterruptTimeoutWarningEvent(BaseModel):
    type: Literal["interrupt_timeout_warning"] = "interrupt_timeout_warning"
    thread_id: str = ""
    seconds_left: int = 0


class DoneMetadata(BaseModel):
    duration_ms: int | None = None
    task_data_changed: bool | None = None
    token_usage: dict[str, int] | None = None
    ocr: bool | None = None
    slash: bool | None = None


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"
    thread_id: str = ""
    metadata: DoneMetadata | dict[str, Any] = Field(default_factory=dict)


class TasksChangedEvent(BaseModel):
    type: Literal["tasks.changed"] = "tasks.changed"
    reason: str = ""


class SchedulerReminderEvent(BaseModel):
    type: Literal["scheduler.reminder"] = "scheduler.reminder"
    title: str = ""
    message: str = ""


class SessionArchivedEvent(BaseModel):
    type: Literal["session.archived"] = "session.archived"
    sessions: list[dict[str, Any]] = Field(default_factory=list)


class SessionArchivedOneEvent(BaseModel):
    type: Literal["session.archived_one"] = "session.archived_one"
    thread_id: str = ""
    ok: bool = False


class SessionUnarchivedOneEvent(BaseModel):
    type: Literal["session.unarchived_one"] = "session.unarchived_one"
    thread_id: str = ""
    ok: bool = False


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str = ""
    code: str | None = None
    thread_id: str | None = None


class SessionListEvent(BaseModel):
    type: Literal["session.list"] = "session.list"
    sessions: list[dict[str, Any]] = Field(default_factory=list)


class SessionCreatedEvent(BaseModel):
    type: Literal["session.created"] = "session.created"
    thread_id: str = ""
    title: str = ""
    created_at: str = ""


class SessionDeletedEvent(BaseModel):
    type: Literal["session.deleted"] = "session.deleted"
    thread_id: str = ""
    ok: bool | None = None


class SessionHistoryEvent(BaseModel):
    type: Literal["session.history"] = "session.history"
    thread_id: str = ""
    messages: list[dict[str, Any]] = Field(default_factory=list)


class RagListEvent(BaseModel):
    type: Literal["rag.list"] = "rag.list"
    sources: list[str] = Field(default_factory=list)


class RagIngestEvent(BaseModel):
    type: Literal["rag.ingest"] = "rag.ingest"
    result: str = ""


class RagSearchEvent(BaseModel):
    type: Literal["rag.search"] = "rag.search"
    query: str | None = None
    results: list[dict[str, Any]] = Field(default_factory=list)


class RagDeletedEvent(BaseModel):
    type: Literal["rag.deleted"] = "rag.deleted"
    source: str | None = None
    ok: bool | None = None


class ChatStoppedEvent(BaseModel):
    type: Literal["chat.stopped"] = "chat.stopped"
    thread_id: str = ""
    ok: bool = False


class MemoryGetEvent(BaseModel):
    type: Literal["memory.get"] = "memory.get"
    namespace: str = ""
    key: str = ""
    value: Any = None


class MemorySetEvent(BaseModel):
    type: Literal["memory.set"] = "memory.set"
    namespace: str = ""
    key: str = ""
    ok: bool = True


class SchedulerListEvent(BaseModel):
    type: Literal["scheduler.list"] = "scheduler.list"
    jobs: list[dict[str, Any]] = Field(default_factory=list)


SERVER_EVENT_MODELS: tuple[type[BaseModel], ...] = (
    ConnectedEvent,
    AuthOkEvent,
    PongEvent,
    TokenEvent,
    ToolProgressEvent,
    ToolStartEvent,
    ToolEndEvent,
    InterruptEvent,
    InterruptTimeoutWarningEvent,
    DoneEvent,
    TasksChangedEvent,
    SchedulerReminderEvent,
    SessionArchivedEvent,
    SessionArchivedOneEvent,
    SessionUnarchivedOneEvent,
    ErrorEvent,
    SessionListEvent,
    SessionCreatedEvent,
    SessionDeletedEvent,
    SessionHistoryEvent,
    RagListEvent,
    RagIngestEvent,
    RagSearchEvent,
    RagDeletedEvent,
    ChatStoppedEvent,
    MemoryGetEvent,
    MemorySetEvent,
    SchedulerListEvent,
)


def export_ws_protocol_json() -> dict[str, Any]:
    """JSON export for codegen and GET /openapi/ws-protocol.json."""
    events = []
    for model in SERVER_EVENT_MODELS:
        type_val = model.model_fields["type"].default
        events.append(
            {
                "type": type_val,
                "schema": model.model_json_schema(ref_template="#/components/schemas/{model}"),
            }
        )
    return {
        "title": "Personal Assistant WebSocket Protocol",
        "description": "Server → client events (companion to REST OpenAPI at /openapi.json).",
        "server_events": events,
    }
