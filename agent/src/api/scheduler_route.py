from __future__ import annotations

from fastapi import APIRouter, Depends

from api.deps import require_auth
from infra.scheduler import list_pending_jobs

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


@router.get("/jobs")
async def list_scheduler_jobs(_: None = Depends(require_auth)) -> dict:
    """List pending scheduled jobs (reminders). Mirrors WS `scheduler.list`."""
    return {"jobs": list_pending_jobs()}
