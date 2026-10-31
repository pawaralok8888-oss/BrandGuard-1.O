"""Run the rule and AI checks as the system. Called by the fact-change flow.

    The caller must set the post to 'Needs revalidation' first, in the same transaction.
    A post still in 'Published', 'In Review' or 'Approved' is rejected with 409.
"""
from __future__ import annotations

from uuid import uuid4

from fastapi import HTTPException
from psycopg import Connection
from psycopg.types.json import Jsonb

from app.ai.prompt import PROMPT_VERSION
from app.services.image_checks import run_content_image_checks
from app.config import get_settings
from app.pipeline.redact import load_confidential_terms
from app.pipeline.rules import run_rules
from app.services.ai_check import AIStage, run_ai_stage

BLOCKED_STATUSES = ("In Review", "Approved", "Published")

# rule_patterns.kind (database) -> rule type understood by pipeline/rules.py
KIND_MAP = {
    "phrase": "phrase",
    "regex": "regex",
    "name_variant": "name_variant",
    "confidential_term": "confidential",
    "required_text": "required_text",
}

SEVERITY_OK = {"critical", "warning", "info"}

# revisions.actor_label for checks run by the system, with no user row (actor_id is NULL).
SYSTEM_ACTOR_LABEL = "AI Check"


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


BRAND_RULE_SQL = """
    SELECT id, kind, pattern, replacement, channel,
           NULL::text AS guideline_id, title, reason AS text, severity, 1 AS version
    FROM brand_rules
    WHERE status = 'approved'
      AND (channel IS NULL OR channel = %s)
    ORDER BY id
"""


def _rule_from_row(row: dict, channel: str) -> dict | None:
    """One rule dict for run_rules, from a rule_patterns or brand_rules row. None if the kind is unknown."""
    kind = KIND_MAP.get(row["kind"])
    if kind is None:
        return None
    severity = row["severity"] if row["severity"] in SEVERITY_OK else "warning"
    is_security = kind == "confidential"
    rule = {
        "id": row["id"],
        "type": kind,
        "severity_default": "critical" if is_security else severity,
        "title": row["title"] or "Brand rule match",
        "reason": row["text"] or "Matched a configured brand rule.",
        "source_id": row["guideline_id"] or row["id"],
        "source_version": row["version"] or 1,
        "suggested_fix": row["replacement"] or "",
        "replacement": row["replacement"] or "",
        "finding_type": "security" if is_security else "rule",
        "suggestion_kind": "Suggested disclaimer" if kind == "required_text" else "Terminology change",
    }
    if kind == "regex":
        rule["regex"] = row["pattern"]
    elif kind == "required_text":
        rule["required_text"] = row["pattern"]
        rule["required_channels"] = [row["channel"]] if row["channel"] else []
        rule["_channel"] = channel
    elif kind == "name_variant":
        rule["pattern"] = row["pattern"]
    else:
        rule["patterns"] = [row["pattern"]]
    return rule


def load_active_rules(conn: Connection, channel: str) -> list[dict]:
    """Rule dicts for run_rules: active rule_patterns (from seeds and approved guideline rules)
    followed by approved brand_rules. Both are filtered by channel in SQL."""
    rows = conn.execute(
        """
        SELECT rp.id, rp.kind, rp.pattern, rp.replacement, rp.channel,
               rp.guideline_id, g.title, g.text, g.severity, g.version
        FROM rule_patterns rp
        LEFT JOIN guidelines g ON g.id = rp.guideline_id
        WHERE rp.is_active = TRUE
          AND (rp.channel IS NULL OR rp.channel = %s)
        ORDER BY rp.id
        """,
        (channel,),
    ).fetchall()
    brand_rows = conn.execute(BRAND_RULE_SQL, (channel,)).fetchall()

    rules = [r for r in (_rule_from_row(row, channel) for row in rows) if r is not None]
    rules += [r for r in (_rule_from_row(row, channel) for row in brand_rows) if r is not None]
    return rules


def _to_camel(row: dict) -> dict:
    return {
        "id": row["id"],
        "contentId": row["content_id"],
        "type": row["type"],
        "start": row["start"],
        "end": row["end"],
        "bbox": row["bbox"],
        "severity": row["severity"],
        "title": row["title"],
        "reason": row["reason"],
        "sourceId": row["source_id"],
        "sourceVersion": row["source_version"],
        "originalText": row["original_text"],
        "suggestedFix": row["suggested_fix"],
        "confidence": float(row["confidence"]),
        "aiGenerated": row["ai_generated"],
        "needsHumanReview": row["needs_human_review"],
        "status": row["status"],
        "suggestionKind": row["suggestion_kind"],
        "checkRunId": row["check_run_id"],
    }


