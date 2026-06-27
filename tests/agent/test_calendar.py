from __future__ import annotations

import sys
import tempfile
from pathlib import Path

AGENT_SRC = Path(__file__).resolve().parents[1] / "agent" / "src"
if str(AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(AGENT_SRC))


def test_create_and_list_events(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        monkeypatch.setattr("tools.business.calendar.DB_PATH", data_dir / "calendar.db")

        from tools.business.calendar import create_event_record, list_events

        event = create_event_record(
            "Team meeting",
            "2026-06-28T10:00:00",
            "2026-06-28T11:00:00",
            location="Room A",
        )
        assert event["id"] == 1
        assert event["title"] == "Team meeting"

        events = list_events()
        assert len(events) == 1


def test_conflict_detection(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        monkeypatch.setattr("tools.business.calendar.DB_PATH", data_dir / "calendar.db")

        from tools.business.calendar import create_event_record, detect_conflicts

        create_event_record("Existing", "2026-06-28T10:00:00", "2026-06-28T11:00:00")
        conflicts = detect_conflicts("2026-06-28T10:30:00", "2026-06-28T11:30:00")
        assert len(conflicts) == 1
        assert conflicts[0]["title"] == "Existing"


def test_calendar_tools_invoke(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        monkeypatch.setattr("tools.business.calendar.DB_PATH", data_dir / "calendar.db")

        from tools.business.calendar import create_calendar_tools

        tools = {t.name: t for t in create_calendar_tools()}
        result = tools["read_calendar"].invoke({"start_date": "", "end_date": ""})
        assert "没有日历事件" in result
