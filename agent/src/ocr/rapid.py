"""RapidOCR（ONNX Runtime）识图。"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from loguru import logger

_engine: Any = None


def rapid_available() -> bool:
    return importlib.util.find_spec("rapidocr_onnxruntime") is not None


def rapid_missing_message() -> str:
    return "缺少 RapidOCR，请运行: pip install -e \".[ocr-rapid]\""


def _get_engine() -> Any:
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR

        logger.info("首次 OCR：正在加载 RapidOCR 模型…")
        _engine = RapidOCR()
        logger.info("RapidOCR 模型已就绪")
    return _engine


def _extract_lines(result: Any) -> list[str]:
    lines: list[str] = []
    if not result:
        return lines
    for item in result:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        text = item[1]
        if text:
            lines.append(str(text))
    return lines


def ocr_image_path_rapid(path: Path) -> dict[str, Any]:
    if not rapid_available():
        return {"ok": False, "error": rapid_missing_message(), "engine": "rapidocr"}

    try:
        engine = _get_engine()
        result, _ = engine(str(path))
    except ImportError:
        return {"ok": False, "error": rapid_missing_message(), "engine": "rapidocr"}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "engine": "rapidocr"}

    lines = _extract_lines(result)
    text = "\n".join(lines).strip()
    return {
        "ok": True,
        "text": text or "(未识别到文字)",
        "engine": "rapidocr",
    }
