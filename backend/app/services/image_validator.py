"""Image checks: WCAG contrast, alt text, logo match and brand colours.

Used by app.services.image_checks, which turns the results into findings for a check run.
The contrast, colour and logo checks are estimates, so callers should send their findings to a
human for review.
"""
from collections import Counter
from html.parser import HTMLParser
from typing import Dict, List

import imagehash
from PIL import Image

MIN_CONTRAST_RATIO = 4.5  # WCAG AA for normal text


def relative_luminance(rgb: tuple) -> float:
    def channel(c: int) -> float:
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(rgb1: tuple, rgb2: tuple) -> float:
    l1, l2 = relative_luminance(rgb1), relative_luminance(rgb2)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


def hex_to_rgb(hex_code: str) -> tuple:
    hex_code = hex_code.lstrip("#")
    return tuple(int(hex_code[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb: tuple) -> str:
    return "#%02X%02X%02X" % rgb


class _ImgParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.issues: List[Dict] = []

    def handle_starttag(self, tag, attrs):
        if tag != "img":
            return
        attrs = dict(attrs)
        if not (attrs.get("alt") or "").strip():
            self.issues.append({
                "type": "missing_alt_text",
                "severity": "warning",
                "src": attrs.get("src", "unknown"),
                "suggested_fix": "Add descriptive alt text",
            })


def check_alt_text(alt: str | None) -> List[Dict]:
    """Alt text for an uploaded image. Empty or blank alt text is a finding."""
    if alt and alt.strip():
        return []
    return [{
        "type": "missing_alt_text",
        "severity": "warning",
        "suggested_fix": "Add a short description of what the image shows",
    }]


class ImageValidator:
    def __init__(self, approved_logo_path: str = "test_data/images/approved_logo_v3.2.png"):
        self.min_contrast_ratio = MIN_CONTRAST_RATIO
        self.approved_colors = {
            "primary_green": "#2D5F3F",
            "secondary_green": "#B8E6D5",
        }
        self.approved_logo_path = approved_logo_path

    # 1. Contrast between two known colours (CSS values, not images)
    def check_text_contrast(self, text_hex: str, background_hex: str) -> List[Dict]:
        ratio = contrast_ratio(hex_to_rgb(text_hex), hex_to_rgb(background_hex))
        passed = ratio >= self.min_contrast_ratio
        return [{
            "type": "contrast_check",
            "status": "pass" if passed else "fail",
            "ratio": round(ratio, 2),
            "severity": None if passed else "critical",
            "suggested_fix": None if passed else "Darken the text or lighten the background to reach 4.5:1",
        }]

    # 2. Alt text in HTML
    def check_alt_text_missing(self, html_content: str) -> List[Dict]:
        parser = _ImgParser()
        parser.feed(html_content)
        return parser.issues

    # 3. Logo version (perceptual hash of the whole image).
    # Not used by the automatic image check: a whole ad image never matches a logo file.
    def check_logo_match(self, image_path: str, max_distance: int = 8, approved_path: str | None = None) -> List[Dict]:
        candidate = imagehash.phash(Image.open(image_path))
        approved = imagehash.phash(Image.open(approved_path or self.approved_logo_path))
        distance = int(candidate - approved)
        matched = distance <= max_distance
        return [{
            "type": "logo_version_check",
            "status": "approved" if matched else "mismatch",
            "distance": distance,
            "severity": None if matched else "warning",
            "suggested_fix": None if matched else "Replace with the approved logo v3.2 from the asset library",
        }]

    # 4. Colours: flag dominant colours far from the brand palette
    def check_brand_colours(self, image_path: str, tolerance: int = 60) -> List[Dict]:
        allowed = [hex_to_rgb(h) for h in self.approved_colors.values()]
        allowed += [(255, 255, 255), (0, 0, 0)]  # white and black are always allowed

        img = Image.open(image_path).convert("RGB").resize((200, 200))
        palette = img.quantize(colors=8).convert("RGB")
        top = sorted(palette.getcolors(maxcolors=40000), reverse=True)[:3]

        off_brand = []
        for _, rgb in top:
            distance = min(sum((a - b) ** 2 for a, b in zip(rgb, ref)) ** 0.5 for ref in allowed)
            if distance > tolerance:
                off_brand.append(rgb_to_hex(rgb))

        return [{
            "type": "colour_check",
            "status": "fail" if off_brand else "pass",
            "off_brand_colours": off_brand,
            "severity": "warning" if off_brand else None,
            "suggested_fix": "Use approved brand colours" if off_brand else None,
        }]


def measure_text_contrast(image_path: str) -> Dict:
    """Estimate text contrast in an image.

    The background is the most common colour. The text is the most common colour clearly
    darker than it. If no darker colour exists, the status is "not_measured" rather than a guess.
    """
    img = Image.open(image_path).convert("RGB")
    img.thumbnail((400, 400))  # keeps the colour count cheap on large images
    counts = Counter(img.getdata())

    background, _ = counts.most_common(1)[0]
    background_sum = sum(background)
    dark = [c for c, _ in counts.most_common() if sum(c) < background_sum - 60]
    if not dark:
        return {
            "text": None,
            "background": rgb_to_hex(background),
            "ratio": None,
            "status": "not_measured",
            "severity": None,
        }

    text = dark[0]
    ratio = contrast_ratio(text, background)
    passed = ratio >= MIN_CONTRAST_RATIO
    return {
        "text": rgb_to_hex(text),
        "background": rgb_to_hex(background),
        "ratio": round(ratio, 2),
        "status": "pass" if passed else "fail",
        "severity": None if passed else "critical",
    }
