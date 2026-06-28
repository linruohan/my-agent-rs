from __future__ import annotations

import base64
from pathlib import Path

from infra.config import get_workspace_dir, load_rag_config, resolve_workspace_path
from memory.rag import SUPPORTED_EXTENSIONS

DEFAULT_MAX_INLINE_CHARS = 500_000
DEFAULT_MAX_PDF_B64_BYTES = 10 * 1024 * 1024


def _ingest_limits() -> tuple[int, int]:
    cfg = load_rag_config().get("ingest", {})
    max_chars = int(cfg.get("max_inline_chars", DEFAULT_MAX_INLINE_CHARS))
    max_pdf = int(cfg.get("max_pdf_b64_bytes", DEFAULT_MAX_PDF_B64_BYTES))
    return max(1, max_chars), max(1, max_pdf)


def validate_rag_inline_content(content: str, *, source: str = "inline") -> str:
    text = content or ""
    max_chars, _ = _ingest_limits()
    if len(text) > max_chars:
        raise ValueError(
            f"Inline content too large ({len(text)} chars). "
            f"Maximum allowed: {max_chars} (source={source})"
        )
    return text


def validate_rag_pdf_b64(payload: str) -> bytes:
    prefix = "__pdf_b64__:"
    if not payload.startswith(prefix):
        raise ValueError("Invalid PDF payload prefix")
    _, max_pdf = _ingest_limits()
    raw_b64 = payload[len(prefix) :]
    if len(raw_b64) > max_pdf * 4 // 3 + 4:
        raise ValueError(
            f"PDF payload too large (>{max_pdf} bytes decoded limit)"
        )
    try:
        decoded = base64.b64decode(raw_b64, validate=True)
    except Exception as exc:
        raise ValueError("Invalid PDF base64 payload") from exc
    if len(decoded) > max_pdf:
        raise ValueError(f"PDF too large ({len(decoded)} bytes). Maximum: {max_pdf}")
    return decoded


def validate_rag_ingest_path(path: str) -> Path:
    """Resolve and validate a RAG ingest path within the workspace."""
    raw = (path or "").strip()
    if not raw:
        raise ValueError("path is required")

    workspace = get_workspace_dir()
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        target = candidate.resolve()
        try:
            target.relative_to(workspace)
        except ValueError as exc:
            raise ValueError(f"Path escapes workspace: {raw}") from exc
    else:
        target = resolve_workspace_path(raw)

    if not target.exists():
        raise ValueError(f"File not found: {raw}")
    if not target.is_file():
        raise ValueError(f"Not a file: {raw}")
    if target.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: {target.suffix}. "
            f"Supported: {sorted(SUPPORTED_EXTENSIONS)}"
        )
    return target
