from __future__ import annotations

import json
import os
from typing import Any

import httpx

from infra.auth import get_or_create_token


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
