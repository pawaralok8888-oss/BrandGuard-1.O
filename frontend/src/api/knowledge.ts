import { apiRequest } from "./client";

export type FactStatus = "Active" | "Expiring soon" | "Expired";
export type FactSeverity = "High" | "Medium";

export interface ProductItem {
  id: string;
  name: string;
  line: string;
  status: "Active" | "Inactive";
}

export interface FactItem {
  id: string;
  productId: string | null;
  title: string;
  statement: string;
  factType: string;
  structuredValue: Record<string, unknown>;
  matchKeywords?: string[];
  severityOnChange: FactSeverity;
  ownerId: string | null;
  version: number;
  validFrom: string;
  validUntil: string | null;
  status: FactStatus;
  category: string;
  createdAt?: string;
  updatedAt: string;
}

// Alias so code written against develop's FactRecord name still compiles.
export type FactRecord = FactItem;

export interface FactHistoryItem {
  factId?: string;
  version: number;
  statement: string;
  structuredValue?: Record<string, unknown>;
  note: string | null;
  owner: string;
  changedBy: string | null;
  changedAt: string;
  validFrom: string;
  validUntil: string | null;
}

export interface GuidelineItem {
  id: string;
  shortName: string;
  title: string;
  text: string;
  category: string;
  ruleType: string;
  severity: "critical" | "warning" | "info";
  appliesToChannels: string[];
  requiredText: string | null;
  version: number;
  ownerId: string | null;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface GuidelineVersionItem {
  guidelineId: string;
  version: number;
  text: string;
  changedBy: string | null;
  changedByName: string | null;
  changeNote: string;
  changedAt: string;
}

export interface GlossaryItem {
  id: string;
  approvedTerm: string;
  avoidTerms: string[];
  kind: "term" | "product_name";
  explanation: string;
  isActive: boolean;
  createdAt: string;
}

/** Category names come from the server (GET /api/knowledge/categories). */
export type GuidelineCategoryName = string;

export const getGuidelineCategories = (): Promise<string[]> =>
  apiRequest<string[]>("/api/knowledge/categories");

export const getChannels = (): Promise<string[]> =>
  apiRequest<string[]>("/api/knowledge/channels");

/** Delete a draft rule. The server refuses if the rule is still switched on. */
export const deleteRulePattern = (id: string): Promise<void> =>
  apiRequest<void>(`/api/knowledge/rule-patterns/${encodeURIComponent(id)}`, { method: "DELETE" });

/** A rule drafted from an uploaded guideline. It affects checks only once a manager approves it. */
export interface RulePatternItem {
  id: string;
  guidelineId: string | null;
  kind: "phrase" | "regex" | "name_variant" | "confidential_term" | "required_text";
  pattern: string;
  replacement: string;
  note: string;
  channel: string | null;
  isActive: boolean;
}

export interface UploadedGuideline extends GuidelineItem {
  ruleCandidates: number;
  unparsedLines: string[];
}

export async function getProducts(): Promise<ProductItem[]> {
  return apiRequest<ProductItem[]>("/api/knowledge/products");
}

export async function getFacts(): Promise<FactItem[]> {
  return apiRequest<FactItem[]>("/api/knowledge/facts");
}

export async function getFactHistory(factId: string): Promise<FactHistoryItem[]> {
  return apiRequest<FactHistoryItem[]>(`/api/knowledge/facts/${factId}/history`);
}

export async function getGuidelines(): Promise<GuidelineItem[]> {
  return apiRequest<GuidelineItem[]>("/api/knowledge/guidelines");
}

export async function getGuidelineVersions(guidelineId: string): Promise<GuidelineVersionItem[]> {
  return apiRequest<GuidelineVersionItem[]>(`/api/knowledge/guidelines/${guidelineId}/versions`);
}

export async function getGlossary(): Promise<GlossaryItem[]> {
  return apiRequest<GlossaryItem[]>("/api/knowledge/glossary");
}

export async function uploadGuidelinesFile(
  file: File,
  category: GuidelineCategoryName = "Tone of Voice",
): Promise<UploadedGuideline> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("category", category);
  return apiRequest<UploadedGuideline>("/api/knowledge/guidelines/upload", {
    method: "POST",
    body: formData,
  });
}

export async function getRulePatterns(options: {
  guidelineId?: string;
  state?: "draft" | "active";
} = {}): Promise<RulePatternItem[]> {
  const params = new URLSearchParams();
  if (options.guidelineId) params.set("guideline_id", options.guidelineId);
  if (options.state) params.set("state", options.state);
  const query = params.toString();
  return apiRequest<RulePatternItem[]>(`/api/knowledge/rule-patterns${query ? `?${query}` : ""}`);
}

export interface RulePatternPatch {
  pattern?: string;
  replacement?: string;
  note?: string;
  is_active?: boolean;
}

export async function updateRulePattern(id: string, patch: RulePatternPatch): Promise<RulePatternItem> {
  return apiRequest<RulePatternItem>(`/api/knowledge/rule-patterns/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}