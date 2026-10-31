"""Evidence retrieval: the facts and guidelines the AI check compares a post against.

Without a query, every active fact and guideline for the channel is returned. With a query (the
masked post text), each kind is ranked by similarity and only the closest EVIDENCE_TOP_K are
returned. Items with no stored vector for their current version are always included, so a
missing embedding can only add evidence, never hide it. If the query cannot be embedded, all
active items are returned.

Return shape: source_id, version, text, kind. Facts come first, then guidelines.
"""
from __future__ import annotations

from psycopg import Connection

from app.ai.embeddings import KIND_FACT, KIND_GUIDELINE, embed_query, to_pgvector
from app.config import get_settings

# Facts with these statuses are sent to the AI. "Expired" facts are not.
ACTIVE_FACT_STATUSES = ["Active", "Expiring soon"]


def _select_relevant(
    conn: Connection, kind: str, items: list[dict], query_vector: list[float], limit: int
) -> list[dict]:
    if len(items) <= limit:
        return items

    rows = conn.execute(
        "SELECT source_id, version, vector <=> %s::vector AS distance FROM embeddings WHERE kind = %s",
        (to_pgvector(query_vector), kind),
    ).fetchall()
    distance = {(r["source_id"], r["version"]): float(r["distance"]) for r in rows}

    def key(item: dict) -> tuple[str, int]:
        return (item["source_id"], item["version"])

    scored = sorted((i for i in items if key(i) in distance), key=lambda i: distance[key(i)])
    keep = {key(i) for i in scored[:limit]}
    keep |= {key(i) for i in items if key(i) not in distance}  # no vector yet: always include
    return [i for i in items if key(i) in keep]


def get_evidence(conn: Connection, channel: str, query_text: str | None = None) -> list[dict]:
    facts = conn.execute(
        """
        SELECT id, version, statement AS text FROM facts
        WHERE status = ANY(%s)
        ORDER BY id
        """,
        (ACTIVE_FACT_STATUSES,),
    ).fetchall()

    guidelines = conn.execute(
        """
        SELECT id, version, text FROM guidelines
        WHERE is_active = TRUE AND %s = ANY(applies_to_channels)
        ORDER BY id
        """,
        (channel,),
    ).fetchall()

    fact_items = [
        {"source_id": row["id"], "version": row["version"], "text": row["text"], "kind": "fact"}
        for row in facts
    ]
    guideline_items = [
        {"source_id": row["id"], "version": row["version"], "text": row["text"], "kind": "guideline"}
        for row in guidelines
    ]

    limit = get_settings().evidence_top_k
    needs_ranking = len(fact_items) > limit or len(guideline_items) > limit
    if query_text and query_text.strip() and needs_ranking:
        query_vector = embed_query(query_text)
        if query_vector is not None:
            fact_items = _select_relevant(conn, KIND_FACT, fact_items, query_vector, limit)
            guideline_items = _select_relevant(conn, KIND_GUIDELINE, guideline_items, query_vector, limit)

    return fact_items + guideline_items
