"""Create embeddings for current facts and guidelines that have none. Safe to re-run.

Seeded rows and rows saved before embeddings existed have no vector. Run once after deploying:

    cd backend && DATABASE_URL=... GEMINI_API_KEY=... python scripts/backfill_embeddings.py

Items without a vector are still used as evidence, so running this only improves ranking.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.ai.embeddings import KIND_FACT, KIND_GUIDELINE, index_item  # noqa: E402
from app.db import create_pool  # noqa: E402


def main() -> int:
    if not get_settings().gemini_api_key:
        print("GEMINI_API_KEY is not set in backend/.env, so no embeddings were created.")
        print("Add the key, then run this script again. The app works without it: checks use rules only.")
        return 2
    pool = create_pool()
    pool.open(wait=True)
    stored = skipped = failed = 0
    try:
        with pool.connection() as conn:
            existing = {
                (r["kind"], r["source_id"], r["version"])
                for r in conn.execute("SELECT kind, source_id, version FROM embeddings").fetchall()
            }
            work = [
                (KIND_FACT, r["id"], r["version"], r["statement"])
                for r in conn.execute("SELECT id, version, statement FROM facts").fetchall()
            ] + [
                (KIND_GUIDELINE, r["id"], r["version"], r["text"])
                for r in conn.execute("SELECT id, version, text FROM guidelines").fetchall()
            ]
            for kind, source_id, version, text in work:
                if (kind, source_id, version) in existing:
                    skipped += 1
                elif index_item(conn, kind, source_id, version, text):
                    stored += 1
                else:
                    failed += 1
    finally:
        pool.close()
    print(f"embeddings stored={stored} already_present={skipped} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
