from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.db import get_conn
from app.routes.knowledge import (
    EXPIRING_SOON_DAYS,
    FactCreate,
    GlossaryCreate,
    GuidelineCreate,
    derive_fact_status,
    generate_next_id,
    next_id,
    router,
)
from app.security import current_user


# -----------------------------------------------------------------------------
# Fakes for DB connection
# -----------------------------------------------------------------------------
from tests.lookups import lookup_rows


class FakeResult:
    def __init__(self, row: dict[str, Any] | None = None, rows: list[dict[str, Any]] | None = None):
        self._row = row
        self._rows = rows or []

    def fetchone(self) -> dict[str, Any] | None:
        return self._row

    def fetchall(self) -> list[dict[str, Any]]:
        return self._rows


class FakeTransaction:
    def __enter__(self) -> FakeTransaction:
        return self

    def __exit__(self, *exc: Any) -> bool:
        return False


class FakeConn:
    def __init__(
        self,
        existing_facts: list[str] | None = None,
        existing_guidelines: list[str] | None = None,
        existing_glossary: list[str] | None = None,
        products: set[str] | None = None,
        users: set[str] | None = None,
    ):
        self.calls: list[tuple[str, tuple]] = []
        self.existing_facts = existing_facts or []
        self.existing_guidelines = existing_guidelines or []
        self.existing_glossary = existing_glossary or []
        self.products = products or {"P-001", "P-002"}
        self.users = users or {"user-manager", "user-admin", "user-creator"}

    def execute(self, sql: str, params: tuple = ()) -> FakeResult:
        self.calls.append((sql, tuple(params) if params else ()))
        lookup = lookup_rows(sql)
        if lookup is not None:
            return FakeResult(rows=lookup)
        normalized = " ".join(sql.strip().split())

        if "SELECT 1 FROM products WHERE id" in normalized:
            prod_id = params[0]
            if prod_id in self.products:
                return FakeResult(row={"1": 1})
            return FakeResult(row=None)

        if "SELECT 1 FROM users WHERE id" in normalized:
            user_id = params[0]
            if user_id in self.users:
                return FakeResult(row={"1": 1})
            return FakeResult(row=None)

        if "SELECT id FROM facts" in normalized:
            return FakeResult(rows=[{"id": fid} for fid in self.existing_facts])

        if "SELECT id FROM guidelines" in normalized:
            return FakeResult(rows=[{"id": gid} for gid in self.existing_guidelines])

        if "SELECT id FROM glossary" in normalized:
            return FakeResult(rows=[{"id": glid} for glid in self.existing_glossary])

        if "INSERT INTO facts" in normalized:
            return FakeResult(
                row={
                    "id": params[0],
                    "product_id": params[1],
                    "title": params[2],
                    "statement": params[3],
                    "fact_type": params[4],
                    "structured_value": getattr(params[5], "obj", params[5]),
                    "match_keywords": params[6],
                    "severity_on_change": params[8],
                    "owner_id": params[9],
                    "version": 1,
                    "valid_from": params[10],
                    "valid_until": params[11],
                    "status": params[12],
                    "category": params[13],
                    "updated_at": "2026-10-27T00:00:00Z",
                }
            )

        if "INSERT INTO guidelines" in normalized:
            return FakeResult(
                row={
                    "id": params[0],
                    "short_name": params[1],
                    "title": params[2],
                    "text": params[3],
                    "category": params[4],
                    "rule_type": params[5],
                    "severity": params[6],
                    "applies_to_channels": params[7],
                    "required_text": params[8],
                    "version": 1,
                    "owner_id": params[9],
                    "is_active": True,
                    "updated_at": "2026-10-27T00:00:00Z",
                }
            )

        if "INSERT INTO glossary" in normalized:
            return FakeResult(
                row={
                    "id": params[0],
                    "approved_term": params[1],
                    "avoid_terms": params[2],
                    "kind": params[3],
                    "explanation": params[4],
                    "is_active": True,
                }
            )

        return FakeResult()

    def transaction(self) -> FakeTransaction:
        return FakeTransaction()


