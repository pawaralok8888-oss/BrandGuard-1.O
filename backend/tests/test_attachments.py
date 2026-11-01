"""Pure-logic tests for attachment validation and storage (plan sections 4.1 and 5.2)."""
import pytest

from app.services.attachments import (
    MAX_BYTES,
    MAX_FILES,
    MAX_PDF_PAGES,
    UploadError,
    find_duplicate,
    extension_of,
    safe_filename,
    sha256_bytes,
    storage_path,
    validate_pdf_pages,
    validate_upload,
)


def _raises(status, fn, *args):
    with pytest.raises(UploadError) as info:
        fn(*args)
    assert info.value.status_code == status
    return info.value.detail


def test_accepted_extensions_map_to_kinds():
    assert validate_upload("banner.png", 100, 0) == "image"
    assert validate_upload("banner.JPG", 100, 0) == "image"
    assert validate_upload("brief.pdf", 100, 0) == "pdf"
    assert validate_upload("script.docx", 100, 0) == "docx"
    assert validate_upload("notes.txt", 100, 0) == "text"


def test_unsupported_type_is_415():
    _raises(415, validate_upload, "video.mp4", 100, 0)
    _raises(415, validate_upload, "noextension", 100, 0)


def test_empty_file_is_422():
    _raises(422, validate_upload, "banner.png", 0, 0)


def test_size_limit_is_413_and_boundary_is_allowed():
    assert validate_upload("banner.png", MAX_BYTES, 0) == "image"
    _raises(413, validate_upload, "banner.png", MAX_BYTES + 1, 0)


def test_file_count_limit_is_409():
    assert validate_upload("banner.png", 100, MAX_FILES - 1) == "image"
    _raises(409, validate_upload, "banner.png", 100, MAX_FILES)


def test_pdf_page_limit():
    validate_pdf_pages(MAX_PDF_PAGES)
    _raises(413, validate_pdf_pages, MAX_PDF_PAGES + 1)
    _raises(422, validate_pdf_pages, 0)


def test_filename_keeps_only_final_part():
    assert safe_filename("..\\..\\secret\\banner.png") == "banner.png"
    assert safe_filename("../../etc/brief.pdf") == "brief.pdf"
    assert safe_filename("  spf banner.png  ") == "spf banner.png"


def test_filename_drops_control_characters_and_limits_length():
    assert safe_filename("ban\x00ner.png") == "banner.png"
    assert len(safe_filename("a" * 500 + ".png")) == 200


def test_extension_comes_from_cleaned_name():
    assert extension_of("..\\x.PNG") == ".png"


def test_sha256_and_duplicate_detection():
    digest = sha256_bytes(b"same bytes")
    assert digest == sha256_bytes(b"same bytes")
    assert digest != sha256_bytes(b"other bytes")
    existing = {"ATT-0001": digest, "ATT-0002": sha256_bytes(b"x")}
    assert find_duplicate(existing, digest) == "ATT-0001"
    assert find_duplicate(existing, sha256_bytes(b"new")) is None


def test_storage_path_is_under_base_and_uses_safe_extension():
    path = storage_path("/data/uploads", "CNT-0142", "ATT-0007", "..\\banner.PNG")
    assert path.parts[-2:] == ("CNT-0142", "ATT-0007.png")


@pytest.mark.parametrize("content_id", ["../etc", "CNT 1", "CNT/1", "", "a" * 65])
def test_storage_rejects_unsafe_content_id(content_id):
    with pytest.raises(ValueError):
        storage_path("/data", content_id, "ATT-0001", "banner.png")


def test_storage_rejects_unsafe_attachment_id_and_unsupported_extension():
    with pytest.raises(ValueError):
        storage_path("/data", "CNT-1", "../../x", "banner.png")
    with pytest.raises(ValueError):
        storage_path("/data", "CNT-1", "ATT-1", "run.exe")
