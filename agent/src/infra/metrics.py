from __future__ import annotations

import threading
from collections import deque
from typing import Any

_lock = threading.Lock()
_counters: dict[str, int] = {}
_tool_durations_ms: deque[float] = deque(maxlen=500)
_turn_durations_ms: deque[float] = deque(maxlen=200)


def inc(name: str, n: int = 1) -> None:
    with _lock:
        _counters[name] = _counters.get(name, 0) + n


def observe_tool_duration(ms: float, *, success: bool) -> None:
    with _lock:
        _tool_durations_ms.append(ms)
    inc("tool_calls.success" if success else "tool_calls.error")


def observe_turn_duration(ms: float) -> None:
    with _lock:
        _turn_durations_ms.append(ms)
    inc("agent.turns")


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(len(ordered) * pct))
    return round(ordered[idx], 1)


def snapshot() -> dict[str, Any]:
    with _lock:
        counters = dict(_counters)
        tool_durs = list(_tool_durations_ms)
        turn_durs = list(_turn_durations_ms)
    return {
        "counters": counters,
        "tool_call_duration_ms": {
            "count": len(tool_durs),
            "p95": _percentile(tool_durs, 0.95),
        },
        "turn_duration_ms": {
            "count": len(turn_durs),
            "p95": _percentile(turn_durs, 0.95),
        },
    }
