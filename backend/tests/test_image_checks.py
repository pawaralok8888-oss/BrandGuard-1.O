"""Image checks on a content item's attached image: findings, upload route, and the check run.

Images are generated in tmp_path, so no test data files are needed. The route tests use a
fake connection, the same way the existing API tests do.
"""
from __future__ import annotations

import io
from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.routes import content_image
from app.routes.content_image import router
from app.security import current_user
from app.services import checks
from app.services.image_checks import find_content_image, run_content_image_checks, run_image_checks


def _save(path, colour, size=(120, 120)):
    Image.new("RGB", size, colour).save(path)
    return path


def _low_contrast_image(path):
    """White background with light grey text: about 1.6:1, which fails WCAG AA."""
    img = Image.new("RGB", (200, 200), (255, 255, 255))
    img.paste((204, 204, 204), (20, 20, 180, 80))
    img.save(path)
    return path


def _sources(findings):
    return {f["sourceId"] for f in findings}


# ---------- run_image_checks: findings ----------

def test_missing_alt_text_gives_accessibility_warning(tmp_path):
    path = _save(tmp_path / "plain.png", (255, 255, 255))
    findings = run_image_checks(path, alt_text=None)
    alt = [f for f in findings if f["sourceId"] == "IMG-ALT"]
    assert len(alt) == 1
    assert alt[0]["type"] == "accessibility"
    assert alt[0]["severity"] == "warning"
    assert alt[0]["needsHumanReview"] is False


def test_blank_alt_text_is_treated_as_missing(tmp_path):
    path = _save(tmp_path / "plain.png", (255, 255, 255))
    assert "IMG-ALT" in _sources(run_image_checks(path, alt_text="   "))


def test_real_alt_text_gives_no_alt_finding(tmp_path):
    path = _save(tmp_path / "plain.png", (255, 255, 255))
    assert "IMG-ALT" not in _sources(run_image_checks(path, alt_text="Bottle of sunscreen"))


def test_flat_image_is_not_measured_for_contrast(tmp_path):
    """No darker text colour exists, so the check must not invent a contrast finding."""
    path = _save(tmp_path / "flat.png", (255, 255, 255))
    assert "IMG-CONTRAST" not in _sources(run_image_checks(path, alt_text="x"))


def test_low_contrast_text_is_flagged_for_human_review(tmp_path):
    path = _low_contrast_image(tmp_path / "ad.png")
    findings = run_image_checks(path, alt_text="Ad")
    contrast = [f for f in findings if f["sourceId"] == "IMG-CONTRAST"]
    assert len(contrast) == 1
    assert contrast[0]["severity"] == "warning"  # an estimate must not block approval as critical
    assert contrast[0]["needsHumanReview"] is True
    assert contrast[0]["confidence"] < 1.0
    assert contrast[0]["suggestionKind"] == "Visual suggestion"


def test_unreadable_file_gives_info_finding_not_an_exception(tmp_path):
    bad = tmp_path / "broken.png"
    bad.write_bytes(b"not really a png")
    findings = run_image_checks(bad, alt_text="x")
    assert [f["title"] for f in findings] == ["Image could not be analysed"]
    assert findings[0]["severity"] == "info"


def test_every_finding_has_the_fields_the_findings_table_needs(tmp_path):
    path = _low_contrast_image(tmp_path / "ad.png")
    for f in run_image_checks(path, alt_text=None):
        assert f["start"] is None and f["end"] is None  # image findings have no text span
        assert f["type"] in {"image", "accessibility"}
        assert f["severity"] in {"critical", "warning", "info"}
        assert f["sourceVersion"] > 0
        assert 0.0 <= f["confidence"] <= 1.0
        assert f["sourceId"] and not f["sourceId"].startswith(("F-", "G-"))


# ---------- content image lookup ----------

def test_no_image_url_means_no_image_findings(tmp_path):
    assert run_content_image_checks("cnt_1", None, None, storage_dir=tmp_path) == []


def test_image_url_without_a_file_gives_missing_file_warning(tmp_path):
    findings = run_content_image_checks("cnt_1", "/api/content/cnt_1/image", "x", storage_dir=tmp_path)
    assert [f["title"] for f in findings] == ["Attached image file is missing"]
    assert findings[0]["severity"] == "warning"


def test_find_content_image_matches_only_this_content_id(tmp_path):
    _save(tmp_path / "cnt_10.png", (255, 255, 255))
    _save(tmp_path / "cnt_1.png", (255, 255, 255))
    assert find_content_image(tmp_path, "cnt_1").name == "cnt_1.png"
    assert find_content_image(tmp_path, "cnt_2") is None


# ---------- run_rule_check includes the image stage ----------

class _FakeResult:
    def __init__(self, row=None, rows=None):
        self._row, self._rows = row, rows or []

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._rows


