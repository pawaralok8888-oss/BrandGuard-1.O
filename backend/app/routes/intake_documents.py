"""Intake documents: upload a guideline file to an intake category, read it, review its insights.

Prefix /api/intake. Managers and admins upload, delete, reprocess and review. Creators and
reviewers can read approved insights only. Response shapes: Appendix A of the phase 1 contract.

GET    /categories                            all roles (approved counts only for creator and reviewer)
POST   /categories/{category_id}/documents    manager, admin
GET    /categories/{category_id}/documents    all roles
GET    /documents/{doc_id}                    manager, admin
DELETE /documents/{doc_id}                    manager, admin (soft delete)
POST   /documents/{doc_id}/reprocess          manager, admin
GET    /insights                              all roles for approved; manager, admin for other statuses
POST   /insights/{insight_id}/approve         manager, admin
POST   /insights/{insight_id}/reject          manager, admin
"""
from __future__ import annotations

from pathlib import PurePath
from typing import Literal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from psycopg import Connection

from app.db import get_conn
from app.security import current_user, require_role
from app.services.document_text import max_bytes_for
from app.services.guideline_insights import process_document
from app.services.intake import load_gap_report

router = APIRouter(prefix="/api/intake", tags=["intake-documents"])

EDITOR_ROLES = ("manager", "admin")
ACCEPTED_EXTENSIONS = (".pdf", ".docx")
MAX_FILENAME_CHARS = 200

DOCUMENT_SELECT = """
    SELECT d.id, d.category_id, d.filename, d.size_bytes, d.status, d.error_message,
           d.uploaded_at, u.name AS uploaded_by_name,
           (SELECT COUNT(*) FROM guideline_insights gi
             WHERE gi.document_id = d.id AND gi.status <> 'rejected') AS insight_count
    FROM intake_documents d
    LEFT JOIN users u ON u.id = d.uploaded_by
"""

INSIGHT_SELECT = """
    SELECT gi.id, gi.field_id, f.label AS field_label, f.category_id, gi.value, gi.evidence,
           gi.confidence, gi.status, gi.document_id,
           rv.name AS reviewed_by_name, gi.reviewed_at
    FROM guideline_insights gi
    JOIN intake_documents d ON d.id = gi.document_id
    JOIN intake_fields f ON f.id = gi.field_id
    LEFT JOIN users rv ON rv.id = gi.reviewed_by
"""


def _is_editor(user: dict) -> bool:
    return user["role"] in EDITOR_ROLES


def _document_json(row, include_counts: bool) -> dict:
    data = {
        "id": row["id"],
        "categoryId": row["category_id"],
        "filename": row["filename"],
        "sizeBytes": row["size_bytes"],
        "status": row["status"],
        "errorMessage": row["error_message"],
        "uploadedBy": row["uploaded_by_name"] or "",
        "uploadedAt": row["uploaded_at"],
    }
    if include_counts:
        data["insightCount"] = int(row["insight_count"])
    return data


def _insight_json(row) -> dict:
    return {
        "id": row["id"],
        "fieldId": row["field_id"],
        "fieldLabel": row["field_label"],
        "categoryId": row["category_id"],
        "value": row["value"],
        "evidence": row["evidence"],
        "confidence": float(row["confidence"]),
        "status": row["status"],
        "documentId": row["document_id"],
        "reviewedBy": row["reviewed_by_name"] or "",
        "reviewedAt": row["reviewed_at"],
    }


def _fetch_document(conn: Connection, doc_id: str):
    return conn.execute(DOCUMENT_SELECT + " WHERE d.id = %s", (doc_id,)).fetchone()


def _list_documents(conn: Connection, category_id: str | None = None) -> list:
    sql = DOCUMENT_SELECT + " WHERE d.deleted_at IS NULL"
    params: tuple = ()
    if category_id is not None:
        sql += " AND d.category_id = %s"
        params = (category_id,)
    sql += " ORDER BY d.uploaded_at, d.id"
    return conn.execute(sql, params).fetchall()


@router.get("/categories")
def list_categories(user: dict = Depends(current_user), conn: Connection = Depends(get_conn)) -> list[dict]:
    include_counts = _is_editor(user)
    categories = load_gap_report(conn)["categories"]

    documents_by_category: dict[str, list[dict]] = {}
    for row in _list_documents(conn):
        documents_by_category.setdefault(row["category_id"], []).append(
            _document_json(row, include_counts)
        )

    for category in categories:
        category["documents"] = documents_by_category.get(category["id"], [])
        if not include_counts:
            for field in category["fields"]:
                field.pop("note", None)  # internal notes are for managers and admins only
    return categories


@router.post("/categories/{category_id}/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(
    category_id: str,
    request: Request,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    user: dict = Depends(require_role(*EDITOR_ROLES)),
    conn: Connection = Depends(get_conn),
) -> dict:
    category = conn.execute("SELECT 1 FROM intake_categories WHERE id = %s", (category_id,)).fetchone()
    if category is None:
        raise HTTPException(status_code=404, detail="Intake category not found")

    filename = (file.filename or "").strip()
    extension = PurePath(filename).suffix.lower()
    if extension not in ACCEPTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file type: only .pdf and .docx files are accepted",
        )

    limit = max_bytes_for(extension)
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds the {limit // (1024 * 1024)} MB limit",
        )
    if not data:
        raise HTTPException(status_code=422, detail="File is empty")

    row = conn.execute(
        """
        INSERT INTO intake_documents
            (category_id, filename, mime_type, size_bytes, content, status, uploaded_by)
        VALUES (%s, %s, %s, %s, %s, 'processing', %s)
        RETURNING id
        """,
        (
            category_id,
            filename[:MAX_FILENAME_CHARS],
            file.content_type or "application/octet-stream",
            len(data),
            data,
            user["id"],
        ),
    ).fetchone()
    conn.commit()  # the background task reads the row from its own connection, so it must be committed now

    background.add_task(process_document, row["id"], request.app.state.db_pool)
    return _document_json(_fetch_document(conn, row["id"]), include_counts=True)


