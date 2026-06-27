from __future__ import annotations

import os
from typing import Any

import httpx

from infra.auth import get_or_create_token
from tools.capability.input_control import execute_input_action


def capture_via_native_bridge() -> tuple[str, str]:
    """Capture screen via Tauri native bridge. Returns (base64_png, error)."""
    bridge_url = os.environ.get("NATIVE_BRIDGE_URL", "").strip()
    if not bridge_url:
        return "", "NATIVE_BRIDGE_URL not configured (not running under Tauri)"

    token = get_or_create_token()
    url = f"{bridge_url.rstrip('/')}/screen"
    try:
        resp = httpx.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        if resp.status_code == 401:
            return "", "Native bridge auth failed"
        if resp.status_code != 200:
            return "", f"Native bridge HTTP {resp.status_code}"
        data: dict[str, Any] = resp.json()
        if "error" in data:
            return "", str(data["error"])
        b64 = data.get("base64", "")
        if not b64:
            return "", "Empty screenshot from native bridge"
        return b64, ""
    except Exception as e:
        return "", str(e)


def capture_screen_png() -> tuple[str, str]:
    """Capture screen: prefer Tauri native bridge, fallback to mss."""
    b64, err = capture_via_native_bridge()
    if b64:
        return b64, ""

    try:
        import base64
        import io

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
        hint = err or "Screen capture requires Tauri or: pip install mss pillow"
        return "", hint
    except Exception as e:
        if err:
            return "", f"Native bridge: {err}; mss fallback: {e}"
        return "", str(e)


def create_computer_tool(config: dict[str, Any]):
    from langchain_core.tools import tool

    input_cfg = {
        "allowed_actions": config.get("allowed_actions", ["type", "click", "scroll"]),
        "pyautogui_pause": config.get("pyautogui_pause", 0.05),
    }

    @tool
    def computer(action: str, text: str = "") -> str:
        """Computer control: screenshot | type | click X Y | scroll.

        Args:
            action: screenshot, type, click (with coords in action or text as X,Y), scroll
            text: text to type, scroll amount, or click coordinates as X,Y
        """
        act = action.strip().lower()
        if act in ("screenshot", "capture", "screen"):
            b64, err = capture_screen_png()
            if err:
                return f"Screenshot failed: {err}"
            source = "Tauri native bridge" if os.environ.get("NATIVE_BRIDGE_URL") else "mss"
            return (
                f"Screenshot captured via {source} ({len(b64)} bytes base64). "
                "Use for visual analysis."
            )

        if act in ("type", "click", "scroll") or act.startswith("click"):
            return execute_input_action(action, text, input_cfg)

        return (
            f"Unknown action: {action}. Supported: screenshot, type, click X Y, scroll"
        )

    return computer
