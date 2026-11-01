import type { GuidelineInsight } from "@/types";

// Set to false once the /api/intake/insights endpoint returns data for this branch.
export const USE_MOCK_INSIGHTS = true;

export const MOCK_APPROVED_INSIGHTS: GuidelineInsight[] = [
  {
    id: "INS-001",
    fieldId: "IF-008",
    fieldLabel: "Tone of voice",
    categoryId: "voice_and_terms",
    value: "Warm, plain, and confident. Avoid jargon and exclamation marks.",
    evidence: "We speak like a knowledgeable friend, never a salesperson.",
    confidence: 0.86,
    status: "approved",
    documentId: "DOC-001",
    reviewedBy: "Jordan Lee",
    reviewedAt: "2026-11-02T11:00:00Z",
  },
];

export const MOCK_DRAFT_INSIGHTS: GuidelineInsight[] = [
  {
    id: "INS-002",
    fieldId: "IF-011",
    fieldLabel: "Required disclaimer",
    categoryId: "claims_and_legal",
    value: "Results may vary. Include the results disclaimer on all paid channels.",
    evidence: "Results may vary from person to person.",
    confidence: 0.72,
    status: "draft",
    documentId: "DOC-002",
    reviewedBy: null,
    reviewedAt: null,
  },
];