"""输入附件 OCR 处理与用户消息拼装。"""

from __future__ import annotations

import base64
import re
import uuid
from pathlib import Path
from typing import Any

from infra.config import get_data_dir
from ocr.worker import ocr_image_path_in_process

TEMP_INPUT_DIR = get_data_dir() / "temp" / "input"
_OCR_SLASH_RE = re.compile(r"^/ocr\b", re.IGNORECASE)
_OCR_ONLY_TEXT_RE = re.compile(
    r"^(?:识别(?:文本|文字|图片)?|文字识别|图片识别|提取文字|ocr)(?:[\s，。!！?？、]*)?$",
    re.IGNORECASE,
)


def ensure_temp_dir() -> Path:
    TEMP_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    return TEMP_INPUT_DIR


def save_temp_image_b64(data_b64: str, *, ext: str = "png") -> dict[str, Any]:
    try:
        raw = base64.b64decode(data_b64.split(",", 1)[-1])
    except Exception as exc:
        return {"ok": False, "error": f"图片数据无效: {exc}"}
    ensure_temp_dir()
    path = TEMP_INPUT_DIR / f"paste_{uuid.uuid4().hex[:12]}.{ext.lstrip('.')}"
    path.write_bytes(raw)
    return {"ok": True, "path": str(path.resolve())}


def _image_ext(name: str, mime_type: str | None) -> str:
    if mime_type:
        if "jpeg" in mime_type or mime_type == "image/jpg":
            return "jpg"
        if "webp" in mime_type:
            return "webp"
        if "gif" in mime_type:
            return "gif"
    suffix = Path(name).suffix.lstrip(".").lower()
    return suffix or "png"


def resolve_image_path(att: dict[str, Any]) -> dict[str, Any]:
    path = str(att.get("path", "")).strip()
    if path and Path(path).is_file():
        return {"ok": True, "path": path}

    if att.get("type") != "image":
        return {"ok": False, "error": "非图片附件"}

    content = str(att.get("content", "")).strip()
    if not content:
        return {"ok": False, "error": "图片路径或数据为空"}

    name = str(att.get("name") or "image.png")
    ext = _image_ext(name, att.get("mimeType") or att.get("mime_type"))
    saved = save_temp_image_b64(content, ext=ext)
    if not saved.get("ok"):
        return saved
    return {"ok": True, "path": str(saved["path"])}


def process_image_ocr(att: dict[str, Any], *, timeout: float | None = 180) -> dict[str, Any]:
    resolved = resolve_image_path(att)
    if not resolved.get("ok"):
        return resolved

    path = str(resolved["path"])
    ocr = ocr_image_path_in_process(path, timeout=timeout)
    if not ocr.get("ok"):
        return ocr

    name = att.get("name") or Path(path).name
    block = f"### 图片 OCR ({name})\n{ocr.get('text', '')}"
    return {
        "ok": True,
        "block": block,
        "kind": "image",
        "ocr": ocr.get("text", ""),
        "engine": ocr.get("engine", ""),
    }


def is_ocr_slash_command(text: str) -> bool:
    return bool(_OCR_SLASH_RE.match((text or "").strip()))


def is_ocr_only_request(text: str, attachments: list[dict[str, Any]] | None = None) -> bool:
    attachments = attachments or []
    if not attachments:
        return False
    if any(att.get("type") != "image" for att in attachments):
        return False
    body = (text or "").strip()
    if is_ocr_slash_command(body):
        return True
    if not body:
        return True
    return bool(_OCR_ONLY_TEXT_RE.fullmatch(body))


def format_ocr_reply(ocr_results: list[dict[str, str]]) -> str:
    if not ocr_results:
        return "(未识别到文字)"
    parts: list[str] = []
    for item in ocr_results:
        name = item.get("name") or "图片"
        text = (item.get("text") or "").strip() or "(未识别到文字)"
        if len(ocr_results) > 1:
            parts.append(f"**{name}**\n\n{text}")
        else:
            parts.append(text)
    return "\n\n".join(parts)


def compose_ocr_message(
    text: str,
    attachments: list[dict[str, Any]] | None = None,
    *,
    timeout: float | None = 180,
) -> dict[str, Any]:
    attachments = attachments or []
    image_atts = [att for att in attachments if att.get("type") == "image"]
    if not image_atts:
        return {"ok": False, "error": "请先添加图片", "errors": ["请先添加图片"]}

    errors: list[str] = []
    ocr_results: list[dict[str, str]] = []
    for att in image_atts:
        result = process_image_ocr(att, timeout=timeout)
        if result.get("ok"):
            path = str(att.get("path", "")).strip()
            ocr_results.append(
                {
                    "name": str(att.get("name") or Path(path).name or "图片"),
                    "text": str(result.get("ocr") or ""),
                }
            )
        else:
            errors.append(str(result.get("error", "识别失败")))

    if not ocr_results:
        return {"ok": False, "error": errors[0] if errors else "识别失败", "errors": errors}

    return {
        "ok": True,
        "ocr_results": ocr_results,
        "errors": errors,
        "ocr_only": True,
    }


def try_direct_ocr_reply(
    text: str,
    attachments: list[dict[str, Any]] | None = None,
    *,
    timeout: float | None = 180,
) -> str | None:
    """纯 OCR 请求时返回识别文本，否则返回 None。"""
    if not attachments:
        if is_ocr_slash_command(text):
            return "请先添加图片，或使用 /ocr 时粘贴/上传图片"
        return None
    if not is_ocr_only_request(text, attachments):
        return None

    composed = compose_ocr_message(text, attachments, timeout=timeout)
    if not composed.get("ok"):
        return str(composed.get("error") or "识别失败")
    return format_ocr_reply(composed.get("ocr_results") or [])


def compose_user_message(
    text: str,
    attachments: list[dict[str, Any]] | None = None,
    *,
    ocr_images: bool = True,
    timeout: float | None = 180,
) -> str:
    attachments = attachments or []
    blocks: list[str] = []
    errors: list[str] = []

    body = (text or "").strip()
    if body:
        blocks.append(body)

    for att in attachments:
        kind = att.get("type")
        if kind == "text":
            name = att.get("name", "attachment")
            content = att.get("content", "")
            if content:
                blocks.append(f"\n\n[附件: {name}]\n{content}")
            continue

        if kind == "image" and ocr_images:
            result = process_image_ocr(att, timeout=timeout)
            if result.get("ok"):
                blocks.append(f"\n\n{result['block']}")
            else:
                errors.append(str(result.get("error", "图片 OCR 失败")))
            continue

        name = att.get("name", "attachment")
        att_type = att.get("type", "file")
        path = att.get("path", "")
        if path:
            blocks.append(f"\n\n[附件: {name} ({att_type})]\n路径: `{path}`")
        elif att.get("content"):
            blocks.append(f"\n\n[附件: {name} ({att_type})]")

    if errors and not any("图片 OCR" in b for b in blocks):
        blocks.append("\n\n[OCR 错误]\n" + "\n".join(errors))

    return "".join(blocks).strip() or body
