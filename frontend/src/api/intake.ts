import { apiRequest } from "./client";

export type IntakeFieldStatus = "covered" | "provided" | "not_applicable" | "gap";

export interface IntakeField {
  id: string;
  label: string;
  description: string;
  required: boolean;
  coverageCheck: string;
  status: IntakeFieldStatus;
  note: string;
  approvedInsightCount?: number;
}

export interface IntakeCategory {
  id: string;
  label: string;
  fields: IntakeField[];
}

export interface GapReport {
  summary: {
    total: number;
    covered: number;
    provided: number;
    notApplicable: number;
    gaps: number;
    requiredGaps: number;
  };
  categories: IntakeCategory[];
}

export type IntakeDocumentStatus = "processing" | "ready" | "failed";

export interface IntakeDocument {
  id: string;
  filename: string;
  sizeBytes: number;
  status: IntakeDocumentStatus;
  uploadedBy: string | null;
  uploadedAt: string;
  insightCount?: number;
  errorMessage: string;
}

export interface IntakeDocumentDetail extends IntakeDocument {
  extractedText: string;
  insights: GuidelineInsight[];
}

export type InsightStatus = "draft" | "approved" | "rejected";

export interface GuidelineInsight {
  id: string;
  fieldId: string;
  fieldLabel: string;
  categoryId: string;
  value: string;
  evidence: string;
  confidence: number;
  status: InsightStatus;
  documentId: string;
  reviewedBy: string | null;
  reviewedAt: string | null;
}

export interface IntakeCategoryWithDocuments extends IntakeCategory {
  documents?: IntakeDocument[];
}

export const getGapReport = (): Promise<GapReport> =>
  apiRequest<GapReport>("/api/intake/gap-report");

/** Mark a field provided or not applicable, or pass null to clear the mark. */
export const setIntakeResponse = (
  fieldId: string,
  response: { status: "provided" | "not_applicable" | null; note?: string },
): Promise<{ fieldId: string; status: string | null; note: string }> =>
  apiRequest(`/api/intake/fields/${encodeURIComponent(fieldId)}`, {
    method: "PATCH",
    body: JSON.stringify({ status: response.status, note: response.note ?? "" }),
  });

export const getIntakeCategories = (): Promise<IntakeCategoryWithDocuments[]> =>
  apiRequest<IntakeCategoryWithDocuments[]>("/api/intake/categories");

export const listCategoryDocuments = (categoryId: string): Promise<IntakeDocument[]> =>
  apiRequest<IntakeDocument[]>(
    `/api/intake/categories/${encodeURIComponent(categoryId)}/documents`,
  );

export const getDocument = (docId: string): Promise<IntakeDocumentDetail> =>
  apiRequest<IntakeDocumentDetail>(`/api/intake/documents/${encodeURIComponent(docId)}`);

/**
 * Upload a PDF or DOCX to a category. Do not set Content-Type here:
 * the browser sets it with the multipart boundary.
 */
export const uploadIntakeDocument = (categoryId: string, file: File): Promise<IntakeDocument> => {
  const form = new FormData();
  form.append("file", file);
  return apiRequest<IntakeDocument>(
    `/api/intake/categories/${encodeURIComponent(categoryId)}/documents`,
    { method: "POST", body: form },
  );
};

export const deleteIntakeDocument = (docId: string): Promise<void> =>
  apiRequest<void>(`/api/intake/documents/${encodeURIComponent(docId)}`, { method: "DELETE" });

export const reprocessDocument = (docId: string): Promise<IntakeDocument> =>
  apiRequest<IntakeDocument>(
    `/api/intake/documents/${encodeURIComponent(docId)}/reprocess`,
    { method: "POST" },
  );

export const listInsights = (params: {
  categoryId?: string;
  status?: InsightStatus | "approved";
}): Promise<GuidelineInsight[]> => {
  const query = new URLSearchParams();
  if (params.categoryId) query.set("categoryId", params.categoryId);
  if (params.status) query.set("status", params.status);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiRequest<GuidelineInsight[]>(`/api/intake/insights${suffix}`);
};

export const approveInsight = (insightId: string): Promise<GuidelineInsight> =>
  apiRequest<GuidelineInsight>(
    `/api/intake/insights/${encodeURIComponent(insightId)}/approve`,
    { method: "POST" },
  );

export const rejectInsight = (insightId: string): Promise<GuidelineInsight> =>
  apiRequest<GuidelineInsight>(
    `/api/intake/insights/${encodeURIComponent(insightId)}/reject`,
    { method: "POST" },
  );