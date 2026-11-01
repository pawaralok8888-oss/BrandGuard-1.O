"""Pure-logic tests for OCR cleaning and PDF helpers. No OCR engine, no PDF library needed."""
from app.services.ocr import (
    all_text,
    is_watermark,
    split_lines,
    to_normalised_bbox,
    visible_text,
)
from app.services.pdf_render import PdfRenderError, check_page_count
from app.services.pdf_text import text_layer_usable

BOX = [[100, 50], [300, 50], [300, 90], [100, 90]]  # pixels on a 1000 x 500 image


def test_bbox_is_normalised_to_0_1():
    assert to_normalised_bbox(BOX, 1000, 500) == [0.1, 0.1, 0.2, 0.08]


def test_bbox_is_clamped_to_image_edges():
    wide = [[-20, -10], [1100, -10], [1100, 90], [-20, 90]]
    assert to_normalised_bbox(wide, 1000, 500) == [0.0, 0.0, 1.0, 0.18]


def test_bbox_none_for_bad_input():
    assert to_normalised_bbox(None, 1000, 500) is None
    assert to_normalised_bbox(BOX, 0, 500) is None
    assert to_normalised_bbox([[5, 5]], 1000, 500) is None  # one point, no area
    assert to_normalised_bbox([["a", "b"]], 1000, 500) is None


def test_watermarks_are_detected():
    assert is_watermark("shutterstock.com·2579651553")
    assert is_watermark("© 2024 Some Agency")
    assert is_watermark("2579651553")
    assert is_watermark("Copyright")


def test_product_text_is_not_a_watermark():
    for text in ["SUN", "SCREEN", "SPF 30", "Dot & Key", "30", "Water resistant 80 min"]:
        assert not is_watermark(text), text


def test_low_score_and_empty_lines_are_dropped():
    raw = [
        [BOX, "SPF 30", 0.95],
        [BOX, "blurry", 0.2],
        [BOX, "   ", 0.99],
        [BOX, "SCREEN", 0.6],
    ]
    lines = split_lines(raw, 1000, 500)
    assert [l["text"] for l in lines] == ["SPF 30", "SCREEN"]


def test_visible_text_hides_watermarks_but_all_text_keeps_them():
    raw = [
        [BOX, "SUN", 0.9],
        [BOX, "shutterstock.com·2579651553", 0.9],
    ]
    lines = split_lines(raw, 1000, 500)
    assert visible_text(lines) == ["SUN"]
    assert "shutterstock" in all_text(lines)  # the confidentiality pre-scan still sees it


def test_split_lines_tolerates_none_and_malformed_items():
    assert split_lines(None, 1000, 500) == []
    assert split_lines([["bad"], [BOX, "SUN", "not a score"]], 1000, 500) == []


def test_page_count_rule():
    check_page_count(5, 20)
    try:
        check_page_count(21, 20)
    except PdfRenderError:
        pass
    else:
        raise AssertionError("expected PdfRenderError")


def test_text_layer_usable_threshold():
    assert text_layer_usable(["This is a real text page with enough words in it to count."])
    assert not text_layer_usable(["", "  "])  # scanned page: no text layer