class _FakeTx:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeConn:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, tuple(params)))
        if "FROM content WHERE id" in sql and "FOR UPDATE" not in sql:
            return _FakeResult(row={"id": "cnt_1", "channel": "Website", "body_text": "Plain.",
                                    "status": "Draft", "image_url": "/api/content/cnt_1/image",
                                    "alt_text": None})
        if "FOR UPDATE" in sql:
            return _FakeResult(row={"status": "Draft", "body_text": "Plain."})
        if sql.lstrip().startswith("SELECT id, content_id, type"):
            return _FakeResult(rows=[])
        return _FakeResult()

    def transaction(self):
        return _FakeTx()


class _EmptyAI:
    status = "success"
    error = None
    findings = []
    dropped = 0
    redacted = 0
    model = "test-model"
    latency_ms = 0
    input_tokens = 0
    output_tokens = 0
    input_hash = None


def test_run_rule_check_stores_image_findings_in_the_same_check_run(monkeypatch):
    monkeypatch.setattr(checks, "load_active_rules", lambda conn, channel: [])
    monkeypatch.setattr(checks, "run_rules", lambda text, content_id, rules: [])
    monkeypatch.setattr(checks, "load_confidential_terms", lambda conn: [])
    monkeypatch.setattr(checks, "run_ai_stage", lambda *a, **k: _EmptyAI())
    monkeypatch.setattr(checks, "get_settings", lambda: type("S", (), {"brandguard_model": "m"})())
    monkeypatch.setattr(checks, "run_content_image_checks", lambda *a, **k: [{
        "type": "accessibility", "start": None, "end": None, "severity": "warning",
        "title": "Image has no alt text", "reason": "r", "sourceId": "IMG-ALT", "sourceVersion": 1,
        "originalText": None, "suggestedFix": "fix", "confidence": 1.0, "aiGenerated": False,
        "needsHumanReview": False, "suggestionKind": "Visual suggestion",
    }])

    conn = _FakeConn()
    result = checks.run_rule_check(conn, "cnt_1", actor={"id": "u1", "name": "Maya"})

    assert result["checkRunId"].startswith("chk_")
    inserts = [params for sql, params in conn.calls if "INSERT INTO findings" in sql]
    assert any("IMG-ALT" in params for params in inserts)


# ---------- upload route ----------

CREATOR = {"id": "user-creator", "name": "Maya", "role": "creator"}


class _FakePool:
    def __init__(self, conn):
        self._conn = conn

    @contextmanager
    def connection(self):
        yield self._conn


class _RouteConn:
    """Holds one content row and records the UPDATE the upload route makes."""

    def __init__(self, owner_id="user-creator", status="Draft"):
        self.row = {"owner_id": owner_id, "status": status}
        self.updates = []

    def execute(self, sql, params=()):
        if sql.lstrip().startswith("SELECT owner_id, status"):
            return _FakeResult(row=self.row)
        if sql.lstrip().startswith("UPDATE content"):
            self.updates.append(params)
        return _FakeResult()

    def transaction(self):
        return _FakeTx()


def _client(conn, user=CREATOR, storage=None, monkeypatch=None):
    app = FastAPI()
    app.include_router(router)
    app.state.db_pool = _FakePool(conn)
    app.dependency_overrides[current_user] = lambda: user
    if monkeypatch is not None and storage is not None:
        monkeypatch.setattr(content_image, "default_storage_dir", lambda: storage)
    return TestClient(app)


def _png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (64, 32), (45, 95, 63)).save(buf, format="PNG")
    return buf.getvalue()


def test_creator_can_upload_an_image_and_it_is_stored(tmp_path, monkeypatch):
    conn = _RouteConn()
    client = _client(conn, storage=tmp_path, monkeypatch=monkeypatch)

    res = client.post(
        "/api/content/cnt_1/image",
        files={"file": ("ad.png", _png_bytes(), "image/png")},
        data={"alt_text": "  Green sunscreen bottle  "},
    )

    assert res.status_code == 201
    body = res.json()
    assert body["imageUrl"] == "/api/content/cnt_1/image"
    assert (body["imageWidth"], body["imageHeight"]) == (64, 32)
    assert body["altText"] == "Green sunscreen bottle"
    assert (tmp_path / "cnt_1.png").exists()
    assert conn.updates, "the content row should be updated"


def test_upload_rejects_non_image_bytes(tmp_path, monkeypatch):
    client = _client(_RouteConn(), storage=tmp_path, monkeypatch=monkeypatch)
    res = client.post("/api/content/cnt_1/image", files={"file": ("x.png", b"hello", "image/png")})
    assert res.status_code == 422


def test_upload_is_blocked_once_content_is_in_review(tmp_path, monkeypatch):
    client = _client(_RouteConn(status="In Review"), storage=tmp_path, monkeypatch=monkeypatch)
    res = client.post("/api/content/cnt_1/image", files={"file": ("a.png", _png_bytes(), "image/png")})
    assert res.status_code == 409


def test_only_the_owner_can_upload(tmp_path, monkeypatch):
    other = {"id": "user-other", "name": "Sam", "role": "creator"}
    client = _client(_RouteConn(owner_id="user-creator"), user=other, storage=tmp_path, monkeypatch=monkeypatch)
    res = client.post("/api/content/cnt_1/image", files={"file": ("a.png", _png_bytes(), "image/png")})
    assert res.status_code == 403
