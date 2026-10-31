"""Answers for the category and channel lookups, shared by the fake connections in the tests.

These match the seed rows in data/migrations/005_categories_channels_logo.sql.
"""
from __future__ import annotations

CATEGORY_IDS = [
    "Terminology", "Claims & Legal", "Tone of Voice", "Formatting",
    "Accessibility", "Brand Assets", "Security",
]
CHANNEL_IDS = ["Website", "Instagram", "Email", "Ad"]


def lookup_rows(sql: str) -> list[dict] | None:
    """Rows for a category or channel lookup, or None if the query is something else."""
    normalized = " ".join(sql.split())
    if "FROM guideline_categories" in normalized:
        return [{"id": c} for c in CATEGORY_IDS]
    if "FROM channels" in normalized:
        return [{"id": c} for c in CHANNEL_IDS]
    return None
