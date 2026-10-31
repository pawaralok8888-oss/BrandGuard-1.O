"""Embeddings for facts and guidelines (Gemini embedding model, 1024 dimensions).

Write side: index_item stores the vector for a fact or guideline version after it is saved.
Read side: embed_query turns the masked post into a vector, and evidence.get_evidence ranks
items by distance to it.

Redaction: text is masked with the confidential terms before it is embedded, the same way the
AI stage masks the post and evidence. If the terms cannot be loaded, nothing is embedded
(fail closed).

Best effort: a missing key, a failed call or a database error is logged and skipped. Saving a
fact or guideline never fails because of an embedding. Items without a vector are still
included as evidence (see evidence.py).
"""
from __future__ import annotations

import logging

import httpx
import psycopg
from psycopg import Connection

from app.config import get_settings
from app.pipeline.redact import load_confidential_terms, mask_text

logger = logging.getLogger(__name__)

EMBEDDING_DIMENSIONS = 1024  # matches embeddings.vector vector(1024) in data/schema.sql
GEMINI_EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent"
TIMEOUT_SECONDS = 15

KIND_FACT = "fact"
KIND_GUIDELINE = "guideline"


class EmbeddingUnavailable(Exception):
    """An embedding could not be made. The message holds no text content."""


def to_pgvector(values: list[float]) -> str:
    """Text form of a vector for a ::vector cast. Values are formatted as floats only."""
    return "[" + ",".join(repr(float(v)) for v in values) + "]"


def embed_text(text: str, task_type: str) -> list[float]:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise EmbeddingUnavailable("GEMINI_API_KEY is not set")

    model = settings.embedding_model
    try:
        resp = httpx.post(
            GEMINI_EMBED_URL.format(model=model),
            headers={"x-goog-api-key": settings.gemini_api_key, "Content-Type": "application/json"},
            json={
                "model": f"models/{model}",
                "content": {"parts": [{"text": text}]},
                "taskType": task_type,
                "outputDimensionality": EMBEDDING_DIMENSIONS,
            },
            timeout=TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        values = resp.json()["embedding"]["values"]
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        raise EmbeddingUnavailable(f"embedding call failed: {exc.__class__.__name__}") from exc

    if len(values) != EMBEDDING_DIMENSIONS:
        raise EmbeddingUnavailable(f"expected {EMBEDDING_DIMENSIONS} dimensions, got {len(values)}")
    return [float(v) for v in values]


def embed_query(text: str) -> list[float] | None:
    """Vector for the masked post, or None when embeddings are unavailable."""
    try:
        return embed_text(text, "RETRIEVAL_QUERY")
    except EmbeddingUnavailable as exc:
        logger.warning("Evidence ranking skipped: %s", exc)
        return None


def index_item(conn: Connection, kind: str, source_id: str, version: int, text: str) -> bool:
    """Embed the redacted text of one fact or guideline version and store it. Returns True if stored."""
    try:
        terms = load_confidential_terms(conn)
    except Exception:
        logger.warning("Embedding skipped for %s %s: confidential terms unavailable", kind, source_id)
        return False

    masked, _ = mask_text(text, terms)
    try:
        values = embed_text(masked, "RETRIEVAL_DOCUMENT")
    except EmbeddingUnavailable as exc:
        logger.warning("Embedding skipped for %s %s v%s: %s", kind, source_id, version, exc)
        return False

    try:
        with conn.transaction():  # savepoint: a failed insert rolls back only this row
            conn.execute(
                """
                INSERT INTO embeddings (kind, source_id, version, vector)
                VALUES (%s, %s, %s, %s::vector)
                ON CONFLICT (kind, source_id, version) DO UPDATE SET vector = EXCLUDED.vector
                """,
                (kind, source_id, version, to_pgvector(values)),
            )
    except psycopg.Error:
        logger.exception("Could not store embedding for %s %s v%s", kind, source_id, version)
        return False
    return True


def carry_forward(conn: Connection, kind: str, source_id: str, previous_version: int, version: int) -> None:
    """Copy the vector to a new version whose text did not change. No API call is made."""
    try:
        with conn.transaction():
            conn.execute(
                """
                INSERT INTO embeddings (kind, source_id, version, vector)
                SELECT kind, source_id, %s, vector FROM embeddings
                WHERE kind = %s AND source_id = %s AND version = %s
                ON CONFLICT (kind, source_id, version) DO NOTHING
                """,
                (version, kind, source_id, previous_version),
            )
    except psycopg.Error:
        logger.exception("Could not carry embedding forward for %s %s", kind, source_id)
