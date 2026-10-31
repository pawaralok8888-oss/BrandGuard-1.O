"""Brand rules and their lifecycle: draft -> approved -> retired.

- A manager or admin creates a rule (draft). Drafts can be edited.
- A different person approves it (four-eyes: the creator cannot approve their own rule).
  Approved rules are loaded by the check pipeline (app.services.checks.load_active_rules).
- A retired rule stops being checked. Retirement is final; create a new rule to replace it.

Every status change is written to brand_rule_history.
"""
from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg import Connection
from pydantic import BaseModel, Field, model_validator

from app.db import get_conn
from app.security import current_user, require_role

router = APIRouter(prefix="/api/brand-rules", tags=["brand-rules"])

EDITOR_ROLES = ("manager", "admin")
BrandRuleKind = Literal["phrase", "regex", "name_variant", "required_text"]
Channel = Literal["Website", "Instagram", "Email", "Ad"]
Severity = Literal["critical", "warning", "info"]
Status = Literal["draft", "approved", "retired"]

# The only moves allowed. Everything else is a 409.
ALLOWED_TRANSITIONS = {("draft", "approved"), ("approved", "retired")}

RULE_COLUMNS = (
    "id, title, kind, pattern, replacement, reason, channel, severity, status, "
    "created_by, approved_by, approved_at, retired_at, created_at, updated_at"
)


class BrandRuleCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    kind: BrandRuleKind
    pattern: str = Field(..., min_length=1, max_length=500)
    replacement: str = Field(default="", max_length=500)
    reason: str = Field(default="", max_length=500)
    channel: Channel | None = None
    severity: Severity = "warning"

    @model_validator(mode="after")
    def regex_must_compile(self) -> "BrandRuleCreate":
        if self.kind == "regex":
            try:
                re.compile(self.pattern)
            except re.error as exc:
                raise ValueError(f"Invalid regex: {exc}")
        return self


class BrandRuleUpdate(BaseModel):
    """Only drafts can be edited. Kind is fixed once a rule is created."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    pattern: str | None = Field(default=None, min_length=1, max_length=500)
    replacement: str | None = Field(default=None, max_length=500)
    reason: str | None = Field(default=None, max_length=500)
    channel: Channel | None = None
    severity: Severity | None = None


class TransitionNote(BaseModel):
    note: str = Field(default="", max_length=500)


def to_brand_rule(row: dict) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "kind": row["kind"],
        "pattern": row["pattern"],
        "replacement": row["replacement"],
        "reason": row["reason"],
        "channel": row["channel"],
        "severity": row["severity"],
        "status": row["status"],
        "createdBy": row["created_by"],
        "approvedBy": row["approved_by"],
        "approvedAt": row["approved_at"],
        "retiredAt": row["retired_at"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _next_id(conn: Connection) -> str:
    conn.execute("LOCK TABLE brand_rules IN EXCLUSIVE MODE")
    numbers = [
        int(r["id"][3:])
        for r in conn.execute("SELECT id FROM brand_rules WHERE id ~ '^BR-[0-9]+$'").fetchall()
    ]
    return f"BR-{(max(numbers, default=0) + 1):03d}"


def _load_for_update(conn: Connection, rule_id: str) -> dict:
    row = conn.execute(
        f"SELECT {RULE_COLUMNS} FROM brand_rules WHERE id = %s FOR UPDATE", (rule_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Brand rule not found")
    return row


def _record(conn: Connection, rule_id: str, from_status: str | None, to_status: str,
            actor_id: str, note: str) -> None:
    conn.execute(
        """
        INSERT INTO brand_rule_history (brand_rule_id, from_status, to_status, actor_id, note)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (rule_id, from_status, to_status, actor_id, note),
    )


