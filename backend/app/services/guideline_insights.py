"""Reads an uploaded intake document with the LLM and stores draft insights, one per field.

Runs in the background after an upload or a reprocess request (see routes/intake_documents.py).
It opens its own database connections, because the request's connection is closed before
background work runs. Never log document text or insight text.

Steps, with a database connection held only during the reads and writes (never during the model call):
  1. Load the document bytes and the category's fields.
  2. Extract text. No text -> status failed.
  3. Call the model (in chunks if the text is long) and merge the answers.
  4. Save one draft insight per field. Rows that a manager already approved or rejected are kept.
  5. Set the document to ready.
"""
from __future__ import annotations

import logging
from pathlib import PurePath

from pydantic import BaseModel, Field

from app.ai.client import AIUnavailable, call_llm
from app.services.document_text import UnsupportedDocument, extract_text

logger = logging.getLogger(__name__)

MAX_SINGLE_CALL_CHARS = 60_000
CHUNK_CHARS = 30_000
MAX_VALUE_CHARS = 1000
MAX_EVIDENCE_CHARS = 300

NO_TEXT_MESSAGE = "No readable text. Upload a text-based PDF or a DOCX, not a scanned image."
AI_FAILED_MESSAGE = "AI reading failed. Use Reprocess to try again."
UNEXPECTED_MESSAGE = "Processing failed unexpectedly. Use Reprocess to try again."
REVIEW_PREFIX = "[Needs review: the source text still has a placeholder] "
NO_ANSWERS_MESSAGE = (
    "The reader found no usable answers in this document for the fields in this category. "
    "Check the document text, or use Reprocess."
)

SYSTEM_PROMPT = """You read one brand guideline document and answer a list of brand intake fields.

Rules:
- Use only what the document says. Do not invent facts, numbers, names or wording.
- For each field the document answers, return one insight with:
  - fieldId: the id exactly as given.
  - value: a plain statement of what the document says. At most 1000 characters.
  - evidence: a short excerpt copied exactly from the document. At most 300 characters.
  - confidence: a number from 0 to 1. Use lower values when the wording is vague or partial.
- If the document does not answer a field, put its fieldId in "notFound".
- Reply with one JSON object only, with the keys "insights" and "notFound". No prose, no markdown."""


def is_placeholder(text: str) -> bool:
    """True when source text still contains a template placeholder such as [PLACEHOLDER: interval]."""
    return "PLACEHOLDER" in text.upper()


def fields_needing_second_pass(fields, answered_ids: set[str], not_found_ids: set[str]) -> list:
    """Fields the model neither answered nor said were missing. They get one focused call each."""
    return [f for f in fields if f["id"] not in answered_ids and f["id"] not in not_found_ids]


class InsightItem(BaseModel):
    fieldId: str
    value: str = ""
    evidence: str = ""
    confidence: float = 0.0


class InsightOutput(BaseModel):
    insights: list[InsightItem] = Field(default_factory=list)
    notFound: list[str] = Field(default_factory=list)


def process_document(document_id: str, pool) -> None:
    """Entry point for BackgroundTasks. Never raises: failures are saved on the document."""
    try:
        _process(document_id, pool)
    except Exception:
        logger.exception("Insight processing crashed for document %s", document_id)
        _set_document_state(pool, document_id, "failed", UNEXPECTED_MESSAGE)


def _process(document_id: str, pool) -> None:
    with pool.connection() as conn:
        doc = conn.execute(
            "SELECT id, category_id, filename, content FROM intake_documents "
            "WHERE id = %s AND deleted_at IS NULL",
            (document_id,),
        ).fetchone()
        if doc is None:
            return
        fields = conn.execute(
            "SELECT id, label, description FROM intake_fields "
            "WHERE category_id = %s ORDER BY sort_order, id",
            (doc["category_id"],),
        ).fetchall()

    extension = PurePath(doc["filename"]).suffix.lower()
    try:
        text = extract_text(extension, bytes(doc["content"])).strip()
    except UnsupportedDocument as exc:
        _set_document_state(pool, document_id, "failed", str(exc))
        return
    if not text:
        _set_document_state(pool, document_id, "failed", NO_TEXT_MESSAGE)
        return

    with pool.connection() as conn:
        conn.execute(
            "UPDATE intake_documents SET extracted_text = %s WHERE id = %s",
            (text, document_id),
        )

    try:
        merged, stats = _read_with_model(text, fields)
    except AIUnavailable:
        logger.warning("Model could not read document %s", document_id)
        _set_document_state(pool, document_id, "failed", AI_FAILED_MESSAGE)
        return

    # Warnings are shown by the server log by default; info lines are not. Keep counts only, never text.
    logger.warning(
        "Document %s: model returned %d answer(s), %d dropped (unknown field id or empty value), "
        "%d field(s) listed as not found, %d field(s) re-asked alone, %d draft insight(s) to save",
        document_id, stats["returned"], stats["dropped"], stats["not_found"],
        stats["second_pass"], len(merged),
    )
    _save_insights(pool, document_id, merged)
    if merged:
        _set_document_state(pool, document_id, "ready", "")
    else:
        _set_document_state(pool, document_id, "ready", NO_ANSWERS_MESSAGE)


