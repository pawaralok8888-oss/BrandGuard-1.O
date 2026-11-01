"""Runs the real OCR and PDF libraries on a sample file you provide.

Skipped unless the environment variables are set, so CI (which uses -m "not integration")
never needs the libraries or any files:

  $env:BRANDGUARD_OCR_SAMPLE = "D:\path\to\product.webp"
  $env:BRANDGUARD_PDF_SAMPLE = "D:\path\to\page.pdf"
  pytest tests/test_ocr_integration.py -m integration -v
"""
import os

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.skipif(not os.getenv("BRANDGUARD_OCR_SAMPLE"), reason="BRANDGUARD_OCR_SAMPLE not set")
def test_ocr_reads_text_from_sample_image():
    from app.services.ocr import read_image_lines, visible_text

    lines = read_image_lines(os.environ["BRANDGUARD_OCR_SAMPLE"])
    assert lines, "OCR returned no lines"
    for line in lines:
        assert line["bbox"] is None or all(0.0 <= v <= 1.0 for v in line["bbox"])
    assert visible_text(lines) is not None


@pytest.mark.skipif(not os.getenv("BRANDGUARD_PDF_SAMPLE"), reason="BRANDGUARD_PDF_SAMPLE not set")
def test_pdf_renders_pages_and_reads_text_layer():
    from app.services.pdf_render import render_pages
    from app.services.pdf_text import extract_page_texts, text_layer_usable

    path = os.environ["BRANDGUARD_PDF_SAMPLE"]
    images = render_pages(path, max_pages=20)
    assert images and images[0].width > 0 and images[0].height > 0
    assert isinstance(text_layer_usable(extract_page_texts(path)), bool)
