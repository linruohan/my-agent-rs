from __future__ import annotations

import base64
import io
from typing import Any


def capture_screen_png() -> tuple[str, str]:
    """Capture screen, return (base64_png, error_message)."""
    try:
        import mss
        from PIL import Image

        with mss.mss() as sct:
            monitor = sct.monitors[1]
            shot = sct.grab(monitor)
            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.standard_b64encode(buf.getvalue()).decode("ascii")
            return b64, ""
    except ImportError:
        return "", "Screen capture requires: pip install mss pillow"
    except Exception as e:
        return "", str(e)


def create_computer_tool(config: dict[str, Any]):
    from langchain_core.tools import tool

    @tool
    def computer(action: str, text: str = "") -> str:
        """Computer control tool. Currently supports: screenshot. Requires confirmation."""
        act = action.strip().lower()
        if act in ("screenshot", "capture", "screen"):
            b64, err = capture_screen_png()
            if err:
                return f"Screenshot failed: {err}"
            return f"Screenshot captured ({len(b64)} bytes base64). Use for visual analysis."
        if act in ("click", "type", "scroll"):
            return f"Action `{action}` is not yet implemented. Use screenshot for now."
        return f"Unknown action: {action}. Supported: screenshot"

    return computer
