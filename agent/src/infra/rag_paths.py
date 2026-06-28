from __future__ import annotations

from pathlib import Path

from infra.config import get_workspace_dir, resolve_workspace_path
from memory.rag import SUPPORTED_EXTENSIONS


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
