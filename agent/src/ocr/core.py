"""图片 OCR：默认 RapidOCR → WinRT → PaddleOCR。"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Callable

from loguru import logger

from ocr.paddle import ocr_image_path_paddle, paddle_available
from ocr.rapid import ocr_image_path_rapid, rapid_available
from ocr.win import is_winrt_ocr_supported, ocr_image_path_win


def ocr_engine_name() -> str:
    env = os.environ.get("AGENT_OCR_ENGINE")
    if env:
        return env.strip().lower()
    try:
        from infra.config import load_tools_config

        cfg = load_tools_config().get("capability", {}).get("ocr", {})
        return str(cfg.get("engine", "auto")).strip().lower()
    except Exception:
        return "auto"


def _try_winrt_ocr(path: Path) -> dict[str, Any] | None:
    if sys.platform != "win32":
        return None
    if not is_winrt_ocr_supported():
        return None
    return ocr_image_path_win(path)


def _all_engines_error(last: dict[str, Any] | None) -> dict[str, Any]:
    hints = []
    if not rapid_available():
        hints.append("pip install -e \".[ocr-rapid]\"")
    if sys.platform == "win32" and not is_winrt_ocr_supported():
        hints.append("pip install -e \".[ocr-winrt]\" 并安装系统中文 OCR")
    if not paddle_available():
        hints.append("pip install -e \".[ocr-paddle]\"（可选）")
    detail = last.get("error", "无可用 OCR 引擎") if last else "无可用 OCR 引擎"
    if hints:
        detail = f"{detail}。可尝试: {'; '.join(hints)}"
    return {"ok": False, "error": detail, "engine": "ocr"}


def _run_chain(path: Path, engines: list[Callable[[Path], dict[str, Any]]]) -> dict[str, Any]:
    last: dict[str, Any] | None = None
    for fn in engines:
        try:
            result = fn(path)
        except Exception as exc:
            result = {"ok": False, "error": str(exc), "engine": "ocr"}
        if result.get("ok"):
            return result
        last = result
        logger.debug("[ocr] {} 失败: {}", fn.__name__, result.get("error"))
    return last or _all_engines_error(None)


def ocr_image_path(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {"ok": False, "error": f"图片不存在: {p}"}

    engine = ocr_engine_name()
    rapid_fn = lambda path: ocr_image_path_rapid(path)
    winrt_fn = lambda path: _try_winrt_ocr(path) or {"ok": False, "error": "WinRT 不可用", "engine": "winrt-ocr"}
    paddle_fn = ocr_image_path_paddle

    if engine in ("rapid", "rapidocr"):
        return _run_chain(p, [rapid_fn])
    if engine in ("winrt", "local", "windows"):
        return _run_chain(p, [winrt_fn])
    if engine in ("paddle", "paddleocr"):
        return _run_chain(p, [paddle_fn])

    # auto: RapidOCR → WinRT → Paddle
    chain: list[Callable[[Path], dict[str, Any]]] = []
    if rapid_available():
        chain.append(rapid_fn)
    if sys.platform == "win32":
        chain.append(winrt_fn)
    if paddle_available():
        chain.append(paddle_fn)

    if not chain:
        return _all_engines_error(None)

    result = _run_chain(p, chain)
    if result.get("ok"):
        return result
    return _all_engines_error(result)
