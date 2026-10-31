"""Brand intake: the gap report, and manual answers to fields.

GET  /api/intake/gap-report          what is covered by real data and what is still a gap
PATCH /api/intake/fields/{field_id}  mark a field provided or not applicable, or clear the mark
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection
from pydantic import BaseModel, Field

from app.db import get_conn
from app.security import require_role
from app.services.intake import load_gap_report

router = APIRouter(prefix="/api/intake", tags=["intake"])

EDITOR_ROLES = ("manager", "admin")


class FieldResponse(BaseModel):
    status: Literal["provided", "not_applicable"] | None = None
    note: str = Field(default="", max_length=500)


@router.get("/gap-report")
def get_gap_report(
    user: dict = Depends(require_role(*EDITOR_ROLES)),
    conn: Connection = Depends(get_conn),
) -> dict:
    return load_gap_report(conn)


@router.patch("/fields/{field_id}")
def set_field_response(
    field_id: str,
    body: FieldResponse,
    user: dict = Depends(require_role(*EDITOR_ROLES)),
    conn: Connection = Depends(get_conn),
) -> dict:
    with conn.transaction():
        exists = conn.execute("SELECT 1 FROM intake_fields WHERE id = %s", (field_id,)).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail="Intake field not found")

        if body.status is None:
            conn.execute("DELETE FROM intake_responses WHERE field_id = %s", (field_id,))
        else:
            conn.execute(
                """
                INSERT INTO intake_responses (field_id, status, note, updated_by)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (field_id) DO UPDATE
                SET status = EXCLUDED.status, note = EXCLUDED.note,
                    updated_by = EXCLUDED.updated_by, updated_at = now()
                """,
                (field_id, body.status, body.note.strip(), user["id"]),
            )
    return {"fieldId": field_id, "status": body.status, "note": body.note.strip()}
