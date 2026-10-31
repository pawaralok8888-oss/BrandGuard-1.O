"""Brand intake gap report.

Each intake field names a coverage check. The check counts the real data that answers the
field (approved assets, products, active facts, active guidelines, rules). A person can also
mark a field provided or not applicable, with a note.

Status of a field, in this order:
  not_applicable  a person marked it not applicable
  provided        a person marked it provided (the only way to answer a manual field)
  covered         the coverage check found data
  gap             none of the above

A required field with status gap is a required gap. Optional gaps are reported, not counted as failures.
"""
from __future__ import annotations

from psycopg import Connection

ACTIVE_FACT_STATUSES = ["Active", "Expiring soon"]
MANUAL = "manual"

# Coverage check -> SQL that returns the count of data that answers it.
COVERAGE_SQL: dict[str, str] = {
    "logo": "SELECT COUNT(*) AS n FROM assets WHERE asset_type = 'logo' AND status = 'approved'",
    "colour_palette": "SELECT COUNT(*) AS n FROM assets WHERE asset_type = 'colour' AND status = 'approved'",
    "fonts": "SELECT COUNT(*) AS n FROM assets WHERE asset_type = 'font' AND status = 'approved'",
    "product_list": "SELECT COUNT(*) AS n FROM products",
    "certifications": (
        "SELECT COUNT(*) AS n FROM facts WHERE fact_type = 'certification' "
        "AND status = ANY(ARRAY['Active','Expiring soon'])"
    ),
    "offers": (
        "SELECT COUNT(*) AS n FROM facts WHERE fact_type IN ('price','offer') "
        "AND status = ANY(ARRAY['Active','Expiring soon'])"
    ),
    "tone_guideline": "SELECT COUNT(*) AS n FROM guidelines WHERE category = 'Tone of Voice' AND is_active = TRUE",
    "terminology_guideline": "SELECT COUNT(*) AS n FROM guidelines WHERE category = 'Terminology' AND is_active = TRUE",
    "claims_guideline": "SELECT COUNT(*) AS n FROM guidelines WHERE category = 'Claims & Legal' AND is_active = TRUE",
    "accessibility_guideline": "SELECT COUNT(*) AS n FROM guidelines WHERE category = 'Accessibility' AND is_active = TRUE",
    "brand_assets_guideline": "SELECT COUNT(*) AS n FROM guidelines WHERE category = 'Brand Assets' AND is_active = TRUE",
    "prohibited_terms": (
        "SELECT (SELECT COUNT(*) FROM rule_patterns WHERE kind = 'phrase' AND is_active = TRUE)"
        " + (SELECT COUNT(*) FROM brand_rules WHERE kind = 'phrase' AND status = 'approved') AS n"
    ),
    "disclaimers": (
        "SELECT (SELECT COUNT(*) FROM rule_patterns WHERE kind = 'required_text' AND is_active = TRUE)"
        " + (SELECT COUNT(*) FROM brand_rules WHERE kind = 'required_text' AND status = 'approved') AS n"
    ),
    "confidential_terms": (
        "SELECT COUNT(*) AS n FROM rule_patterns WHERE kind = 'confidential_term' AND is_active = TRUE"
    ),
}


def field_status(coverage_check: str, data_found: bool, response_status: str | None) -> str:
    if response_status == "not_applicable":
        return "not_applicable"
    if response_status == "provided":
        return "provided"
    if coverage_check != MANUAL and data_found:
        return "covered"
    return "gap"


def build_gap_report(rows: list[dict], counts: dict[str, int]) -> dict:
    """Pure: field rows (from the join in load_gap_report) and coverage counts -> report."""
    categories: dict[str, dict] = {}
    summary = {"total": 0, "covered": 0, "provided": 0, "notApplicable": 0, "gaps": 0, "requiredGaps": 0}

    for row in rows:
        data_found = counts.get(row["coverage_check"], 0) > 0
        status = field_status(row["coverage_check"], data_found, row["response_status"])

        category = categories.setdefault(row["category_id"], {
            "id": row["category_id"],
            "label": row["category_label"],
            "fields": [],
        })
        category["fields"].append({
            "id": row["id"],
            "label": row["label"],
            "description": row["description"],
            "required": row["required"],
            "coverageCheck": row["coverage_check"],
            "status": status,
            "note": row["response_note"] or "",
        })

        summary["total"] += 1
        if status == "covered":
            summary["covered"] += 1
        elif status == "provided":
            summary["provided"] += 1
        elif status == "not_applicable":
            summary["notApplicable"] += 1
        else:
            summary["gaps"] += 1
            if row["required"]:
                summary["requiredGaps"] += 1

    return {"summary": summary, "categories": list(categories.values())}


FIELD_QUERY = """
    SELECT c.id AS category_id, c.label AS category_label,
           f.id, f.label, f.description, f.required, f.coverage_check,
           r.status AS response_status, r.note AS response_note
    FROM intake_fields f
    JOIN intake_categories c ON c.id = f.category_id
    LEFT JOIN intake_responses r ON r.field_id = f.id
    ORDER BY c.sort_order, c.id, f.sort_order, f.id
"""


def load_gap_report(conn: Connection) -> dict:
    rows = conn.execute(FIELD_QUERY).fetchall()
    counts: dict[str, int] = {}
    for check in {r["coverage_check"] for r in rows if r["coverage_check"] != MANUAL}:
        counts[check] = int(conn.execute(COVERAGE_SQL[check]).fetchone()["n"])
    return build_gap_report(rows, counts)
