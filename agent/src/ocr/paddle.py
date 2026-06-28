"""PaddleOCR 识图（可选兜底）。"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

from loguru import logger

_engine: Any = None


def _configure_paddle_env() -> None:
    os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "0")
    os.environ.setdefault("FLAGS_enable_pir_api", "0")
    os.environ.setdefault("FLAGS_use_mkldnn", "0")
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")


_configure_paddle_env()


def paddle_available() -> bool:
    return importlib.util.find_spec("paddle") is not None


def paddle_missing_message() -> str:
    py = f"{sys.version_info.major}.{sys.version_info.minor}"
    if sys.version_info >= (3, 14):
        return (
            f"PaddleOCR 需要 paddlepaddle，但 PyPI 尚无 Python {py} 的 wheel。"
            "请改用 RapidOCR（pip install -e \".[ocr-rapid]\") 或 WinRT OCR。"
        )
    return "缺少 paddlepaddle，请运行: pip install -e \".[ocr-paddle]\""


def paddle_ocr_version() -> str:
    return os.environ.get("AGENT_OCR_PADDLE_VERSION", "PP-OCRv6").strip()


def _get_engine() -> Any:
    global _engine
    if _engine is None:
        if not paddle_available():
            raise RuntimeError(paddle_missing_message())
        _configure_paddle_env()
        version = paddle_ocr_version()
        logger.info(
            "首次 OCR：正在加载 PaddleOCR {} 模型（约数十秒，仅第一次较慢）…",
            version,
        )
        from paddleocr import PaddleOCR

        _engine = PaddleOCR(
            ocr_version=version,
            lang="ch",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=True,
        )
        logger.info("PaddleOCR {} 模型已就绪", version)
    return _engine


def _legacy_line_text(item: Any) -> str | None:
    if not isinstance(item, (list, tuple)) or len(item) < 2:
        return None
    text_part = item[1]
    if isinstance(text_part, (list, tuple)) and text_part and isinstance(text_part[0], str):
        return str(text_part[0])
    if isinstance(text_part, str):
        return text_part
    return None


def extract_paddle_text(raw: Any) -> list[str]:
    lines: list[str] = []
    if not raw:
        return lines

    pages = raw if isinstance(raw, list) else [raw]
    for page in pages:
        if page is None:
            continue

        rec_texts: Any = None
        if isinstance(page, dict):
            rec_texts = page.get("rec_texts")
        elif hasattr(page, "get"):
            try:
                rec_texts = page.get("rec_texts")
            except Exception:
                rec_texts = None
        if rec_texts is None and hasattr(page, "rec_texts"):
            rec_texts = page.rec_texts
        if rec_texts is None and hasattr(page, "json"):
            try:
                payload = page.json() if callable(page.json) else page.json
                if isinstance(payload, dict):
                    rec_texts = payload.get("rec_texts")
            except Exception:
                pass

        if rec_texts:
            for text in rec_texts:
                if text:
                    lines.append(str(text))
            continue

        if isinstance(page, (list, tuple)):
            direct = _legacy_line_text(page)
            if direct:
                lines.append(direct)
                continue
            for item in page:
                text = _legacy_line_text(item)
                if text:
                    lines.append(text)
    return lines


def ocr_image_path_paddle(path: Path) -> dict[str, Any]:
    if not paddle_available():
        return {"ok": False, "error": paddle_missing_message(), "engine": "paddleocr"}

    try:
        engine = _get_engine()
        raw = engine.predict(str(path))
    except ImportError:
        return {"ok": False, "error": paddle_missing_message(), "engine": "paddleocr"}
    except Exception as exc:
        msg = str(exc)
        if "paddlepaddle" in msg.lower() or "paddle_static" in msg.lower():
            return {"ok": False, "error": paddle_missing_message(), "engine": "paddleocr"}
        return {"ok": False, "error": msg, "engine": "paddleocr"}

    lines = extract_paddle_text(raw)
    text = "\n".join(lines).strip()
    return {
        "ok": True,
        "text": text or "(未识别到文字)",
        "engine": "paddleocr",
        "model": paddle_ocr_version(),
    }
