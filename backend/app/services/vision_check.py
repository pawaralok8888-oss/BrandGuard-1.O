"""Visual read of one submission (phase 2, plan sections 5.3 steps 2 to 6).

Order of work, and why:
1. Confidential pre-scan on all text (body, file names, OCR including watermarks).
   A match stops everything: no model call is made, and the submission is held.
2. Images are sent in batches of up to 4 per call. Each call costs one unit of the
   CallBudget (10 per submission). When the budget runs out, the remaining images are
   reported as unread, and the status becomes "partial".
3. Each model reply goes through apply_safeguards() before anything is kept.
4. A batch that fails is reported by attachment id. Other batches still run.

The model call is injected (`call`), so tests use a fake and CI never calls Gemini.
Nothing here touches the database. The route saves the result.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

from app.ai.vision_client import VisionError, call_vision
from app.ai.vision_prompt import SYSTEM_PROMPT, build_user_prompt
from app.services.prescan import scan_for_confidential
from app.services.vision_safeguards import (
    MAX_CALLS_PER_SUBMISSION,
    BudgetExceeded,
    CallBudget,
    apply_safeguards,
)

MAX_IMAGES_PER_CALL = 4
HOLD_MESSAGE = (
    "This file was held for manager review because it may contain internal information. "
    "A manager will contact you."
)


@dataclass(frozen=True)
class ImageInput:
    attachment_id: str
    mime_type: str
    data: bytes


@dataclass
class ReadResult:
    status: str  # "ready", "partial", "failed", or "held"
    message: str = ""
    findings: list[dict] = field(default_factory=list)
    not_found: list[str] = field(default_factory=list)
    dropped: dict[str, int] = field(default_factory=dict)
    unread_attachment_ids: list[str] = field(default_factory=list)
    failed_attachment_ids: list[str] = field(default_factory=list)
    calls_used: int = 0


def plan_batches(images: Sequence[ImageInput], per_call: int = MAX_IMAGES_PER_CALL) -> list[list[ImageInput]]:
    """Group images into calls of up to `per_call` images each, keeping their order."""
    if per_call < 1:
        raise ValueError("per_call must be at least 1")
    return [list(images[i:i + per_call]) for i in range(0, len(images), per_call)]


def _merge_counts(into: dict[str, int], more: dict[str, int]) -> None:
    for reason, count in more.items():
        into[reason] = into.get(reason, 0) + count


def run_visual_read(
    *,
    scan_texts: Iterable[str],
    visible_texts: Sequence[str],
    guidelines: Sequence[dict],
    images: Sequence[ImageInput],
    terms: Iterable[str],
    model: str,
    api_key: str,
    title: str = "",
    budget: CallBudget | None = None,
    call: Callable[..., dict] = call_vision,
) -> ReadResult:
    """Read the images of one submission against the guidelines. See the module docstring."""
    if not guidelines:
        raise ValueError("at least one guideline is required")

    scan = scan_for_confidential(scan_texts, terms)
    all_ids = [image.attachment_id for image in images]
    if scan["decision"] == "hold":
        return ReadResult(status="held", message=HOLD_MESSAGE, unread_attachment_ids=all_ids)

    if not images:
        return ReadResult(status="ready", message="No images to read.")

    budget = budget or CallBudget(MAX_CALLS_PER_SUBMISSION)
    allowed_ids = {g["id"] for g in guidelines}
    quote_source = "\n".join(t for t in visible_texts if t)
    user_text = build_user_prompt(guidelines, visible_texts, content_title=title)

    result = ReadResult(status="ready")
    batches = plan_batches(images)
    succeeded = 0

    for index, batch in enumerate(batches):
        batch_ids = [image.attachment_id for image in batch]
        try:
            budget.consume()
        except BudgetExceeded:
            for later in batches[index:]:
                result.unread_attachment_ids.extend(image.attachment_id for image in later)
            break

        result.calls_used += 1
        try:
            reply = call(
                model,
                api_key,
                SYSTEM_PROMPT,
                user_text,
                [(image.mime_type, image.data) for image in batch],
            )
        except VisionError:
            result.failed_attachment_ids.extend(batch_ids)
            continue

        kept, dropped = apply_safeguards(reply, allowed_ids, quote_source)
        _merge_counts(result.dropped, dropped)
        for finding in kept:
            finding["attachmentIds"] = batch_ids
        result.findings.extend(kept)
        for item in reply.get("notFound") or []:
            if isinstance(item, str) and item not in result.not_found:
                result.not_found.append(item)
        succeeded += 1

    result.status = _final_status(succeeded, result)
    result.message = _message(result.status, result)
    return result


def _final_status(succeeded: int, result: ReadResult) -> str:
    if succeeded == 0 and (result.failed_attachment_ids or result.unread_attachment_ids):
        return "failed"
    if result.failed_attachment_ids or result.unread_attachment_ids:
        return "partial"
    return "ready"


def _message(status: str, result: ReadResult) -> str:
    if status == "ready":
        return ""
    if status == "failed":
        return "The images could not be read. Use Reprocess to try again."
    parts = []
    if result.failed_attachment_ids:
        parts.append(f"{len(result.failed_attachment_ids)} image(s) could not be read")
    if result.unread_attachment_ids:
        parts.append(f"{len(result.unread_attachment_ids)} image(s) were not read because the check limit was reached")
    return "Partly read: " + "; ".join(parts) + "."
