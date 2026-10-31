"""Attach, view and replace the image on a content item. The image checks read this file.

Only the creator who owns the content can change its image. Images cannot change once the
content is In Review, Approved or Published, because that would change what was approved.
"""
from __future__ import annotations

import io
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi import Response
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from psycopg import Connection

from app.db import get_conn
from app.security import current_user
from app.services.checks import BLOCKED_STATUSES
from app.services.image_checks import default_storage_dir, find_content_image

router = APIRouter(prefix="/api/content", tags=["content-image"])

MAX_IMAGE_BYTES = 2 * 1024 * 1024
FORMAT_EXTENSIONS = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}


def _content_row(conn: Connection, content_id: str) -> dict:
    row = conn.execute(
        "SELECT owner_id, status FROM content WHERE id = %s", (content_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Content not found")
    return row


@router.post("/{content_id}/image", status_code=status.HTTP_201_CREATED)
async def upload_content_image(
    content_id: str,
    file: UploadFile = File(...),
    alt_text: str | None = Form(default=None),
    is_logo: bool = Form(default=False),
    conn: Connection = Depends(get_conn),
    user: dict = Depends(current_user),
) -> dict:
    row = _content_row(conn, content_id)
    if user["role"] != "creator" or row["owner_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Only the creator can change the image on their content")
    if row["status"] in BLOCKED_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"The image cannot change while the content is {row['status']}",
        )

    data = await file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Image is larger than 2 MB")

    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()
        with Image.open(io.BytesIO(data)) as img:
            image_format = img.format
            width, height = img.size
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=422, detail="File must be a valid PNG, JPEG or WebP image")

    extension = FORMAT_EXTENSIONS.get(image_format or "")
    if extension is None:
        raise HTTPException(status_code=415, detail="Only PNG, JPEG and WebP images are accepted")

    storage = default_storage_dir()
    storage.mkdir(parents=True, exist_ok=True)
    for old in storage.glob(f"{content_id}.*"):
        old.unlink()
    (storage / f"{content_id}{extension}").write_bytes(data)

    image_url = f"/api/content/{content_id}/image"
    cleaned_alt = alt_text.strip() if alt_text is not None else None
    with conn.transaction():
        conn.execute(
            """
            UPDATE content
            SET image_url = %s, image_width = %s, image_height = %s,
                alt_text = COALESCE(%s, alt_text), image_is_logo = %s, updated_at = now()
            WHERE id = %s
            """,
            (image_url, width, height, cleaned_alt, is_logo, content_id),
        )

    return {
        "contentId": content_id,
        "imageUrl": image_url,
        "imageWidth": width,
        "imageHeight": height,
        "altText": cleaned_alt,
        "isLogo": is_logo,
    }


@router.get("/{content_id}/image")
def get_content_image(
    content_id: str,
    conn: Connection = Depends(get_conn),
    user: dict = Depends(current_user),
) -> FileResponse:
    row = _content_row(conn, content_id)
    if user["role"] == "creator" and row["owner_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="You can only access your own content")

    path: Path | None = find_content_image(default_storage_dir(), content_id)
    if path is None:
        raise HTTPException(status_code=404, detail="No image is stored for this content")
    return FileResponse(path)


@router.delete("/{content_id}/image", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_content_image(
    content_id: str,
    conn: Connection = Depends(get_conn),
    user: dict = Depends(current_user),
) -> Response:
    """Remove the saved image from a draft. Only the owner can, and only while the content is editable."""
    row = _content_row(conn, content_id)
    if user["role"] != "creator" or row["owner_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Only the creator can remove the image from their content")
    if row["status"] in BLOCKED_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"The image cannot change while the content is {row['status']}",
        )
    for stored in default_storage_dir().glob(f"{content_id}.*"):
        stored.unlink()
    with conn.transaction():
        conn.execute(
            """
            UPDATE content
            SET image_url = NULL, image_width = NULL, image_height = NULL,
                image_is_logo = FALSE, updated_at = now()
            WHERE id = %s
            """,
            (content_id,),
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)

