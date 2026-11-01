"""Local OCR for phase 2 (plan sections 5.3 and 8).

Images are read on this machine with RapidOCR. Nothing is sent to a service here.

Two views of the same text, on purpose:
- every line, including watermarks, is used by the confidentiality pre-scan. A confidential
  name in a watermark still counts.
- visible lines only (watermarks removed) go to the model and the reviewer.

The pure functions below take RapidOCR's raw output, so they can be tested without the
library. The heavy imports are inside read_image_lines().
"""
from __future__ import annotations

import re
from typing import Any

MIN_SCORE = 0.5

# Stock-photo vendors, copyright marks, and long number-only asset ids. Matched case-insensitively.
_WATERMARK_PATTERNS = [
    re.compile(r"shutterstock|istock|getty\s*images|adobe\s*stock|depositphotos|alamy|pixabay", re.I),
    re.compile(r"©|\(c\)|copyright", re.I),
    re.compile(r"^\W*\d{6,}\W*$"),
]


def is_watermark(text: str) -> bool:
    return any(p.search(text or "") for p in _WATERMARK_PATTERNS)


def to_normalised_bbox(points: Any, width: int, height: int) -> list[float] | None:
    """RapidOCR gives four corner points in pixels. Return [x, y, w, h] in 0..1, or None if empty."""
    if width <= 0 or height <= 0 or not points:
        return None
    try:
        xs = [float(p[0]) for p in points]
        ys = [float(p[1]) for p in points]
    except (TypeError, ValueError, IndexError):
        return None
    x0, x1 = max(min(xs), 0.0), min(max(xs), float(width))
    y0, y1 = max(min(ys), 0.0), min(max(ys), float(height))
    if x1 <= x0 or y1 <= y0:
        return None
    return [round(x0 / width, 4), round(y0 / height, 4),
            round((x1 - x0) / width, 4), round((y1 - y0) / height, 4)]


def split_lines(raw: Any, width: int, height: int, min_score: float = MIN_SCORE) -> list[dict]:
    """Turn RapidOCR's raw result ([points, text, score] items, or None) into clean lines.

    Lines with a low score or no text are dropped. Each kept line gets a normalised bbox
    and a watermark flag.
    """
    lines: list[dict] = []
    for item in raw or []:
        try:
            points, text, score = item[0], str(item[1]).strip(), float(item[2])
        except (TypeError, ValueError, IndexError):
            continue
        if not text or score < min_score:
            continue
        lines.append({
            "text": text,
            "score": round(score, 3),
            "bbox": to_normalised_bbox(points, width, height),
            "watermark": is_watermark(text),
        })
    return lines


def visible_text(lines: list[dict]) -> list[str]:
    """Text the model and reviewer may see: everything except watermarks."""
    return [line["text"] for line in lines if not line["watermark"]]


def all_text(lines: list[dict]) -> str:
    """Everything, watermarks included. This is what the confidentiality pre-scan reads."""
    return "\n".join(line["text"] for line in lines)


def read_image_lines(path: str, min_score: float = MIN_SCORE) -> list[dict]:
    """Run RapidOCR on an image file. Needs rapidocr-onnxruntime and Pillow installed."""
    from PIL import Image
    from rapidocr_onnxruntime import RapidOCR

    with Image.open(path) as img:
        width, height = img.size
    raw, _elapsed = RapidOCR()(path)
    return split_lines(raw, width, height, min_score=min_score)