def split_text(text: str) -> list[str]:
    if len(text) <= MAX_SINGLE_CALL_CHARS:
        return [text]
    return [text[i:i + CHUNK_CHARS] for i in range(0, len(text), CHUNK_CHARS)]


def _field_list(fields) -> str:
    return "\n".join(f"{f['id']} | {f['label']} | {f['description']}" for f in fields)


def _read_with_model(text: str, fields) -> tuple[dict[str, InsightItem], dict[str, int]]:
    """Returns the best insight per field id (ids from this category only) and counts for the log.

    Pass 1 asks about all fields together. Pass 2 asks about each field that pass 1 neither
    answered nor listed as not found, because the model sometimes skips fields in a long list.
    """
    valid_ids = {f["id"] for f in fields}
    chunks = split_text(text)
    if len(chunks) > 3:
        logger.warning("Long document: reading in %d chunks", len(chunks))

    stats = {"returned": 0, "dropped": 0, "not_found": 0, "second_pass": 0}
    best: dict[str, InsightItem] = {}
    not_found: set[str] = set()

    def absorb(output: InsightOutput) -> None:
        stats["returned"] += len(output.insights)
        not_found.update(output.notFound)
        for item in output.insights:
            if item.fieldId not in valid_ids or not item.value.strip():
                stats["dropped"] += 1
                continue
            item.confidence = min(max(item.confidence, 0.0), 1.0)
            current = best.get(item.fieldId)
            if current is None or item.confidence > current.confidence:
                best[item.fieldId] = item

    for chunk in chunks:
        user_message = f"Fields:\n{_field_list(fields)}\n\nDocument:\n{chunk}"
        absorb(call_llm(SYSTEM_PROMPT, user_message, InsightOutput).output)

    missing = fields_needing_second_pass(fields, set(best), not_found)
    stats["second_pass"] = len(missing)
    for field in missing:
        for chunk in chunks:
            user_message = f"Fields:\n{_field_list([field])}\n\nDocument:\n{chunk}"
            absorb(call_llm(SYSTEM_PROMPT, user_message, InsightOutput).output)

    stats["not_found"] = len(not_found)
    for item in best.values():
        if is_placeholder(item.value) or is_placeholder(item.evidence):
            item.value = REVIEW_PREFIX + item.value
    return best, stats


def _save_insights(pool, document_id: str, merged: dict[str, InsightItem]) -> None:
    """Insert or refresh draft rows. Approved and rejected rows are never overwritten."""
    with pool.connection() as conn:
        for field_id, item in merged.items():
            conn.execute(
                """
                INSERT INTO guideline_insights (document_id, field_id, value, evidence, confidence)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (document_id, field_id) DO UPDATE
                SET value = EXCLUDED.value,
                    evidence = EXCLUDED.evidence,
                    confidence = EXCLUDED.confidence,
                    created_at = now()
                WHERE guideline_insights.status = 'draft'
                """,
                (
                    document_id,
                    field_id,
                    item.value.strip()[:MAX_VALUE_CHARS],
                    item.evidence.strip()[:MAX_EVIDENCE_CHARS],
                    round(item.confidence, 2),
                ),
            )


def _set_document_state(pool, document_id: str, status: str, message: str) -> None:
    with pool.connection() as conn:
        conn.execute(
            "UPDATE intake_documents SET status = %s, error_message = %s WHERE id = %s",
            (status, message, document_id),
        )