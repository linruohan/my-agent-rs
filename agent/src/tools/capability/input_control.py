from __future__ import annotations

import re
from typing import Any


def _parse_click_coords(action: str, text: str) -> tuple[int, int] | None:
    """Parse click coordinates from action 'click X Y' or text 'X,Y'."""
    parts = action.strip().split()
    if len(parts) >= 3 and parts[0].lower() == "click":
        try:
            return int(parts[1]), int(parts[2])
        except ValueError:
            return None
    if text and "," in text:
        xy = text.split(",", 1)
        try:
            return int(xy[0].strip()), int(xy[1].strip())
        except ValueError:
            return None
    return None


def execute_input_action(action: str, text: str = "", config: dict[str, Any] | None = None) -> str:
    """Execute keyboard/mouse action via pyautogui. High privilege — caller must enforce HITL."""
    cfg = config or {}
    allowed = set(cfg.get("allowed_actions", ["type", "click", "scroll"]))
    act = action.strip().lower()
    base = act.split()[0] if act else ""

    if base not in allowed and act not in allowed:
        return f"Action `{action}` not allowed. Permitted: {sorted(allowed)}"

    try:
        import pyautogui
    except ImportError:
        return "pyautogui not installed. pip install pyautogui"

    pyautogui.FAILSAFE = True
    pause = float(cfg.get("pyautogui_pause", 0.05))
    pyautogui.PAUSE = pause

    if base == "type" or act == "type":
        if not text:
            return "type action requires text parameter"
        pyautogui.write(text, interval=0.02)
        return f"Typed {len(text)} characters"

    if base == "click" or act.startswith("click"):
        coords = _parse_click_coords(action, text)
        if not coords:
            return "click requires coordinates: action='click X Y' or text='X,Y'"
        x, y = coords
        pyautogui.click(x, y)
        return f"Clicked at ({x}, {y})"

    if base == "scroll" or act == "scroll":
        amount = 3
        if text:
            try:
                amount = int(text)
            except ValueError:
                m = re.search(r"-?\d+", text)
                if m:
                    amount = int(m.group())
        pyautogui.scroll(amount)
        return f"Scrolled {amount} units"

    return f"Unknown action: {action}. Supported: type, click X Y, scroll"
