"""Turns safeguarded findings into rows for the `findings` table (phase 2, plan section 3.2).

Pure logic. The route generates each row's id and check_run_id, then writes the rows.
Returns each row with the attachment ids it came from. The findings table has no column for
attachments, so the route stores those links separately (see the open decision in the plan).

Column rules that the database enforces are checked here, so a bad row never reaches it:
- type is one of rule, claim, tone, image, accessibility, security
- severity is one of critical, warning, info
- suggestion_kind is one of the five values the table allows
- start and end are both set (text findings) or both null
- bbox is four numbers between 0 and 1, or null
- confidence is between 0 and 1
- source_version is above 0
"""
from __future__ import annotations

from typing import Iterable, Mapping

from app.services.vision_safeguards import valid_bbox

STORED_TYPES = {"rule", "claim", "tone", "image", "accessibility", "security"}
SEVERITIES = {"critical", "warning", "info"}

# The database allows only these five suggestion kinds. Confidential findings have no kind of their
# own, so they use "Terminology change". Adding "Manager review" needs a change to the constraint.
SUGGESTION_KIND = {
    "claim": "Claim correction",
    "tone": "Tone rewrite",
    "rule": "Terminology change",
    "image": "Visual suggestion",
    "accessibility": "Visual suggestion",
    "security": "Terminology change",
}

CONFIDENTIAL_SOURCE = "confidential-terms"


class MappingError(ValueError):
    """A finding cannot be stored as it is. The message names the field, not the content."""


def _clamp(value: float) -> float:
    return min(max(float(value), 0.0), 1.0)


def to_finding_row(
    finding: Mapping,
    *,
    content_id: str,
    check_run_id: str | None,
    visible_text: str = "",
    known_guideline_versions: Mapping[str, int] | None = None,
) -> tuple[dict, list[str]]:
    """Map one safeguarded finding to a findings row. Returns (row, attachment_ids)."""
    stored_type = finding.get("type")
    if stored_type not in STORED_TYPES:
        raise MappingError("finding type is not one the table allows")

    severity = finding.get("severity", "warning")
    if severity not in SEVERITIES:
        severity = "warning"

    versions = dict(known_guideline_versions or {})
    source_id = str(finding.get("sourceId") or "")
    if source_id == CONFIDENTIAL_SOURCE or source_id not in versions:
        guideline_id = None
        source_version = 1
    else:
        guideline_id = source_id
        source_version = versions[source_id]
    if source_version < 1:
        raise MappingError("source version must be at least 1")

    original_text = (finding.get("originalText") or "").strip() or None
    start = end = None
    if original_text is not None and visible_text:
        index = visible_text.find(original_text)
        if index >= 0:
            start, end = index, index + len(original_text)

    bbox = valid_bbox(finding.get("bbox")) if finding.get("bbox") is not None else None

    confidence = finding.get("confidence", 0.0)
    try:
        confidence = _clamp(confidence)
    except (TypeError, ValueError):
        raise MappingError("confidence is not a number") from None

    row = {
        "content_id": content_id,
        "check_run_id": check_run_id,
        "type": stored_type,
        "start": start,
        "end": end,
        "bbox": bbox,
        "severity": severity,
        "title": str(finding.get("title", ""))[:200] or "Finding",
        "reason": str(finding.get("reason", "")) or "No reason given.",
        "source_id": source_id or CONFIDENTIAL_SOURCE,
        "source_version": source_version,
        "guideline_id": guideline_id,
        "suggested_fix": str(finding.get("suggestedFix", "")),
        "original_text": original_text,
        "confidence": round(confidence, 3),
        "ai_generated": bool(finding.get("aiGenerated", True)),
        "needs_human_review": bool(finding.get("needsHumanReview", True)),
        "status": "open",
        "suggestion_kind": SUGGESTION_KIND[stored_type],
    }
    attachment_ids = [str(a) for a in finding.get("attachmentIds") or []]
    return row, attachment_ids


def to_finding_rows(
    findings: Iterable[Mapping],
    *,
    content_id: str,
    check_run_id: str | None,
    visible_text: str = "",
    known_guideline_versions: Mapping[str, int] | None = None,
) -> list[tuple[dict, list[str]]]:
    """Map many findings. Any finding that cannot be stored raises MappingError."""
    return [
        to_finding_row(
            f,
            content_id=content_id,
            check_run_id=check_run_id,
            visible_text=visible_text,
            known_guideline_versions=known_guideline_versions,
        )
        for f in findings
    ]