@router.get("/categories/{category_id}/documents")
def list_category_documents(
    category_id: str,
    user: dict = Depends(current_user),
    conn: Connection = Depends(get_conn),
) -> list[dict]:
    include_counts = _is_editor(user)
    return [_document_json(r, include_counts) for r in _list_documents(conn, category_id)]


@router.get("/documents/{doc_id}")
def get_document(
    doc_id: str,
    user: dict = Depends(require_role(*EDITOR_ROLES)),
    conn: Connection = Depends(get_conn),
) -> dict:
    row = conn.execute(DOCUMENT_SELECT + " WHERE d.id = %s AND d.deleted_at IS NULL", (doc_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    text_row = conn.execute("SELECT extracted_text FROM intake_documents WHERE id = %s", (doc_id,)).fetchone()
    insights = conn.execute(
        INSIGHT_SELECT + " WHERE gi.document_id = %s AND d.deleted_at IS NULL ORDER BY f.sort_order, gi.id",
        (doc_id,),
    ).fetchall()
    data = _document_json(row, include_counts=True)
    data["extractedText"] = text_row["extracted_text"]
    data["insights"] = [_insight_json(i) for i in insights]
    return data


@router.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    doc_id: str,
    user: dict = Depends(require_role(*EDITOR_ROLES)),
    conn: Connection = Depends(get_conn),
) -> Response:
    deleted = conn.execute(
        "UPDATE intake_documents SET deleted_at = now() WHERE id = %s AND deleted_at IS NULL RETURNING id",
        (doc_id,),
    ).fetchone()
    if deleted is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/documents/{doc_id}/reprocess", status_code=status.HTTP_202_ACCEPTED)
def reprocess_document(
    doc_id: str,
    request: Request,
    background: BackgroundTasks,
    user: dict = Depends(require_role(*EDITOR_ROLES)),
    conn: Connection = Depends(get_conn),
) -> dict:
    row = conn.execute(
        "SELECT status FROM intake_documents WHERE id = %s AND deleted_at IS NULL FOR UPDATE",
        (doc_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if row["status"] == "processing":
        raise HTTPException(status_code=409, detail="Document is already being read")

    conn.execute(
        "UPDATE intake_documents SET status = 'processing', error_message = '' WHERE id = %s",
        (doc_id,),
    )
    conn.commit()
    background.add_task(process_document, doc_id, request.app.state.db_pool)
    return _document_json(_fetch_document(conn, doc_id), include_counts=True)


@router.get("/insights")
def list_insights(
    category_id: str | None = Query(default=None, alias="categoryId"),
    insight_status: Literal["draft", "approved", "rejected"] | None = Query(default=None, alias="status"),
    user: dict = Depends(current_user),
    conn: Connection = Depends(get_conn),
) -> list[dict]:
    editor = _is_editor(user)
    if not editor and insight_status not in (None, "approved"):
        raise HTTPException(status_code=403, detail="Only managers and admins can see draft or rejected insights")

    sql = INSIGHT_SELECT + " WHERE d.deleted_at IS NULL"
    params: list = []
    if not editor:
        sql += " AND gi.status = 'approved'"
    elif insight_status is not None:
        sql += " AND gi.status = %s"
        params.append(insight_status)
    if category_id is not None:
        sql += " AND f.category_id = %s"
        params.append(category_id)
    sql += " ORDER BY f.category_id, f.sort_order, gi.id"

    return [_insight_json(r) for r in conn.execute(sql, tuple(params)).fetchall()]


def _review_insight(conn: Connection, insight_id: str, new_status: str, user: dict) -> dict:
    updated = conn.execute(
        """
        UPDATE guideline_insights gi
        SET status = %s, reviewed_by = %s, reviewed_at = now()
        FROM intake_documents d
        WHERE gi.id = %s AND d.id = gi.document_id AND d.deleted_at IS NULL
        RETURNING gi.id
        """,
        (new_status, user["id"], insight_id),
    ).fetchone()
    if updated is None:
        raise HTTPException(status_code=404, detail="Insight not found")
    row = conn.execute(INSIGHT_SELECT + " WHERE gi.id = %s", (insight_id,)).fetchone()
    return _insight_json(row)


@router.post("/insights/{insight_id}/approve")
def approve_insight(
    insight_id: str,
    user: dict = Depends(require_role(*EDITOR_ROLES)),
    conn: Connection = Depends(get_conn),
) -> dict:
    return _review_insight(conn, insight_id, "approved", user)


@router.post("/insights/{insight_id}/reject")
def reject_insight(
    insight_id: str,
    user: dict = Depends(require_role(*EDITOR_ROLES)),
    conn: Connection = Depends(get_conn),
) -> dict:
    return _review_insight(conn, insight_id, "rejected", user)
