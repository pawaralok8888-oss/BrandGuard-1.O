"""Safeguards for model findings in phase 2 (plan section 5.5).

Pure functions only: no database, no network, no model. The reading pipeline calls these
on every model response before anything is saved. Standard library only, so they can be
unit-tested anywhere.

A finding is kept only if it passes every check below. Anything else is dropped, and the
reason is counted so the team can see why.
"""
from __future__ import annotations

from typing import Any, Iterable

MIN_CONFIDENCE = 0.30
REVIEW_BELOW = 0.60
MAX_CALLS_PER_SUBMISSION = 10

# Model finding type -> stored finding type (the `findings.type` column and `Finding.type` in the frontend).
TYPE_MAP = {
    "claim": "claim",
    "disclaimer": "claim",
    "tone": "tone",
    "terminology": "rule",
    "visual": "image",
    "accessibility": "accessibility",
}
TEXT_TYPES = {"claim", "disclaimer", "tone", "terminology"}
VISUAL_TYPES = {"visual", "accessibility"}


class BudgetExceeded(Exception):
    """Raised when a submission would make more model calls than allowed."""


class CallBudget:
    """Counts model calls for one submission. Call consume() before each call."""

    def __init__(self, limit: int = MAX_CALLS_PER_SUBMISSION) -> None:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        self.limit = limit
        self.used = 0

    @property
    def remaining(self) -> int:
        return self.limit - self.used

    def consume(self) -> None:
        if self.used >= self.limit:
            raise BudgetExceeded(f"Model call limit of {self.limit} reached for this submission")
        self.used += 1


def valid_bbox(bbox: Any) -> list[float] | None:
    """[x, y, width, height], each between 0 and 1, width and height above 0. Otherwise None."""
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    try:
        x, y, w, h = (float(v) for v in bbox)
    except (TypeError, ValueError):
        return None
    if any(v != v for v in (x, y, w, h)):  # NaN check
        return None
    if not all(0.0 <= v <= 1.0 for v in (x, y, w, h)):
        return None
    if w <= 0 or h <= 0:
        return None
    return [x, y, w, h]


def quote_in_text(quote: str, text: str) -> bool:
    """The quote must be non-empty and appear exactly in the extracted text."""
    quote = (quote or "").strip()
    return bool(quote) and quote in text


def clamp_confidence(value: Any) -> float | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v != v:
        return None
    return min(max(v, 0.0), 1.0)


def decide_route(confidential_matches: int) -> str:
    """'hold' if any confidential term was found before the model call, otherwise 'proceed'."""
    return "hold" if confidential_matches > 0 else "proceed"


def apply_safeguards(
    output: dict,
    allowed_guideline_ids: Iterable[str],
    extracted_text: str,
) -> tuple[list[dict], dict[str, int]]:
    """Filter one model response. Returns (kept findings, counts of dropped findings by reason).

    `output` has the shape in phase2_contract.md section 6: "facts", "findings", "notFound".
    Each kept finding is a dict with the stored finding type, bbox, confidence and review flag.
    """
    allowed = set(allowed_guideline_ids)
    facts = output.get("facts") or []
    fact_by_id: dict[str, dict] = {}
    for fact in facts:
        if isinstance(fact, dict) and isinstance(fact.get("id"), str):
            fact_by_id[fact["id"]] = fact

    kept: list[dict] = []
    dropped: dict[str, int] = {}

    def drop(reason: str) -> None:
        dropped[reason] = dropped.get(reason, 0) + 1

    for raw in output.get("findings") or []:
        if not isinstance(raw, dict):
            drop("malformed")
            continue

        model_type = raw.get("type")
        if model_type not in TYPE_MAP:
            drop("unknown_type")
            continue

        guideline_id = raw.get("guidelineId")
        if guideline_id not in allowed:
            drop("unknown_guideline")
            continue

        fact_ids = raw.get("factIds")
        if not isinstance(fact_ids, list) or not fact_ids:
            drop("no_fact")
            continue
        referenced = [fact_by_id.get(fid) for fid in fact_ids]
        if any(f is None for f in referenced):
            drop("unknown_fact")
            continue

        confidence = clamp_confidence(raw.get("confidence"))
        if confidence is None or confidence < MIN_CONFIDENCE:
            drop("low_confidence")
            continue

        if model_type in TEXT_TYPES and not quote_in_text(raw.get("quote", ""), extracted_text):
            drop("quote_not_found")
            continue

        is_visual = model_type in VISUAL_TYPES
        bbox = None
        if is_visual:
            bbox = valid_bbox(referenced[0].get("bbox"))  # None means a whole-image finding

        kept.append({
            "type": TYPE_MAP[model_type],
            "severity": raw.get("severity", "warning"),
            "title": str(raw.get("title", ""))[:200],
            "reason": str(raw.get("reason", "")),
            "suggestedFix": str(raw.get("suggestedFix", "")),
            "sourceId": guideline_id,
            "originalText": (raw.get("quote") or "").strip() if model_type in TEXT_TYPES else "",
            "bbox": bbox,
            "confidence": round(confidence, 3),
            "aiGenerated": True,
            "needsHumanReview": is_visual or confidence < REVIEW_BELOW,
            "factIds": fact_ids,
        })

    return kept, dropped
