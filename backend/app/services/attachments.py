"""Upload validation and storage helpers for phase 2 attachments (plan sections 4.1 and 5.2).

Pure standard-library code. The route turns UploadError into an HTTP response with
error.status_code and error.detail, so the rules can be tested without FastAPI.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path, PurePosixPath, PureWindowsPath

MAX_BYTES = 10 * 1024 * 1024
MAX_FILES = 10
MAX_PDF_PAGES = 20
MAX_FILENAME_CHARS = 200

# Extension -> attachment kind. Anything else is refused with 415.
EXTENSION_KINDS = {
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".pdf": "pdf",
    ".docx": "docx",
    ".txt": "text",
}

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class UploadError(Exception):
    """A rule was broken. status_code matches the contract (section 4.3)."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def extension_of(filename: str) -> str:
    return PurePosixPath(safe_filename(filename)).suffix.lower()


def safe_filename(name: str) -> str:
    """Keep only the final name part, with no folders, control characters, or extra length."""
    name = (name or "").strip()
    # Accept both Windows and POSIX separators, so "..\\..\\x.png" becomes "x.png".
    name = re.split(r"[\\/]", name)[-1]
    name = "".join(ch for ch in name if ch.isprintable())
    return name[:MAX_FILENAME_CHARS]


def validate_upload(filename: str, size_bytes: int, existing_count: int) -> str:
    """Return the attachment kind if the upload is allowed. Raise UploadError otherwise."""
    extension = extension_of(filename)
    if extension not in EXTENSION_KINDS:
        raise UploadError(415, "Unsupported file type: use .png, .jpg, .pdf, .docx or .txt")
    if size_bytes <= 0:
        raise UploadError(422, "File is empty")
    if size_bytes > MAX_BYTES:
        raise UploadError(413, f"File size exceeds the {MAX_BYTES // (1024 * 1024)} MB limit")
    if existing_count >= MAX_FILES:
        raise UploadError(409, f"A submission can have at most {MAX_FILES} attachments")
    return EXTENSION_KINDS[extension]


def validate_pdf_pages(page_count: int) -> None:
    if page_count < 1:
        raise UploadError(422, "PDF has no pages")
    if page_count > MAX_PDF_PAGES:
        raise UploadError(413, f"PDF has {page_count} pages; the limit is {MAX_PDF_PAGES}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def find_duplicate(existing: dict[str, str], sha256: str) -> str | None:
    """existing maps attachment id -> sha256. Returns the id of an identical file, or None."""
    for attachment_id, digest in existing.items():
        if digest == sha256:
            return attachment_id
    return None


def storage_path(base_dir: str | Path, content_id: str, attachment_id: str, filename: str) -> Path:
    """Where the file is written: base/<content_id>/<attachment_id><ext>. Ids must be safe."""
    if not _SAFE_ID.match(content_id or ""):
        raise ValueError("unsafe content id")
    if not _SAFE_ID.match(attachment_id or ""):
        raise ValueError("unsafe attachment id")
    extension = extension_of(filename)
    if extension not in EXTENSION_KINDS:
        raise ValueError("unsupported extension")
    return Path(base_dir) / content_id / f"{attachment_id}{extension}"
