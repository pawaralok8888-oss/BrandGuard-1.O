"""PostgreSQL coverage for the Phase 1 migration and seed."""
from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.sql import SQL, Identifier

ROOT = Path(__file__).resolve().parents[2]
MIGRATION_FILE = ROOT / "database" / "migrations" / "20261030_phase1_inputs.sql"
SEED_FILE = ROOT / "data" / "seeds" / "05_phase1_inputs.sql"
DATABASE_URL = os.getenv("DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL is unset")


def _database_name(conninfo: str) -> str:
    return conninfo_to_dict(conninfo).get("dbname", "")


def _connect_test_database(conninfo: str) -> psycopg.Connection:
    database_name = _database_name(conninfo)
    if database_name == "brandguard":
        raise RuntimeError("Gate 1 tests refuse to connect to the brandguard database")
    if not database_name.startswith("brandguard_test_"):
        raise RuntimeError(f"Gate 1 test target is not a throwaway database: {database_name}")
    return psycopg.connect(conninfo, autocommit=True)


@contextmanager
def _throwaway_database() -> Iterator[tuple[str, str]]:
    assert DATABASE_URL is not None
    test_database = f"brandguard_test_{uuid.uuid4().hex}"
    if test_database == "brandguard":
        raise RuntimeError("Gate 1 tests refuse to target the brandguard database")

    admin_url = make_conninfo(DATABASE_URL, dbname="postgres")
    test_url = make_conninfo(DATABASE_URL, dbname=test_database)
    created = False

    try:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute(
                SQL("CREATE DATABASE {} TEMPLATE {}").format(
                    Identifier(test_database), Identifier("brandguard")
                )
            )
            created = True
        yield test_database, test_url
    finally:
        if created:
            with psycopg.connect(admin_url, autocommit=True) as admin:
                admin.execute(
                    SQL("DROP DATABASE {}").format(Identifier(test_database))
                )


def _apply_sql_file(conn: psycopg.Connection, path: Path) -> None:
    database_name = conn.execute("SELECT current_database()").fetchone()[0]
    if database_name == "brandguard":
        raise RuntimeError("Refusing to apply Gate 1 SQL to brandguard")
    conn.execute(path.read_text(encoding="utf-8"), prepare=False)


def _scalar(conn: psycopg.Connection, query: str) -> int:
    return conn.execute(query).fetchone()[0]


def _assert_unique_rows(conn: psycopg.Connection) -> None:
    assert _scalar(conn, "SELECT count(*) FROM intake_fields") == _scalar(
        conn,
        """
        SELECT count(DISTINCT (spec_key, spec_version, category_key, field_key))
        FROM intake_fields
        """,
    )
    assert _scalar(conn, "SELECT count(*) FROM guideline_categories") == _scalar(
        conn, "SELECT count(DISTINCT category_key) FROM guideline_categories"
    )
    assert _scalar(conn, "SELECT count(*) FROM intake_categories") == _scalar(
        conn,
        """
        SELECT count(DISTINCT (spec_key, spec_version, category_key))
        FROM intake_categories
        """,
    )
    assert _scalar(conn, "SELECT count(*) FROM guideline_test_cases") == _scalar(
        conn, "SELECT count(DISTINCT case_id) FROM guideline_test_cases"
    )
    assert _scalar(conn, "SELECT count(*) FROM reference_documents") == _scalar(
        conn, "SELECT count(DISTINCT document_key) FROM reference_documents"
    )


def test_migration_preserves_guidelines_and_existing_content_on_upgrade_copy() -> None:
    with _throwaway_database() as (database_name, test_url):
        assert database_name.startswith("brandguard_test_")
        print(f"upgrade database: {database_name}")
        with _connect_test_database(test_url) as upgrade:
            guidelines_before = upgrade.execute(
                "SELECT to_jsonb(g) FROM guidelines AS g ORDER BY id"
            ).fetchall()
            content_before = upgrade.execute(
                "SELECT to_jsonb(c) - 'asset_type' FROM content AS c ORDER BY id"
            ).fetchall()
            assert len(guidelines_before) == 17

            _apply_sql_file(upgrade, MIGRATION_FILE)

            guidelines_after = upgrade.execute(
                "SELECT to_jsonb(g) FROM guidelines AS g ORDER BY id"
            ).fetchall()
            content_after = upgrade.execute(
                "SELECT to_jsonb(c) - 'asset_type' FROM content AS c ORDER BY id"
            ).fetchall()
            assert guidelines_after == guidelines_before
            assert content_after == content_before
            assert _scalar(upgrade, "SELECT count(*) FROM guidelines") == 17
            assert _scalar(
                upgrade,
                "SELECT count(*) FROM content WHERE asset_type <> 'social_post'",
            ) == 0


def test_migration_and_seed_are_repeatable_on_throwaway_database() -> None:
    with _throwaway_database() as (database_name, test_url):
        assert database_name.startswith("brandguard_test_")
        print(f"migration database: {database_name}")
        with _connect_test_database(test_url) as conn:
            for _ in range(2):
                _apply_sql_file(conn, MIGRATION_FILE)
                _apply_sql_file(conn, SEED_FILE)

            assert _scalar(conn, "SELECT count(*) FROM guidelines") == 17
            assert _scalar(conn, "SELECT count(*) FROM guideline_categories") == 7
            assert _scalar(conn, "SELECT count(*) FROM intake_fields") == 38
            assert _scalar(conn, "SELECT count(*) FROM content") == 8
            assert _scalar(
                conn,
                "SELECT count(*) FROM content WHERE asset_type <> 'social_post'",
            ) == 0
            _assert_unique_rows(conn)


def test_seed_is_repeatable_with_expected_counts_on_throwaway_database() -> None:
    with _throwaway_database() as (database_name, test_url):
        assert database_name.startswith("brandguard_test_")
        print(f"seed database: {database_name}")
        with _connect_test_database(test_url) as conn:
            _apply_sql_file(conn, MIGRATION_FILE)
            _apply_sql_file(conn, SEED_FILE)
            _apply_sql_file(conn, SEED_FILE)

            assert _scalar(conn, "SELECT count(*) FROM guideline_categories") == 7
            assert _scalar(conn, "SELECT count(*) FROM intake_fields") == 38
            assert _scalar(
                conn,
                """
                SELECT count(*) FROM guideline_categories
                WHERE source_file <> 'intake_requirements.json'
                """,
            ) == 0
            assert _scalar(
                conn,
                """
                SELECT count(*) FROM intake_specs
                WHERE source_file <> 'intake_requirements.json'
                """,
            ) == 0
            _assert_unique_rows(conn)
