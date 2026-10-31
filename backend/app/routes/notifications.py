"""Notification log for managers and admins: what was sent, failed or skipped, and why.

GET /api/notifications?status=skipped&limit=50
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from psycopg import Connection

from app.db import get_conn
from app.security import require_role

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

EDITOR_ROLES = ("manager", "admin")
NotificationStatus = Literal["queued", "sent", "failed", "read", "skipped"]


@router.get("")
def list_notifications(
    status: NotificationStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    user: dict = Depends(require_role(*EDITOR_ROLES)),
    conn: Connection = Depends(get_conn),
) -> list[dict]:
    clauses, params = [], []
    if status is not None:
        clauses.append("status = %s")
        params.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"""
        SELECT id, channel, recipient_id, subject, status, error, created_at
        FROM notification_log {where}
        ORDER BY created_at DESC, id DESC
        LIMIT %s
        """,
        [*params, limit],
    ).fetchall()
    return [
        {
            "id": r["id"],
            "channel": r["channel"],
            "recipientId": r["recipient_id"],
            "subject": r["subject"],
            "status": r["status"],
            "error": r["error"],
            "createdAt": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else str(r["created_at"]),
        }
        for r in rows
    ]
