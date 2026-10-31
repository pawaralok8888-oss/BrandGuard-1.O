"""AI claim and tone stage (plan section 3). Returns only findings that pass every safeguard.

Safeguards, in order: the source ID must be one of the evidence items, the quote must
appear exactly in the post, the finding must not overlap a rule finding, very low
confidence is dropped, and confidence below REVIEW_BELOW is shown as a suggestion.
Any failure returns status "fallback" so the rules result is still shown.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field

from psycopg import Connection
from psycopg.types.json import Jsonb
from pydantic import ValidationError

from app.ai.client import AIUnavailable, call_llm
from app.ai.evidence import get_evidence
from app.ai.prompt import PROMPT_VERSION, SYSTEM_PROMPT, build_user_prompt
from app.ai.schemas import AIOutput
from app.config import get_settings
from app.pipeline.redact import mask_text, normalise_terms, terms_digest

logger = logging.getLogger(__name__)

MAX_FINDINGS = 20
DROP_BELOW = 0.30      # very low confidence: discarded
REVIEW_BELOW = 0.60    # below this: shown as a suggestion needing human review


@dataclass
class AIStage:
    status: str                       # success | cached | fallback
    findings: list[dict] = field(default_factory=list)
    model: str = ""
    input_hash: str = ""
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None
    dropped: int = 0
    redacted: int = 0                 # confidential-term matches masked before the call


def _input_hash(body_text: str, channel: str, evidence: list[dict], redaction: str = "") -> str:
    """Cache key. Anything that can change the model's output belongs here:
    prompt version, model name, post text as sent, channel, evidence versions and
    the confidential-term list (so a term change never reuses an old answer)."""
    payload = {
        "text": body_text,
        "channel": channel,
        "prompt": PROMPT_VERSION,
        "model": get_settings().brandguard_model,
        "evidence": [[e["source_id"], e["version"]] for e in evidence],
        "redaction": redaction,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _overlaps_rule(start: int, end: int, rule_spans: list[tuple[int, int]]) -> bool:
    return any(s < end and e > start for s, e in rule_spans)


def _to_findings(
    output: AIOutput,
    body_text: str,
    evidence_by_id: dict[str, dict],
    rule_spans: list[tuple[int, int]],
) -> tuple[list[dict], int]:
    findings: list[dict] = []
    dropped = 0
    seen: set[tuple[str, int]] = set()

    for item in output.findings:
        evidence = evidence_by_id.get(item.source_id)
        if evidence is None or item.confidence < DROP_BELOW:
            dropped += 1
            continue

        start = body_text.find(item.quote)
        if start < 0:
            dropped += 1  # quote is not exactly in the post
            continue
        end = start + len(item.quote)

        if _overlaps_rule(start, end, rule_spans) or (item.source_id, start) in seen:
            dropped += 1  # already covered by a rule finding, or a duplicate
            continue
        if len(findings) >= MAX_FINDINGS:
            dropped += 1
            continue

        seen.add((item.source_id, start))
        findings.append({
            "type": "tone" if item.suggestion_kind == "Tone rewrite" else "claim",
            "start": start,
            "end": end,
            "severity": item.severity,
            "title": item.title,
            "reason": item.reason,
            "sourceId": item.source_id,
            "sourceVersion": int(evidence["version"]),
            "originalText": item.quote,
            "suggestedFix": item.suggested_fix,
            "confidence": item.confidence,
            "aiGenerated": True,
            "needsHumanReview": item.confidence < REVIEW_BELOW,
            "suggestionKind": item.suggestion_kind,
        })
    return findings, dropped


def _read_cache(conn: Connection, input_hash: str) -> AIOutput | None:
    """A cache row that no longer validates is treated as a miss, not an error."""
    with conn.transaction():  # savepoint: a DB error here cannot abort the outer transaction
        row = conn.execute(
            "SELECT output_json FROM ai_cache WHERE input_hash = %s", (input_hash,)
        ).fetchone()
    if row is None:
        return None
    try:
        return AIOutput.model_validate(row["output_json"])
    except ValidationError:
        logger.warning("Ignoring invalid ai_cache entry %s", input_hash[:12])
        return None


def _write_cache(conn: Connection, input_hash: str, output: AIOutput) -> None:
    with conn.transaction():
        conn.execute(
            """
            INSERT INTO ai_cache (input_hash, output_json) VALUES (%s, %s)
            ON CONFLICT (input_hash) DO NOTHING
            """,
            (input_hash, Jsonb(output.model_dump())),
        )


def run_ai_stage(
    conn: Connection,
    body_text: str,
    channel: str,
    rule_spans: list[tuple[int, int]],
    confidential_terms: list[str] | None = None,
) -> AIStage:
    if not body_text.strip():
        return AIStage(status="success")

    # Redaction (plan step 6): confidential terms never leave the server. The model sees
    # masked text and masked evidence; findings are still matched against the original
    # body_text, so a quote containing a mask character cannot match and is dropped.
    # The masked post is also the query for evidence ranking, so the embedding API never
    # sees unmasked text either.
    terms = normalise_terms(confidential_terms or [])
    redaction_key = terms_digest(terms)
    model_body, body_hits = mask_text(body_text, terms)

    evidence = get_evidence(conn, channel, query_text=model_body)
    if not evidence:
        return AIStage(status="success")

    redacted_evidence = []
    evidence_hits = 0
    for item in evidence:
        masked, hits = mask_text(item["text"], terms)
        evidence_hits += hits
        redacted_evidence.append({**item, "text": masked})
    evidence = redacted_evidence

    model = get_settings().brandguard_model
    evidence_by_id = {e["source_id"]: e for e in evidence}
    input_hash = _input_hash(model_body, channel, evidence, redaction_key)
    redacted = body_hits + evidence_hits

    try:
        cached = _read_cache(conn, input_hash)
        if cached is not None:
            findings, dropped = _to_findings(cached, body_text, evidence_by_id, rule_spans)
            return AIStage(status="cached", findings=findings, model=model,
                           input_hash=input_hash, dropped=dropped, redacted=redacted)

        evidence_text = "\n".join(
            f"[{e['source_id']} v{e['version']}] {e['text']}" for e in evidence
        )
        call = call_llm(SYSTEM_PROMPT, build_user_prompt(model_body, channel, evidence_text), AIOutput)
        try:
            _write_cache(conn, input_hash, call.output)
        except Exception:  # a cache write failure must not discard a good answer
            logger.warning("Could not write ai_cache; continuing without caching")

        findings, dropped = _to_findings(call.output, body_text, evidence_by_id, rule_spans)
        return AIStage(
            status="success",
            findings=findings,
            model=call.model,
            input_hash=input_hash,
            latency_ms=call.latency_ms,
            input_tokens=call.input_tokens,
            output_tokens=call.output_tokens,
            dropped=dropped,
            redacted=redacted,
        )
    except AIUnavailable as exc:
        return AIStage(status="fallback", input_hash=input_hash, model=model, error=str(exc)[:500],
                       redacted=redacted)
    except Exception as exc:  # the rules result must never be blocked by the AI stage
        logger.exception("AI stage failed")
        return AIStage(status="fallback", input_hash=input_hash, model=model,
                       error=f"AI stage failed: {exc.__class__.__name__}", redacted=redacted)
