import type {
  GuidelineInsight,
  IntakeCategoryWithDocuments,
  IntakeDocument,
} from "../api/intake";

export const mockCategories: IntakeCategoryWithDocuments[] = [
  {
    id: "claims_and_legal",
    label: "Claims and legal",
    fields: [
      {
        id: "IF-010",
        label: "Certifications",
        description: "Approved certifications and their claim wording.",
        required: true,
        coverageCheck: "certification",
        status: "covered",
        note: "",
        approvedInsightCount: 1,
      },
      {
        id: "IF-011",
        label: "Legal disclaimers",
        description: "Required disclaimer text for promotional content.",
        required: false,
        coverageCheck: "manual",
        status: "gap",
        note: "",
        approvedInsightCount: 0,
      },
    ],
    documents: [],
  },
];

export const mockDocuments: IntakeDocument[] = [
  {
    id: "DOC-001",
    filename: "claims_guidelines_v2.pdf",
    sizeBytes: 412300,
    status: "ready",
    uploadedBy: "Jordan Lee",
    uploadedAt: "2026-11-02T10:14:00Z",
    insightCount: 2,
    errorMessage: "",
  },
  {
    id: "DOC-002",
    filename: "legal_terms_draft.docx",
    sizeBytes: 88211,
    status: "processing",
    uploadedBy: "Jordan Lee",
    uploadedAt: "2026-11-02T10:20:00Z",
    insightCount: 0,
    errorMessage: "",
  },
];

export const mockInsights: GuidelineInsight[] = [
  {
    id: "INS-001",
    fieldId: "IF-010",
    fieldLabel: "Certifications",
    categoryId: "claims_and_legal",
    value: "Certified by an independent lab for skin sensitivity.",
    evidence: "All products are independently certified for skin sensitivity.",
    confidence: 0.86,
    status: "approved",
    documentId: "DOC-001",
    reviewedBy: "Jordan Lee",
    reviewedAt: "2026-11-02T11:00:00Z",
  },
  {
    id: "INS-002",
    fieldId: "IF-011",
    fieldLabel: "Legal disclaimers",
    categoryId: "claims_and_legal",
    value: "Results may vary between individuals.",
    evidence: "Individual results may vary.",
    confidence: 0.62,
    status: "draft",
    documentId: "DOC-001",
    reviewedBy: null,
    reviewedAt: null,
  },
];