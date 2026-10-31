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
