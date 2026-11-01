"""Instructions for the vision model (phase 2, plan section 5.4).

Pure string building. The model must answer with one JSON object in the shape given in
phase2_contract.md section 6. Safeguards in services/vision_safeguards.py check the answer.
"""
from __future__ import annotations

from typing import Iterable

SYSTEM_PROMPT = """You check marketing content against a brand's guidelines.

You are given guideline excerpts, a list of allowed guideline ids, and one or more images or texts.
Reply with ONE JSON object and nothing else. No markdown, no prose outside the JSON.

The JSON object has three keys:
- "facts": things you can see or read. Each has "id" (F1, F2, ...), "kind"
  (one of: text, logo, product, person, colour, layout, other), "value" (what you saw, short),
  "bbox" ([x, y, width, height], each between 0 and 1, measured from the top-left corner of the image,
  or null if the fact is not in one place), and "confidence" (0 to 1).
- "findings": problems compared with the guidelines. Each has "factIds" (the ids of facts it is based on,
  at least one), "type" (one of: claim, tone, terminology, disclaimer, visual, accessibility),
  "severity" (critical, warning, or info), "title" (short), "quote" (for claim, tone, terminology and
  disclaimer only: copied EXACTLY, character for character, from the text provided; leave it out for visual types),
  "reason" (one or two sentences), "guidelineId" (must be one of the allowed ids), "suggestedFix",
  and "confidence" (0 to 1).
- "notFound": ids of guideline topics you checked and could not find in the content.

Rules:
- Only report a problem if a guideline in the list clearly supports it. If unsure, use a low confidence.
- Never invent a guideline id. Use only the allowed ids.
- Never invent text. A quote must appear exactly in the text provided.
- Small or blurred text may be misread. Give those facts a low confidence.
- Do not judge personal characteristics of anyone shown in an image.
- Ignore watermarks and stock-photo credits.
"""


def build_user_prompt(
    guidelines: Iterable[dict],
    texts: Iterable[str] = (),
    content_title: str = "",
) -> str:
    """The text part of the request: allowed ids, guideline excerpts, and any text from the submission.

    Each guideline is a dict with "id", "title" and "text". Only these ids may be cited.
    """
    guideline_list = list(guidelines)
    if not guideline_list:
        raise ValueError("at least one guideline is required")

    lines = []
    if content_title:
        lines.append(f"Submission title: {content_title}")
    lines.append("Allowed guideline ids: " + ", ".join(g["id"] for g in guideline_list))
    lines.append("")
    lines.append("Guidelines:")
    for g in guideline_list:
        lines.append(f"[{g['id']}] {g.get('title', '')}: {g.get('text', '')}")

    text_items = [t for t in texts if t and t.strip()]
    if text_items:
        lines.append("")
        lines.append("Text from the submission (quote only from this text):")
        for i, t in enumerate(text_items, start=1):
            lines.append(f"--- text {i} ---")
            lines.append(t)

    lines.append("")
    lines.append("The images follow. Return the JSON object now.")
    return "\n".join(lines)
