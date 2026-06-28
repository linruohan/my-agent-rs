"""图片 OCR。"""

from ocr.compose import (
    compose_ocr_message,
    compose_user_message,
    format_ocr_reply,
    is_ocr_only_request,
    is_ocr_slash_command,
    try_direct_ocr_reply,
)
from ocr.core import ocr_engine_name, ocr_image_path
from ocr.paddle import paddle_available, paddle_missing_message
from ocr.rapid import rapid_available, rapid_missing_message
from ocr.worker import ocr_image_path_in_process, ocr_progress_text, shutdown_ocr_pool

__all__ = [
    "compose_ocr_message",
    "compose_user_message",
    "format_ocr_reply",
    "is_ocr_only_request",
    "is_ocr_slash_command",
    "ocr_engine_name",
    "ocr_image_path",
    "ocr_image_path_in_process",
    "ocr_progress_text",
    "paddle_available",
    "paddle_missing_message",
    "rapid_available",
    "rapid_missing_message",
    "shutdown_ocr_pool",
    "try_direct_ocr_reply",
]