def run_rule_check(conn: Connection, content_id: str, actor: dict | None) -> dict:
    """Run the rules and AI checks. Returns checkRunId, aiStatus and findings.

    actor is the user who ran the check. Pass None when the system runs it (for example
    the fact-change flow); the revision is then recorded as "AI Check" with no user id.
    """
    content = conn.execute(
        "SELECT id, channel, body_text, status, image_url, alt_text, image_is_logo FROM content WHERE id = %s",
        (content_id,),
    ).fetchone()
    if content is None:
        raise HTTPException(status_code=404, detail="Content not found")
    if content["status"] in BLOCKED_STATUSES:
        raise HTTPException(status_code=409, detail=f"Cannot check content in status {content['status']}")

    body_text = content["body_text"]
    channel = content["channel"]

    # Stage 1: rules (deterministic, no AI).
    rule_findings = run_rules(body_text, content_id, load_active_rules(conn, channel))
    rule_spans = [(f["start"], f["end"]) for f in rule_findings if f["start"] is not None]

    # Stage 2: AI claim and tone check (may fall back to rules only).
    # Redaction is fail-closed: if the confidential terms cannot be loaded, the AI stage is
    # skipped rather than sending unredacted text to the model.
    try:
        confidential_terms = load_confidential_terms(conn)
    except Exception:
        ai = AIStage(status="fallback", error="Confidential terms could not be loaded; AI skipped")
    else:
        ai = run_ai_stage(conn, body_text, channel, rule_spans, confidential_terms)
    # Stage 3: image checks on the attached image (no AI). Empty when there is no image.
    image_findings = run_content_image_checks(
        content_id, content.get("image_url"), content.get("alt_text"),
        is_logo=bool(content.get("image_is_logo")),
    )
    all_findings = rule_findings + ai.findings + image_findings

    check_run_id = _new_id("chk")
    with conn.transaction():
        locked = conn.execute(
            "SELECT status, body_text FROM content WHERE id = %s FOR UPDATE",
            (content_id,),
        ).fetchone()
        if locked is None:
            raise HTTPException(status_code=404, detail="Content not found")
        if locked["status"] in BLOCKED_STATUSES:
            raise HTTPException(status_code=409, detail=f"Cannot check content in status {locked['status']}")
        if locked["body_text"] != body_text:
            raise HTTPException(status_code=409, detail="The draft changed during the check. Run the check again.")

        from_status = locked["status"]

        conn.execute(
            """
            INSERT INTO check_runs
                (id, content_id, started_at, finished_at, rules_count, ai_count,
                 rules_only_fallback, metadata)
            VALUES (%s, %s, now(), now(), %s, %s, %s, %s)
            """,
            (
                check_run_id, content_id, len(rule_findings), len(ai.findings),
                ai.status == "fallback",
                Jsonb({
                    "aiStatus": ai.status,
                    "promptVersion": PROMPT_VERSION,
                    "dropped": ai.dropped,
                    "redactedMatches": ai.redacted,
                    "imageFindings": len(image_findings),
                }),
            ),
        )

        # Replace previous open findings; keep accepted/edited/rejected history.
        conn.execute("DELETE FROM findings WHERE content_id = %s AND status = 'open'", (content_id,))

        for f in all_findings:
            guideline_id = f["sourceId"] if f["sourceId"].startswith("G-") else None
            conn.execute(
                """
                INSERT INTO findings (
                    id, content_id, check_run_id, type, start, "end", bbox,
                    severity, title, reason, source_id, source_version, guideline_id,
                    suggested_fix, original_text, confidence, ai_generated,
                    needs_human_review, status, suggestion_kind
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, NULL,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, 'open', %s
                )
                """,
                (
                    _new_id("fnd"), content_id, check_run_id, f["type"],
                    f["start"], f["end"],
                    f["severity"], f["title"], f["reason"],
                    f["sourceId"], f["sourceVersion"], guideline_id,
                    f["suggestedFix"], f["originalText"] or None,
                    max(0.0, min(1.0, f["confidence"])),
                    bool(f.get("aiGenerated", False)),
                    bool(f.get("needsHumanReview", False)),
                    f["suggestionKind"],
                ),
            )

        # Replace source links for this content: one row per distinct source and version.
        conn.execute("DELETE FROM fact_content_links WHERE content_id = %s", (content_id,))
        seen: set[tuple[str, str, int]] = set()
        for f in all_findings:
            sid = f["sourceId"]
            if sid.startswith("F-"):
                kind = "fact"
            elif sid.startswith("G-"):
                kind = "guideline"
            else:
                continue  # rule without a guideline: nothing to link
            key = (kind, sid, f["sourceVersion"])
            if key in seen:
                continue
            seen.add(key)
            conn.execute(
                """
                INSERT INTO fact_content_links
                    (id, content_id, source_kind, fact_id, guideline_id, source_id,
                     source_version, match_reason)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    _new_id("lnk"), content_id, kind,
                    sid if kind == "fact" else None,
                    sid if kind == "guideline" else None,
                    sid, f["sourceVersion"],
                    "AI claim check" if f.get("aiGenerated") else "rule match",
                ),
            )

        if ai.input_hash:
            conn.execute(
                """
                INSERT INTO ai_calls
                    (id, content_id, check_run_id, model, purpose, input_hash, status,
                     latency_ms, input_tokens, output_tokens, error_message)
                VALUES (%s, %s, %s, %s, 'claim_tone_check', %s, %s, %s, %s, %s, %s)
                """,
                (
                    _new_id("aic"), content_id, check_run_id, ai.model or get_settings().brandguard_model,
                    ai.input_hash, ai.status, ai.latency_ms, ai.input_tokens,
                    ai.output_tokens, ai.error,
                ),
            )

        conn.execute(
            "UPDATE check_runs SET rules_count = %s WHERE id = %s",
            (len(rule_findings), check_run_id),
        )

        to_status = "Checked" if from_status in ("Draft", "Fixing") else from_status
        if to_status != from_status:
            conn.execute(
                "UPDATE content SET status = %s, updated_at = now() WHERE id = %s",
                (to_status, content_id),
            )

        # Human checks record the user. System checks record actor_id NULL and kind 'ai'.
        conn.execute(
            """
            INSERT INTO revisions
                (id, content_id, actor_id, actor_label, kind, action, detail, from_status, to_status)
            VALUES (%s, %s, %s, %s, %s, 'checked', %s, %s, %s)
            """,
            (
                _new_id("rev"), content_id,
                actor["id"] if actor else None,
                actor["name"] if actor else SYSTEM_ACTOR_LABEL,
                "person" if actor else "ai",
                f"Rules check found {len(rule_findings)} issue(s)", from_status, to_status,
            ),
        )
        if ai.input_hash:
            ai_detail = (
                f"AI check found {len(ai.findings)} issue(s)"
                if ai.status != "fallback"
                else f"AI unavailable, rules only: {ai.error}"
            )
            conn.execute(
                """
                INSERT INTO revisions
                    (id, content_id, actor_id, actor_label, kind, action, detail, from_status, to_status)
                VALUES (%s, %s, NULL, 'AI Check', 'ai', 'ai_checked', %s, %s, %s)
                """,
                (_new_id("rev"), content_id, ai_detail, to_status, to_status),
            )

        findings = conn.execute(
            """
            SELECT id, content_id, type, start, "end", bbox, severity, title, reason,
                   source_id, source_version, original_text, suggested_fix, confidence,
                   ai_generated, needs_human_review, status, suggestion_kind, check_run_id
            FROM findings
            WHERE check_run_id = %s
            ORDER BY start NULLS LAST, id
            """,
            (check_run_id,),
        ).fetchall()

    return {
        "checkRunId": check_run_id,
        "model": ai.model or get_settings().brandguard_model,
        "aiStatus": ai.status,
        "aiError": ai.error,
        "rulesOnlyFallback": ai.status == "fallback",
        "findings": [_to_camel(r) for r in findings],
    }


def run_check(conn: Connection, content_id: str) -> dict:
    """Run the rule and AI checks as the system. Called by the fact-change flow.

    The caller must set the post to 'Needs revalidation' first, in the same transaction.
    A post still in 'Published', 'In Review' or 'Approved' is rejected with 409.
    """
    return run_rule_check(conn, content_id, actor=None)


def list_latest_findings(conn: Connection, content_id: str) -> list[dict]:
    """Findings from the most recent check run for this content, open first."""
    rows = conn.execute(
        """
        SELECT f.id, f.content_id, f.type, f.start, f."end", f.bbox, f.severity, f.title,
               f.reason, f.source_id, f.source_version, f.original_text, f.suggested_fix,
               f.confidence, f.ai_generated, f.needs_human_review, f.status,
               f.suggestion_kind, f.check_run_id
        FROM findings f
        WHERE f.check_run_id = (
            SELECT id FROM check_runs
            WHERE content_id = %s
            ORDER BY started_at DESC
            LIMIT 1
        )
        ORDER BY (f.status = 'open') DESC, f.start NULLS LAST, f.id
        """,
        (content_id,),
    ).fetchall()
    return [_to_camel(r) for r in rows]
