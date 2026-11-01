"""Pydantic shape of the vision model's reply (phase2_contract.md section 6).

Validation is deliberately lenient. One odd field must not throw away a whole reply,
because services/vision_safeguards.py decides what is kept. So: unknown extra keys are
ignored, and numbers are not range-checked here (the safeguards clamp them).
Required structure is still enforced: "facts", "findings" and "notFound" must be lists.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class _Lenient(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class VisionFact(_Lenient):
    id: str
    kind: str = "other"
    value: str = ""
    bbox: Optional[list[Any]] = None
    confidence: Any = 0.0


class VisionFinding(_Lenient):
    factIds: list[str] = Field(default_factory=list)
    type: str = ""
    severity: str = "warning"
    title: str = ""
    quote: str = ""
    reason: str = ""
    guidelineId: str = ""
    suggestedFix: str = ""
    confidence: Any = 0.0


class VisionOutput(_Lenient):
    facts: list[VisionFact] = Field(default_factory=list)
    findings: list[VisionFinding] = Field(default_factory=list)
    notFound: list[str] = Field(default_factory=list)