def make_client(role: str = "manager", conn: FakeConn | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    active_conn = conn if conn is not None else FakeConn()
    app.dependency_overrides[get_conn] = lambda: active_conn
    app.dependency_overrides[current_user] = lambda: {
        "id": f"user-{role}",
        "name": f"Test {role.capitalize()}",
        "role": role,
    }
    return TestClient(app)


# -----------------------------------------------------------------------------
# 1. Pure ID helper unit tests
# -----------------------------------------------------------------------------
def test_pure_id_helper_empty_table_gives_f001():
    assert generate_next_id("F-", []) == "F-001"
    assert next_id("F-", []) == "F-001"


def test_pure_id_helper_existing_f009_gives_f010():
    assert generate_next_id("F-", ["F-009"]) == "F-010"


def test_pure_id_helper_gaps_are_not_reused():
    # Gap between 1 and 9: next is 10, not 2
    assert generate_next_id("F-", ["F-001", "F-009"]) == "F-010"
    assert generate_next_id("F-", ["F-003", "F-007"]) == "F-008"


def test_pure_id_helper_guideline_and_glossary_prefixes():
    assert generate_next_id("G-", []) == "G-001"
    assert generate_next_id("G-", ["G-015"]) == "G-016"
    assert generate_next_id("GL-", []) == "GL-001"
    assert generate_next_id("GL-", ["GL-004"]) == "GL-005"


# -----------------------------------------------------------------------------
# 2. Status derivation unit tests
# -----------------------------------------------------------------------------
def test_status_derivation_expired():
    ref = date(2026, 6, 1)
    expired_date = ref - timedelta(days=1)
    assert derive_fact_status(expired_date, today=ref) == "Expired"


def test_status_derivation_expiring_within_90_days():
    ref = date(2026, 6, 1)
    expiring_date = ref + timedelta(days=45)
    assert derive_fact_status(expiring_date, today=ref) == "Expiring soon"
    # Same day as today
    assert derive_fact_status(ref, today=ref) == "Expiring soon"


def test_status_derivation_boundary_on_exactly_90_days():
    ref = date(2026, 6, 1)
    boundary_90 = ref + timedelta(days=EXPIRING_SOON_DAYS)
    assert derive_fact_status(boundary_90, today=ref) == "Expiring soon"


def test_status_derivation_active_beyond_90_days_or_none():
    ref = date(2026, 6, 1)
    active_date = ref + timedelta(days=EXPIRING_SOON_DAYS + 1)
    assert derive_fact_status(active_date, today=ref) == "Active"
    assert derive_fact_status(None, today=ref) == "Active"


# -----------------------------------------------------------------------------
# 3. Pydantic validation unit tests
# -----------------------------------------------------------------------------
def test_pydantic_validation_bad_fact_type():
    with pytest.raises(ValidationError):
        FactCreate(
            title="Valid Title",
            statement="Valid statement",
            fact_type="not_a_real_type",  # type: ignore[arg-type]
        )


def test_pydantic_validation_valid_until_before_valid_from():
    with pytest.raises(ValidationError) as exc_info:
        FactCreate(
            title="Valid Title",
            statement="Valid statement",
            fact_type="claim",
            valid_from=date(2026, 6, 10),
            valid_until=date(2026, 6, 9),
        )
    assert "valid_until must be >= valid_from" in str(exc_info.value)


def test_pydantic_validation_empty_statement():
    with pytest.raises(ValidationError):
        FactCreate(
            title="Valid Title",
            statement="",
            fact_type="claim",
        )


def test_pydantic_validation_guideline_text_over_20000_chars():
    with pytest.raises(ValidationError):
        GuidelineCreate(
            short_name="Short",
            title="Title",
            text="a" * 20001,
            category="Terminology",
        )


def test_unknown_channel_is_rejected_using_the_database_list():
    client = make_client(role="manager")
    res = client.post("/api/knowledge/guidelines", json={
        "short_name": "Short", "title": "Title", "text": "Valid guideline text",
        "category": "Terminology", "applies_to_channels": ["TikTok"],
    })
    assert res.status_code == 422
    assert "TikTok" in res.json()["detail"]


def test_unknown_category_is_rejected_using_the_database_list():
    client = make_client(role="manager")
    res = client.post("/api/knowledge/guidelines", json={
        "short_name": "Short", "title": "Title", "text": "Valid guideline text",
        "category": "Billboards",
    })
    assert res.status_code == 422
    assert "Billboards" in res.json()["detail"]


def test_pydantic_validation_status_contradicting_dates():
    # If valid_until was in the past, client cannot claim "Active"
    with pytest.raises(ValidationError):
        FactCreate(
            title="Title",
            statement="Statement",
            fact_type="claim",
            valid_from=date.today() - timedelta(days=20),
            valid_until=date.today() - timedelta(days=5),
            status="Active",
        )


# -----------------------------------------------------------------------------
# 4. Upload route tests
# -----------------------------------------------------------------------------
def test_upload_unsupported_extension_gives_415():
    client = make_client(role="manager")
    res = client.post(
        "/api/knowledge/guidelines/upload",
        files={"file": ("guideline.exe", b"MZ...", "application/octet-stream")},
        data={"category": "Brand Assets"},
    )
    assert res.status_code == 415


def test_upload_pdf_that_is_not_really_a_pdf_gives_422():
    client = make_client(role="manager")
    res = client.post(
        "/api/knowledge/guidelines/upload",
        files={"file": ("guideline.pdf", b"not a pdf", "application/pdf")},
        data={"category": "Brand Assets"},
    )
    assert res.status_code == 422


def test_upload_empty_file_gives_422():
    client = make_client(role="manager")
    res = client.post(
        "/api/knowledge/guidelines/upload",
        files={"file": ("empty.txt", b"   \n  ", "text/plain")},
        data={"category": "Brand Assets"},
    )
    assert res.status_code == 422


def test_upload_invalid_utf8_gives_422():
    client = make_client(role="manager")
    res = client.post(
        "/api/knowledge/guidelines/upload",
        files={"file": ("invalid.txt", b"\xff\xfe\x00\x00", "text/plain")},
        data={"category": "Brand Assets"},
    )
    assert res.status_code == 422


def test_upload_file_over_1mb_gives_413():
    client = make_client(role="manager")
    huge_content = b"a" * (1024 * 1024 + 1)
    res = client.post(
        "/api/knowledge/guidelines/upload",
        files={"file": ("large.md", huge_content, "text/markdown")},
        data={"category": "Formatting"},
    )
    assert res.status_code == 413


def test_upload_valid_md_file_succeeds():
    conn = FakeConn(existing_guidelines=["G-001", "G-002"])
    client = make_client(role="manager", conn=conn)

    content = b"# Tone Guidelines\nAlways use clear and friendly language."
    res = client.post(
        "/api/knowledge/guidelines/upload",
        files={"file": ("tone_guide.md", content, "text/markdown")},
        data={
            "category": "Tone of Voice",
            "severity": "info",
            "applies_to_channels": "Website, Instagram",
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["id"] == "G-003"
    assert data["title"] == "tone_guide"
    assert data["shortName"] == "tone_guide"
    assert data["category"] == "Tone of Voice"
    assert data["severity"] == "info"
    assert data["appliesToChannels"] == ["Website", "Instagram"]
    assert "Always use clear and friendly language." in data["text"]
    assert data["version"] == 1
    assert data["isActive"] is True

    # Check locking and versions insert in DB calls
    sql_statements = [sql for sql, _ in conn.calls]
    assert any("LOCK TABLE guidelines IN EXCLUSIVE MODE" in s for s in sql_statements)
    assert any("INSERT INTO guideline_versions" in s for s in sql_statements)


# -----------------------------------------------------------------------------
# 5. Role check tests: creator role gets 403, manager is allowed
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "method,path,kwargs",
    [
        (
            "post",
            "/api/knowledge/facts",
            {
                "json": {
                    "title": "Title",
                    "statement": "Statement",
                    "fact_type": "claim",
                }
            },
        ),
        (
            "post",
            "/api/knowledge/guidelines",
            {
                "json": {
                    "short_name": "Short",
                    "title": "Title",
                    "text": "Guideline text",
                    "category": "Claims & Legal",
                }
            },
        ),
        (
            "post",
            "/api/knowledge/guidelines/upload",
            {
                "files": {"file": ("test.txt", b"Valid text", "text/plain")},
                "data": {"category": "Claims & Legal"},
            },
        ),
        (
            "post",
            "/api/knowledge/glossary",
            {
                "json": {
                    "approved_term": "GreenGlow",
                    "kind": "term",
                }
            },
        ),
    ],
)
def test_role_check_creator_gets_403(method: str, path: str, kwargs: dict[str, Any]):
    client = make_client(role="creator")
    caller = getattr(client, method)
    res = caller(path, **kwargs)
    assert res.status_code == 403


@pytest.mark.parametrize(
    "method,path,kwargs",
    [
        (
            "post",
            "/api/knowledge/facts",
            {
                "json": {
                    "title": "Title",
                    "statement": "Statement",
                    "fact_type": "claim",
                }
            },
        ),
        (
            "post",
            "/api/knowledge/guidelines",
            {
                "json": {
                    "short_name": "Short",
                    "title": "Title",
                    "text": "Guideline text",
                    "category": "Claims & Legal",
                }
            },
        ),
        (
            "post",
            "/api/knowledge/guidelines/upload",
            {
                "files": {"file": ("test.txt", b"Valid text", "text/plain")},
                "data": {"category": "Claims & Legal"},
            },
        ),
        (
            "post",
            "/api/knowledge/glossary",
            {
                "json": {
                    "approved_term": "GreenGlow",
                    "kind": "term",
                }
            },
        ),
    ],
)
def test_role_check_manager_allowed(method: str, path: str, kwargs: dict[str, Any]):
    client = make_client(role="manager")
    caller = getattr(client, method)
    res = caller(path, **kwargs)
    assert res.status_code == 201


# -----------------------------------------------------------------------------
# 6. Additional route validations: product_id and owner_id checks
# -----------------------------------------------------------------------------
def test_create_fact_invalid_product_gives_404():
    conn = FakeConn(products={"P-001"})
    client = make_client(role="manager", conn=conn)
    res = client.post(
        "/api/knowledge/facts",
        json={
            "title": "Sunscreen Fact",
            "statement": "Statement",
            "fact_type": "spec",
            "product_id": "P-999",
        },
    )
    assert res.status_code == 404
    assert "Product 'P-999' not found" in res.json()["detail"]


def test_create_fact_invalid_owner_gives_404():
    conn = FakeConn(users={"user-manager"})
    client = make_client(role="manager", conn=conn)
    res = client.post(
        "/api/knowledge/facts",
        json={
            "title": "Fact",
            "statement": "Statement",
            "fact_type": "spec",
            "owner_id": "user-nonexistent",
        },
    )
    assert res.status_code == 404
    assert "User 'user-nonexistent' not found" in res.json()["detail"]


def test_create_fact_success_inserts_fact_and_version():
    conn = FakeConn(existing_facts=["F-001", "F-002"])
    client = make_client(role="manager", conn=conn)
    res = client.post(
        "/api/knowledge/facts",
        json={
            "title": "SPF 50 claim",
            "statement": "Provides broad spectrum UVA/UVB protection.",
            "fact_type": "claim",
            "product_id": "P-001",
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["id"] == "F-003"
    assert data["version"] == 1
    assert data["status"] == "Active"

    sql_statements = [sql for sql, _ in conn.calls]
    assert any("LOCK TABLE facts IN EXCLUSIVE MODE" in s for s in sql_statements)
    assert any("INSERT INTO fact_versions" in s for s in sql_statements)

