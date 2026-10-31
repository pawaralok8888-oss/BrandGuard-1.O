"""Fact-change impact (Person 3).

Finds published content linked to a fact, and alerts only the owners of that content.
"""
from __future__ import annotations

import uuid

from psycopg import Connection

PUBLISHED = "Published"
NEEDS_REVALIDATION = "Needs revalidation"
ALERT_PRIORITIES = ("High", "Medium")


def preview_fact_impact(conn: Connection, fact_id: str) -> dict:
    """Read-only: which published posts and owners a change to this fact would affect."""
    rows = conn.execute(
        """
        SELECT DISTINCT c.id AS content_id, c.title, c.owner_id
        FROM fact_content_links l
        JOIN content c ON c.id = l.content_id
        WHERE l.source_kind = 'fact' AND l.fact_id = %s AND c.status = %s
        ORDER BY c.id
        """,
        (fact_id, PUBLISHED),
    ).fetchall()

    owners = sorted({r["owner_id"] for r in rows if r["owner_id"]})
    return {
        "factId": fact_id,
        "affectedItems": [
            {"contentId": r["content_id"], "title": r["title"], "ownerId": r["owner_id"]}
            for r in rows
        ],
        "affectedOwners": owners,
    }


def apply_fact_change(
    conn: Connection,
    fact_id: str,
    old_statement: str,
    new_statement: str,
    new_version: int,
    severity: str,
    suggested_fix: str,
) -> dict:
    """Mark affected published posts and alert their owners.

    Runs inside the caller's transaction. Does not call run_check; the caller
    does that after this returns, so the posts are already in Needs revalidation.
    Raises ValueError for an unknown severity, before any SQL runs.
    """
    if severity not in ALERT_PRIORITIES:
        raise ValueError(f"Unsupported fact severity: {severity!r}")

    impact = preview_fact_impact(conn, fact_id)
    if not impact["affectedItems"]:
        return impact

    content_ids = [i["contentId"] for i in impact["affectedItems"]]

    conn.execute(
        "UPDATE content SET status = %s, updated_at = now() WHERE id = ANY(%s) AND status = %s",
        (NEEDS_REVALIDATION, content_ids, PUBLISHED),
    )

    alerts: list[dict] = []
    for item in impact["affectedItems"]:
        alert_id = f"AL-{uuid.uuid4().hex[:12]}"
        alerts.append({
            "id": alert_id,
            "recipient_id": item["ownerId"],
            "content_id": item["contentId"],
            "title": f"Fact {fact_id} changed: {item['title']}",
            "priority": severity,
            "old_value": old_statement,
            "new_value": new_statement,
            "suggested_fix": suggested_fix,
        })
        conn.execute(
            """
            INSERT INTO alerts
                (id, recipient_id, content_id, source_id, source_version, priority,
                 title, reason, old_value, new_value, old_text, suggested_fix)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                alert_id,
                item["ownerId"],
                item["contentId"],
                fact_id,
                new_version,
                severity,
                f"Fact {fact_id} changed: {item['title']}",
                "A fact used in your published post has changed.",
                old_statement,
                new_statement,
                old_statement,
                suggested_fix,
            ),
        )

    impact["alerts"] = alerts
    return impact

