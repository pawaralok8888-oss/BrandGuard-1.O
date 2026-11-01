"""Scores a pipeline run against the labelled submissions (phase 2, plan section 12.2).

    python scripts/score_submissions.py ..\\tests\\quality\\submissions\\manifest.json results.json

results.json maps each submission id to its status and findings:
    {"S2": {"status": "ready", "findings": [{"guidelineId": "G-001", "title": "...", "reason": "...", "originalText": "..."}]}}

Measures:
- recall: expected problems found (same guideline id, and a mustMention phrase if one is given)
- precision: findings that match an expected problem, out of all findings
- hold accuracy: held when a hold is expected, and not held otherwise

Missing results count as no findings and no hold.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _matches(expected: dict, finding: dict) -> bool:
    if finding.get("guidelineId") != expected["guidelineId"]:
        return False
    must = [m.lower() for m in expected.get("mustMention", []) if m]
    if not must:
        return True
    text = " ".join(str(finding.get(k, "")) for k in ("title", "reason", "originalText")).lower()
    return any(m in text for m in must)


def score(manifest: dict, results: dict) -> dict:
    """Pure: manifest and results in, metrics out. Nothing is read from disk here."""
    per_kind: dict[str, dict] = {}
    holds = {"expected": 0, "correct": 0, "wrong": 0}
    missed: list[str] = []
    false_positive_examples: list[str] = []

    for sub in manifest["submissions"]:
        sid, kind = sub["id"], sub["kind"]
        run = results.get(sid, {})
        status = run.get("status", "")
        findings = run.get("findings", []) or []
        k = per_kind.setdefault(kind, {"expected": 0, "found": 0, "findings": 0, "false_positives": 0})

        held = status == "held"
        if sub["holdExpected"]:
            holds["expected"] += 1
            if held:
                holds["correct"] += 1
            else:
                holds["wrong"] += 1
                missed.append(f"{sid}: confidential submission was not held")
        elif held:
            holds["wrong"] += 1
            missed.append(f"{sid}: held, but no confidential term was expected")

        expected = sub.get("expected", [])
        k["expected"] += len(expected)
        for exp in expected:
            if any(_matches(exp, f) for f in findings):
                k["found"] += 1
            else:
                missed.append(f"{sid}: expected {exp['guidelineId']} not found")

        expected_ids = {e["guidelineId"] for e in expected}
        k["findings"] += len(findings)
        for f in findings:
            if f.get("guidelineId") in expected_ids and any(_matches(e, f) for e in expected):
                continue
            k["false_positives"] += 1
            if len(false_positive_examples) < 10:
                false_positive_examples.append(f"{sid}: {f.get('guidelineId', '?')} {f.get('title', '')}")

    total = {"expected": 0, "found": 0, "findings": 0, "false_positives": 0}
    for k in per_kind.values():
        for key in total:
            total[key] += k[key]

    def _pct(part: int, whole: int) -> float | None:
        return round(100.0 * part / whole, 1) if whole else None

    return {
        "recall_percent": _pct(total["found"], total["expected"]),
        "precision_percent": _pct(total["findings"] - total["false_positives"], total["findings"]),
        "false_positive_rate_percent": _pct(total["false_positives"], total["findings"]),
        "total": total,
        "by_kind": {
            kind: {
                "recall_percent": _pct(k["found"], k["expected"]),
                "precision_percent": _pct(k["findings"] - k["false_positives"], k["findings"]),
                **k,
            }
            for kind, k in sorted(per_kind.items())
        },
        "holds": holds,
        "missed": missed,
        "false_positive_examples": false_positive_examples,
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    manifest = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    results = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    report = score(manifest, results)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
