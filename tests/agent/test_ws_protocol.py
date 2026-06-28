from __future__ import annotations

import sys
from pathlib import Path

AGENT_SRC = Path(__file__).resolve().parents[1] / "agent" / "src"
if str(AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(AGENT_SRC))

from api.ws_protocol import SERVER_EVENT_MODELS, export_ws_protocol_json


def test_export_ws_protocol_json():
    data = export_ws_protocol_json()
    assert data["title"]
    assert len(data["server_events"]) == len(SERVER_EVENT_MODELS)
    types = {e["type"] for e in data["server_events"]}
    assert "connected" in types
    assert "tasks.changed" in types
    assert "done" in types