@router.get("")
def list_brand_rules(
    state: Status | None = Query(default=None, alias="status"),
    user: dict = Depends(require_role(*EDITOR_ROLES)),
    conn: Connection = Depends(get_conn),
) -> list[dict]:
    if state is None:
        rows = conn.execute(f"SELECT {RULE_COLUMNS} FROM brand_rules ORDER BY id").fetchall()
    else:
        rows = conn.execute(
            f"SELECT {RULE_COLUMNS} FROM brand_rules WHERE status = %s ORDER BY id", (state,)
        ).fetchall()
    return [to_brand_rule(r) for r in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_brand_rule(
    body: BrandRuleCreate,
    user: dict = Depends(require_role(*EDITOR_ROLES)),
    conn: Connection = Depends(get_conn),
) -> dict:
    with conn.transaction():
        rule_id = _next_id(conn)
        row = conn.execute(
            f"""
            INSERT INTO brand_rules
                (id, title, kind, pattern, replacement, reason, channel, severity, status, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'draft', %s)
            RETURNING {RULE_COLUMNS}
            """,
            (rule_id, body.title.strip(), body.kind, body.pattern, body.replacement,
             body.reason, body.channel, body.severity, user["id"]),
        ).fetchone()
        _record(conn, rule_id, None, "draft", user["id"], "Created")
    return to_brand_rule(row)


@router.patch("/{rule_id}")
def update_brand_rule(
    rule_id: str,
    body: BrandRuleUpdate,
    user: dict = Depends(require_role(*EDITOR_ROLES)),
    conn: Connection = Depends(get_conn),
) -> dict:
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="No fields to update")

    with conn.transaction():
        current = _load_for_update(conn, rule_id)
        if current["status"] != "draft":
            raise HTTPException(status_code=409, detail="Only draft rules can be edited")
        if "pattern" in changes and current["kind"] == "regex":
            try:
                re.compile(changes["pattern"])
            except re.error as exc:
                raise HTTPException(status_code=422, detail=f"Invalid regex: {exc}")

        set_clause = ", ".join(f"{column} = %s" for column in changes)
        row = conn.execute(
            f"UPDATE brand_rules SET {set_clause}, updated_at = now() WHERE id = %s RETURNING {RULE_COLUMNS}",
            [*changes.values(), rule_id],
        ).fetchone()
    return to_brand_rule(row)


def _transition(conn: Connection, rule_id: str, user: dict, to_status: str, note: str) -> dict:
    with conn.transaction():
        current = _load_for_update(conn, rule_id)
        from_status = current["status"]
        if (from_status, to_status) not in ALLOWED_TRANSITIONS:
            raise HTTPException(
                status_code=409,
                detail=f"A {from_status} rule cannot become {to_status}",
            )
        if to_status == "approved" and current["created_by"] == user["id"]:
            raise HTTPException(status_code=403, detail="The creator cannot approve their own rule")

        if to_status == "approved":
            row = conn.execute(
                f"""
                UPDATE brand_rules
                SET status = 'approved', approved_by = %s, approved_at = now(), updated_at = now()
                WHERE id = %s RETURNING {RULE_COLUMNS}
                """,
                (user["id"], rule_id),
            ).fetchone()
        else:
            row = conn.execute(
                f"""
                UPDATE brand_rules
                SET status = 'retired', retired_at = now(), updated_at = now()
                WHERE id = %s RETURNING {RULE_COLUMNS}
                """,
                (rule_id,),
            ).fetchone()
        _record(conn, rule_id, from_status, to_status, user["id"], note)
    return to_brand_rule(row)


@router.post("/{rule_id}/approve")
def approve_brand_rule(
    rule_id: str,
    body: TransitionNote | None = None,
    user: dict = Depends(require_role(*EDITOR_ROLES)),
    conn: Connection = Depends(get_conn),
) -> dict:
    return _transition(conn, rule_id, user, "approved", (body.note if body else "") or "Approved")


@router.post("/{rule_id}/retire")
def retire_brand_rule(
    rule_id: str,
    body: TransitionNote | None = None,
    user: dict = Depends(require_role(*EDITOR_ROLES)),
    conn: Connection = Depends(get_conn),
) -> dict:
    return _transition(conn, rule_id, user, "retired", (body.note if body else "") or "Retired")
