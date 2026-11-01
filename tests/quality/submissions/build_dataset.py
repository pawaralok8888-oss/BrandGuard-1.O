"""Builds the 30 labelled test submissions (phase 2, plan section 12.2).

Run once from this folder: python build_dataset.py
It writes files/ (text and PNG files) and manifest.json (the gold answers).

The images are synthetic: drawn text on plain panels, not real product designs. They test
whether the reader finds printed text and visual problems, not whether it can judge real artwork.
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
FILES = HERE / "files"
FILES.mkdir(exist_ok=True)

CONFIDENTIAL_TERM = "Project Nightingale"


def _font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # older Pillow without sized default font
        return ImageFont.load_default()


def _panel(name, lines, background=(255, 255, 255), ink=(20, 20, 20), size=(900, 500)):
    image = Image.new("RGB", size, background)
    draw = ImageDraw.Draw(image)
    y = 40
    for text, pixel_size in lines:
        draw.text((40, y), text, fill=ink, font=_font(pixel_size))
        y += int(pixel_size * 1.8)
    image.save(FILES / name, "PNG")
    return f"files/{name}"


def _text(name, body):
    (FILES / name).write_text(body, encoding="utf-8")
    return f"files/{name}"


def build():
    cases = []

    def add(case_id, kind, path, expected=(), hold=False, note=""):
        cases.append({
            "id": case_id, "kind": kind, "file": path,
            "expected": list(expected), "holdExpected": hold, "note": note,
        })

    E = lambda gid, *must: {"guidelineId": gid, "mustMention": list(must)}

    # Scripts (6): text files
    add("S1", "script", _text("S1.txt", "Hook: Long days outside need a sunscreen that keeps up.\nSay: Dot & Key SPF 50 is light and easy to wear."), note="clean script")
    add("S2", "script", _text("S2.txt", "Hook: Our serum removes all wrinkles overnight.\nSay: Dot & Key makes skin look smooth."),
        [E("G-001", "all wrinkles", "removes all")], note="absolute claim")
    add("S3", "script", _text("S3.txt", "Hook: This cream cures sunburn in one night.\nSay: Dot & Key is a safe fix for burnt skin."),
        [E("G-012", "cures", "sunburn")], note="medical claim")
    add("S4", "script", _text("S4.txt", "Hook: Tired of paying more? Unlike BrandX, we are worth it.\nSay: Try Dot & Key today."),
        [E("G-013", "BrandX")], note="competitor name")
    add("S5", "script", _text("S5.txt", "Hook: The best sunscreen ever made.\nSay: Dot & Key SPF 50, every day."),
        [E("G-002", "best")], note="unsupported superlative")
    add("S6", "script", _text("S6.txt", "Hook: Our customer Maria says her acne is gone.\nSay: Dot & Key is gentle on skin."),
        [E("G-014", "Maria")], note="testimonial without consent note")

    # Marketing ideas (6): text files
    add("M1", "marketing_idea", _text("M1.txt", "Idea: Summer glow challenge. Customers share a photo of their morning routine with Dot & Key SPF 50."), note="clean idea")
    add("M2", "marketing_idea", _text("M2.txt", "Idea: 50% off all sunscreens this weekend, no end date."),
        [E("G-010", "50%")], note="offer without an approved fact")
    add("M3", "marketing_idea", _text("M3.txt", f"Idea: Teaser for {CONFIDENTIAL_TERM}, our secret launch."),
        hold=True, note="confidential launch name")
    add("M4", "marketing_idea", _text("M4.txt", "Idea: Preview our new unreleased serum to the first 100 followers."),
        [E("G-009", "unreleased")], note="unreleased product")
    add("M5", "marketing_idea", _text("M5.txt", "Idea: Switch from CompetitorCo today and get a free tube."),
        [E("G-013", "CompetitorCo")], note="competitor name")
    add("M6", "marketing_idea", _text("M6.txt", "Idea: A week of sunscreen tips from our dermatology partners, posted each morning."), note="clean idea")

    # Designs (9): PNG panels with printed text
    add("D1", "design", _panel("D1.png", [("Dot & Key SPF 50", 46), ("Light, water resistant sunscreen", 26)]), note="clean product panel")
    add("D2", "design", _panel("D2.png", [("Dot & Key", 46), ("Cures sunburn fast", 30)]),
        [E("G-012", "cures", "sunburn")], note="medical claim printed on panel")
    add("D3", "design", _panel("D3.png", [("Dot & Key", 46), ("100% protection guaranteed", 30)]),
        [E("G-001", "100%", "guaranteed")], note="absolute claim printed")
    add("D4", "design", _panel("D4.png", [("Dot & Key", 46), ("The best sunscreen", 30)]),
        [E("G-002", "best")], note="superlative printed")
    add("D5", "design", _panel("D5.png", [("Dot & Key", 46), ("Results in 2 weeks", 30)]),
        [E("G-004", "results", "2 weeks")], note="results claim without disclaimer")
    add("D6", "design", _panel("D6.png", [("Dot & Key", 46), ("Gentle everyday care", 30)], ink=(225, 225, 225)),
        [E("G-007", "contrast")], note="very low contrast text")
    add("D7", "design", _panel("D7.png", [("Dot & Key SPF 50", 40), ("Better than BrandX", 30)]),
        [E("G-013", "BrandX")], note="competitor name printed")
    add("D8", "design", _panel("D8.png", [("Dot & Key", 46), (CONFIDENTIAL_TERM, 34)]),
        hold=True, note="confidential name printed on panel")
    add("D9", "design", _panel("D9.png", [("Dot & Key", 46), ("Your daily sun routine", 30)]), note="clean design")

    # Images (9): PNG graphics with printed text
    add("I1", "image", _panel("I1.png", [("Morning routine", 40), ("Step 1: Cleanse", 26), ("Step 2: Protect", 26)]), note="clean graphic")
    add("I2", "image", _panel("I2.png", [("Cures acne overnight", 40)]),
        [E("G-012", "cures", "acne")], note="medical claim")
    add("I3", "image", _panel("I3.png", [("Guaranteed results", 40)]),
        [E("G-001", "guaranteed")], note="absolute claim")
    add("I4", "image", _panel("I4.png", [("Priya: it changed my skin", 36)]),
        [E("G-014", "Priya")], note="testimonial without consent")
    add("I5", "image", _panel("I5.png", [("Hard to read", 36)], ink=(230, 230, 230)),
        [E("G-007", "contrast")], note="low contrast")
    add("I6", "image", _panel("I6.png", [("Unreleased shade", 40)]),
        [E("G-009", "unreleased")], note="unreleased product")
    add("I7", "image", _panel("I7.png", [("Sun care for everyone", 40)]), note="clean graphic")
    add("I8", "image", _panel("I8.png", [("50% off today", 40)]),
        [E("G-010", "50%")], note="offer without approved fact")
    add("I9", "image", _panel("I9.png", [(CONFIDENTIAL_TERM, 40)]), hold=True, note="confidential name in image")

    kinds = {}
    for c in cases:
        kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
    manifest = {
        "version": 1,
        "note": "Gold answers for 30 test submissions. Images are synthetic. Guideline ids are from the seed (01_foundation.sql).",
        "counts": kinds,
        "terms": [CONFIDENTIAL_TERM],
        "submissions": cases,
    }
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    m = build()
    print("submissions:", len(m["submissions"]), m["counts"])
