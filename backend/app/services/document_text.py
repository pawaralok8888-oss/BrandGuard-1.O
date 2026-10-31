"""Read the text of an uploaded guideline: .txt, .md, .pdf or .docx.

Everything returned is plain text in reading order. Bullets become "- item" lines, so the rule
extractor (app.pipeline.guideline_rules) can read them the same way for every format.

Limits: PDFs of up to MAX_PDF_PAGES pages. Scanned PDFs (no text layer) and password-protected
PDFs are refused with a clear message. Scanned pages would need OCR, which is not included.
"""
from __future__ import annotations

import io
import logging
import zipfile

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from pypdf import PasswordType, PdfReader
from pypdf.errors import PdfReadError

logger = logging.getLogger(__name__)

TEXT_EXTENSIONS = (".txt", ".md")
BINARY_EXTENSIONS = (".pdf", ".docx")
SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS + BINARY_EXTENSIONS
MAX_TEXT_BYTES = 1 * 1024 * 1024
MAX_BINARY_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 100


class UnsupportedDocument(ValueError):
    """The file cannot be read as text. The message is safe to show to the user."""


def max_bytes_for(extension: str) -> int:
    return MAX_BINARY_BYTES if extension in BINARY_EXTENSIONS else MAX_TEXT_BYTES


def extract_text(extension: str, data: bytes) -> str:
    extension = extension.lower()
    if extension in TEXT_EXTENSIONS:
        return _decode_text(data)
    if extension == ".pdf":
        return _pdf_text(data)
    if extension == ".docx":
        return _docx_text(data)
    raise UnsupportedDocument("Only .txt, .md, .pdf and .docx files are accepted")


def _decode_text(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise UnsupportedDocument("File must be valid UTF-8 text")


def _pdf_text(data: bytes) -> str:
    if not data.startswith(b"%PDF-"):
        raise UnsupportedDocument("The file is not a PDF")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and reader.decrypt("") == PasswordType.NOT_DECRYPTED:
            raise UnsupportedDocument("Password-protected PDFs are not supported")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise UnsupportedDocument(f"The PDF has more than {MAX_PDF_PAGES} pages")
        pages = [page.extract_text() or "" for page in reader.pages]
    except UnsupportedDocument:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError, IndexError, OSError) as exc:
        logger.info("PDF could not be read: %s", exc.__class__.__name__)
        raise UnsupportedDocument("The PDF could not be read")

    text = "\n".join(pages)
    if not text.strip():
        raise UnsupportedDocument(
            "This PDF has no text layer, so it may be a scan. Scanned PDFs are not supported yet."
        )
    return text


def _docx_text(data: bytes) -> str:
    if not data.startswith(b"PK"):
        raise UnsupportedDocument("The file is not a Word document")
    try:
        document = Document(io.BytesIO(data))
    except (zipfile.BadZipFile, KeyError, ValueError, OSError) as exc:
        logger.info("DOCX could not be read: %s", exc.__class__.__name__)
        raise UnsupportedDocument("The Word document could not be read")

    lines: list[str] = []
    for child in document.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            paragraph = Paragraph(child, document)
            text = paragraph.text.strip()
            if not text:
                continue
            style = (paragraph.style.name if paragraph.style is not None else "").lower()
            if style.startswith("list"):
                text = f"- {text}"
            elif (style.startswith("heading") or style == "title") and not text.endswith(":"):
                text = f"{text}:"  # headings in Word rarely end with a colon; the rule extractor needs one
            lines.append(text)
        elif tag == "tbl":
            for row in Table(child, document).rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    lines.append("- " + " | ".join(dict.fromkeys(cells)))  # merged cells repeat

    text = "\n".join(lines)
    if not text.strip():
        raise UnsupportedDocument("The Word document has no text")
    return text
