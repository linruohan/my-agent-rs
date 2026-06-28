from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.tools import tool


def create_image_ocr_tool(config: dict[str, Any]):
    timeout = float(config.get("timeout_sec", 180))

    @tool
    def image_ocr(image_path: str) -> str:
        """Extract text from a local image file using OCR.

        Use when the user asks to read or recognize text in an image at a known path.
        Supports Chinese and English. Engine priority: RapidOCR → WinRT → PaddleOCR.

        Args:
            image_path: Absolute or relative path to a local image file.
        """
        from ocr.worker import ocr_image_path_in_process

        path = Path(image_path).expanduser()
        if not path.is_file():
            return f"图片不存在: {path}"

        result = ocr_image_path_in_process(path, timeout=timeout)
        if not result.get("ok"):
            return f"OCR 失败: {result.get('error', '未知错误')}"

        engine = result.get("engine", "ocr")
        text = result.get("text", "")
        return f"[{engine}]\n{text}"

    return image_ocr
