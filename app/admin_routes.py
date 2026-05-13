"""
Admin-only routes: request history and activity log.
"""

from fastapi import APIRouter, Depends

import app.db as db
from app.auth import require_admin

router = APIRouter(prefix="/api/admin")


@router.get("/requests")
def request_history(user: dict = Depends(require_admin)):
    return db.get_all_requests_admin()


@router.get("/activity")
def activity_log(
    event_type: str | None = None,
    user_id: int | None = None,
    user: dict = Depends(require_admin),
):
    return db.get_activity_log(event_type=event_type, user_id=user_id)
