"""Render PDF pages to images for the vision model and for OCR (plan sections 5.3 and 7).

Only the page-count rule is pure. Rendering needs pypdfium2, imported inside the function.
"""
from __future__ import annotations

DEFAULT_DPI = 150


class PdfRenderError(Exception):
    pass


def check_page_count(page_count: int, max_pages: int) -> None:
    if page_count < 1:
        raise PdfRenderError("PDF has no pages")
    if page_count > max_pages:
        raise PdfRenderError(f"PDF has {page_count} pages; the limit is {max_pages}")


def render_pages(path: str, max_pages: int, dpi: int = DEFAULT_DPI) -> list:
    """Return one PIL image per page, at the given DPI. Raises PdfRenderError if too long."""
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(path)
    try:
        check_page_count(len(doc), max_pages)
        images = []
        for index in range(len(doc)):
            page = doc[index]
            try:
                bitmap = page.render(scale=dpi / 72)
                images.append(bitmap.to_pil())
            finally:
                page.close()
        return images
    finally:
        doc.close()
