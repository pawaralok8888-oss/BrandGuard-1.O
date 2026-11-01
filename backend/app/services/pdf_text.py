"""Read the text layer of a PDF, so text PDFs don't need OCR (plan section 5.3 step 1).

text_layer_usable() is pure. The pypdf calls import the library inside the function.
"""
from __future__ import annotations

MIN_USABLE_CHARS = 40


def text_layer_usable(page_texts: list[str], min_chars: int = MIN_USABLE_CHARS) -> bool:
    """True if the PDF has enough real text. A scanned PDF has almost none and needs rendering + OCR."""
    total = sum(len("".join(text.split())) for text in page_texts)
    return total >= min_chars


def extract_page_texts(path: str) -> list[str]:
    from pypdf import PdfReader

    reader = PdfReader(path)
    return [(page.extract_text() or "") for page in reader.pages]
