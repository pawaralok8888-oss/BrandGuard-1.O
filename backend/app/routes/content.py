from __future__ import annotations

from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from psycopg import Connection

from app.db import get_conn
from app.services.content_text import plain_text_to_html
from app.security import current_user, require_role

router = APIRouter(prefix="/api/content", tags=["content"])

Channel = Literal["Website", "Instagram", "Email", "Ad"]
Team = Literal["Marketing", "Sales", "Brand", "Legal", "Product", "Design", "HR", "Support"]
EDITABLE_STATUSES = ("Draft", "Checked", "Fixing", "Changes requested")
# Asset type for the content. "" means not chosen yet. Values are stored as given.
AssetFormat = Literal["", "social_post", "web_page", "email", "ad", "product_page", "blog_article"]


class ContentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    channel: Channel
    team: Team
    bodyText: str
    bodyHtml: str
    format: AssetFormat = ""
    thumbnailArt: str | None = None
    imageUrl: str | None = None
    altText: str | None = None


class ContentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    channel: Channel | None = None
    format: AssetFormat | None = None
    bodyText: str | None = None
    bodyHtml: str | None = None
    altText: str | None = None


def to_item(row: dict) -> dict:
    """Convert a content database row into the public camelCase response shape."""
    return {
        "id": row["id"],
        "title": row["title"],
        "channel": row["channel"],
        "team": row["team"],
        "status": row["status"],
        "bodyText": row["body_text"],
        "bodyHtml": row["body_html"],
        "ownerId": row["owner_id"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "currentVersion": row["current_version"],
        "thumbnailArt": row["thumbnail_art"],
        "imageUrl": row["image_url"],
        "altText": row["alt_text"],
        "format": row["format"],
        "imageIsLogo": row["image_is_logo"],
    }


def _content_select() -> str:
    return """
        SELECT c.id, c.title, c.channel, c.team, c.status, c.body_text,
               c.body_html, c.owner_id, c.created_at, c.updated_at,
               c.thumbnail_art, c.image_url, c.alt_text, c.format, c.image_is_logo,
               COALESCE((SELECT MAX(cv.version)
                         FROM content_versions cv
                         WHERE cv.content_id = c.id), 0) AS current_version
        FROM content c
    """


def _get_content(conn: Connection, content_id: str) -> dict:
    row = conn.execute(
        _content_select() + " WHERE c.id = %s",
        (content_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Content not found")
    return row


def _ensure_can_view(row: dict, user: dict) -> None:
    if user["role"] == "creator" and row["owner_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="You can only access your own content")


@router.get("")
def list_content(
    conn: Connection = Depends(get_conn),
    user: dict = Depends(current_user),
) -> list[dict]:
    query = _content_select()
    params: tuple = ()
    if user["role"] == "creator":
        query += " WHERE c.owner_id = %s"
        params = (user["id"],)
    query += " ORDER BY c.updated_at DESC, c.created_at DESC"
    rows = conn.execute(query, params).fetchall()
    return [to_item(row) for row in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_content(
    payload: ContentCreate,
    conn: Connection = Depends(get_conn),
    user: dict = Depends(current_user),
    _role: dict = Depends(require_role("creator")),
) -> dict:
    content_id = "cnt_" + uuid4().hex[:12]
    version_id = "cv_" + uuid4().hex[:12]
    revision_id = "rev_" + uuid4().hex[:12]

    with conn.transaction():
        conn.execute(
            """
            INSERT INTO content (
                id, title, channel, team, owner_id, status, body_text, body_html,
                thumbnail_art, image_url, alt_text, format, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, 'Draft', %s, %s, %s, %s, %s, %s, now(), now())
            """,
            (
                content_id, payload.title.strip(), payload.channel, payload.team,
                user["id"], payload.bodyText, payload.bodyHtml, payload.thumbnailArt,
                payload.imageUrl, payload.altText, payload.format,
            ),
        )
        conn.execute(
            """
            INSERT INTO content_versions (
                id, content_id, version, body_text, body_html, change_type,
                actor_id, actor_label, note, created_at
            ) VALUES (%s, %s, 1, %s, %s, 'initial', %s, %s, %s, now())
            """,
            (version_id, content_id, payload.bodyText, payload.bodyHtml,
             user["id"], user["name"], "Initial draft created"),
        )
        conn.execute(
            """
            INSERT INTO revisions (
                id, content_id, actor_id, actor_label, kind, action, detail,
                from_status, to_status, version, created_at
            ) VALUES (%s, %s, %s, %s, 'person', 'created', %s, NULL, 'Draft', 1, now())
            """,
            (revision_id, content_id, user["id"], user["name"], "Content created"),
        )
        row = _get_content(conn, content_id)
    return to_item(row)


@router.get("/{content_id}")
def get_content(
    content_id: str,
    conn: Connection = Depends(get_conn),
    user: dict = Depends(current_user),
) -> dict:
    row = _get_content(conn, content_id)
    _ensure_can_view(row, user)
    return to_item(row)


@router.put("/{content_id}")
def update_content(
    content_id: str,
    payload: ContentUpdate,
    conn: Connection = Depends(get_conn),
    user: dict = Depends(current_user),
) -> dict:
    patch = payload.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(status_code=400, detail="Provide at least one field to update")
    required_fields = ("title", "channel", "bodyText", "bodyHtml")
    null_required = [key for key in required_fields if key in patch and patch[key] is None]
    if null_required:
        raise HTTPException(status_code=422, detail=f"Field cannot be empty: {null_required[0]}")
    if "bodyText" in patch and "bodyHtml" not in patch:
        patch["bodyHtml"] = plain_text_to_html(patch["bodyText"])

    column_map = {
        "title": "title",
        "channel": "channel",
        "bodyText": "body_text",
        "bodyHtml": "body_html",
        "altText": "alt_text",
        "format": "format",
    }

    with conn.transaction():
        existing = _get_content(conn, content_id)
        if existing["owner_id"] != user["id"]:
            raise HTTPException(status_code=403, detail="Only the content owner may edit this content")
        if existing["status"] not in EDITABLE_STATUSES:
            raise HTTPException(
                status_code=409,
                detail=f"Content is locked for editing in status {existing['status']}",
            )

        assignments = [f"{column_map[key]} = %s" for key in patch]
        values = [patch[key] for key in patch]
        assignments.append("updated_at = now()")
        conn.execute(
            "UPDATE content SET " + ", ".join(assignments) + " WHERE id = %s",
            (*values, content_id),
        )
        updated = _get_content(conn, content_id)
        next_version = updated["current_version"] + 1
        conn.execute(
            """
            INSERT INTO content_versions (
                id, content_id, version, body_text, body_html, change_type,
                actor_id, actor_label, note, created_at
            ) VALUES (%s, %s, %s, %s, %s, 'human_edit', %s, %s, %s, now())
            """,
            (
                "cv_" + uuid4().hex[:12], content_id, next_version,
                updated["body_text"], updated["body_html"], user["id"],
                user["name"], "Content edited",
            ),
        )
        conn.execute(
            """
            INSERT INTO revisions (
                id, content_id, actor_id, actor_label, kind, action, detail,
                from_status, to_status, version, created_at
            ) VALUES (%s, %s, %s, %s, 'person', 'updated', %s, %s, %s, %s, now())
            """,
            (
                "rev_" + uuid4().hex[:12], content_id, user["id"], user["name"],
                "Content edited", existing["status"], existing["status"], next_version,
            ),
        )
        row = _get_content(conn, content_id)
    return to_item(row)


@router.get("/{content_id}/versions")
def list_versions(
    content_id: str,
    conn: Connection = Depends(get_conn),
    user: dict = Depends(current_user),
) -> list[dict]:
    content = _get_content(conn, content_id)
    _ensure_can_view(content, user)
    rows = conn.execute(
        """
        SELECT version, change_type, actor_label, note, created_at, body_text
        FROM content_versions
        WHERE content_id = %s
        ORDER BY version DESC, created_at DESC
        """,
        (content_id,),
    ).fetchall()
    return [
        {
            "version": row["version"],
            "changeType": row["change_type"],
            "actorLabel": row["actor_label"],
            "note": row["note"],
            "createdAt": row["created_at"],
            "bodyText": row["body_text"],
        }
        for row in rows
    ]


@router.get("/{content_id}/revisions")
def list_revisions(
    content_id: str,
    conn: Connection = Depends(get_conn),
    user: dict = Depends(current_user),
) -> list[dict]:
    content = _get_content(conn, content_id)
    _ensure_can_view(content, user)
    rows = conn.execute(
        """
        SELECT actor_label, kind, action, detail, from_status, to_status, version, created_at
        FROM revisions
        WHERE content_id = %s
        ORDER BY created_at ASC, id ASC
        """,
        (content_id,),
    ).fetchall()
    return [
        {
            "actorLabel": row["actor_label"],
            "kind": row["kind"],
            "action": row["action"],
            "detail": row["detail"],
            "fromStatus": row["from_status"],
            "toStatus": row["to_status"],
            "version": row["version"],
            "createdAt": row["created_at"],
        }
        for row in rows
    ]
