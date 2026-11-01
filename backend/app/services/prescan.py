"""Confidentiality pre-scan (phase 2, plan section 5.3 step 2 and section 9).

Runs before any model call. If a confidential term appears anywhere in a submission
(body text, file names, or OCR text including watermarks), the submission is held.

Reuses the existing matcher in app/pipeline/redact.py, so the rules are the same as for
text posts. The result holds counts only. It never includes the term or the matched text.
"""
from __future__ import annotations

from typing import Iterable

from app.pipeline.redact import mask_text, normalise_terms
from app.services.vision_safeguards import decide_route


def scan_for_confidential(texts: Iterable[str], terms: Iterable[str]) -> dict:
    """Return {"decision": "hold" | "proceed", "matches": n}. Never returns the terms or text."""
    active = normalise_terms(terms)
    matches = 0
    if active:
        for text in texts:
            if not text:
                continue
            _masked, count = mask_text(text, active)
            matches += count
    return {"decision": decide_route(matches), "matches": matches}
