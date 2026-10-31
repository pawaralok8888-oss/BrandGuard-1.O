"""Image checks for a content item's attached image.

The results are findings shaped like the rule findings in app.services.checks, so they are
stored in the same check run and shown next to the text findings.

Contrast, colour and alt text checks are estimates or simple rules. Their findings go to a
human (needs_human_review) and the contrast and colour severities are warnings, not critical,
so an estimate cannot block approval on its own.
"""
from __future__ import annotations

import logging
from pathlib import Path

from PIL import UnidentifiedImageError

from app.config import get_settings
from app.services.image_validator import check_alt_text, ImageValidator, measure_text_contrast

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
IMAGE_SOURCE_ID = "IMG-VALIDATOR"


def _finding(
    *,
    finding_type: str,
    severity: str,
    title: str,
    reason: str,
    suggested_fix: str,
    source_id: str,
    confidence: float,
    needs_human_review: bool,
) -> dict:
    return {
        "type": finding_type,
        "start": None,
        "end": None,
        "severity": severity,
        "title": title,
        "reason": reason,
        "sourceId": source_id,
        "sourceVersion": 1,
        "originalText": None,
        "suggestedFix": suggested_fix,
        "confidence": confidence,
        "aiGenerated": False,
        "needsHumanReview": needs_human_review,
        "suggestionKind": "Visual suggestion",
    }


def default_storage_dir() -> Path:
    return Path(get_settings().image_storage_dir)


def find_content_image(storage_dir: Path, content_id: str) -> Path | None:
    """The stored image for a content item. Files are saved as <content_id>.<extension>."""
    for path in sorted(storage_dir.glob(f"{content_id}.*")):
        if path.suffix.lower() in IMAGE_EXTENSIONS:
            return path
    return None


def run_image_checks(image_path: Path, alt_text: str | None, is_logo: bool = False) -> list[dict]:
    """Run every image check on one file and return findings.

    The logo check only runs when is_logo is True. Comparing an ad with the logo file would
    always fail, so it is never run on ordinary images.
    """
    findings: list[dict] = []

    for _ in check_alt_text(alt_text):
        findings.append(_finding(
            finding_type="accessibility",
            severity="warning",
            title="Image has no alt text",
            reason="Screen readers cannot describe this image without alt text.",
            suggested_fix="Add a short description of what the image shows",
            source_id="IMG-ALT",
            confidence=1.0,
            needs_human_review=False,
        ))

    validator = ImageValidator()
    try:
        contrast = measure_text_contrast(str(image_path))
        if contrast["status"] == "fail":
            findings.append(_finding(
                finding_type="accessibility",
                severity="warning",
                title="Text may be too low contrast in the image",
                reason=(
                    f"Text colour {contrast['text']} on background {contrast['background']} "
                    f"has a contrast ratio of {contrast['ratio']}:1. WCAG AA needs 4.5:1. "
                    "This is estimated from the pixels, so please confirm."
                ),
                suggested_fix="Darken the text or lighten the background to reach 4.5:1",
                source_id="IMG-CONTRAST",
                confidence=0.6,
                needs_human_review=True,
            ))

        if is_logo:
            findings.extend(_logo_findings(image_path, validator))

        colour = validator.check_brand_colours(str(image_path))[0]
        if colour["status"] == "fail":
            findings.append(_finding(
                finding_type="image",
                severity="info",
                title="Image has colours outside the brand palette",
                reason=(
                    "Dominant colours " + ", ".join(colour["off_brand_colours"])
                    + " are not in the brand palette. Photos often trigger this, so check it by eye."
                ),
                suggested_fix="Use approved brand colours where the design allows",
                source_id="IMG-COLOUR",
                confidence=0.5,
                needs_human_review=True,
            ))
    except (OSError, UnidentifiedImageError, ValueError) as exc:
        logger.warning("Image checks could not read %s: %s", image_path, exc)
        findings.append(_finding(
            finding_type="image",
            severity="info",
            title="Image could not be analysed",
            reason=(
                f"The uploaded file could not be read ({exc.__class__.__name__}). "
                "Upload it again as PNG, JPEG or WebP."
            ),
            suggested_fix="Upload the image again as PNG, JPEG or WebP",
            source_id=IMAGE_SOURCE_ID,
            confidence=1.0,
            needs_human_review=True,
        ))

    return findings


def _logo_findings(image_path: Path, validator: ImageValidator) -> list[dict]:
    logo_path = Path(get_settings().approved_logo_path)
    if not logo_path.is_file():
        return [_finding(
            finding_type="image",
            severity="info",
            title="Logo check skipped",
            reason=f"The approved logo file was not found on the server ({logo_path.name}), so the logo was not compared.",
            suggested_fix="Set APPROVED_LOGO_PATH to the approved logo file",
            source_id="IMG-LOGO",
            confidence=1.0,
            needs_human_review=True,
        )]
    result = validator.check_logo_match(str(image_path), approved_path=str(logo_path))[0]
    if result["status"] == "approved":
        return []
    return [_finding(
        finding_type="image",
        severity="warning",
        title="This image does not match the approved logo",
        reason=f"Compared with the approved logo, the image differs by {result['distance']} (limit 8).",
        suggested_fix=result["suggested_fix"] or "Replace it with the approved logo",
        source_id="IMG-LOGO",
        confidence=0.7,
        needs_human_review=True,
    )]


def run_content_image_checks(
    content_id: str,
    image_url: str | None,
    alt_text: str | None,
    storage_dir: Path | None = None,
    is_logo: bool = False,
) -> list[dict]:
    """Image findings for a content item. Empty when no image is attached."""
    if not image_url:
        return []

    path = find_content_image(storage_dir or default_storage_dir(), content_id)
    if path is None:
        return [_finding(
            finding_type="image",
            severity="warning",
            title="Attached image file is missing",
            reason=(
                "The image is linked to this draft but the file is not on the server. "
                "This can happen after a redeploy. Upload the image again."
            ),
            suggested_fix="Upload the image again",
            source_id=IMAGE_SOURCE_ID,
            confidence=1.0,
            needs_human_review=True,
        )]

    return run_image_checks(path, alt_text, is_logo=is_logo)
