import { apiRequest } from "./client";

export type BrandRuleKind = "phrase" | "regex" | "name_variant" | "required_text";
export type BrandRuleStatus = "draft" | "approved" | "retired";
export type BrandRuleSeverity = "critical" | "warning" | "info";
export type BrandRuleChannel = "Website" | "Instagram" | "Email" | "Ad";

export interface BrandRule {
  id: string;
  title: string;
  kind: BrandRuleKind;
  pattern: string;
  replacement: string;
  reason: string;
  channel: BrandRuleChannel | null;
  severity: BrandRuleSeverity;
  status: BrandRuleStatus;
  createdBy: string;
  approvedBy: string | null;
  approvedAt: string | null;
  retiredAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface BrandRuleInput {
  title: string;
  kind: BrandRuleKind;
  pattern: string;
  replacement?: string;
  reason?: string;
  channel?: BrandRuleChannel | null;
  severity?: BrandRuleSeverity;
}

export type BrandRulePatch = Partial<Omit<BrandRuleInput, "kind">>;

export const listBrandRules = (status?: BrandRuleStatus): Promise<BrandRule[]> =>
  apiRequest<BrandRule[]>(`/api/brand-rules${status ? `?status=${status}` : ""}`);

export const createBrandRule = (input: BrandRuleInput): Promise<BrandRule> =>
  apiRequest<BrandRule>("/api/brand-rules", { method: "POST", body: JSON.stringify(input) });

export const updateBrandRule = (id: string, patch: BrandRulePatch): Promise<BrandRule> =>
  apiRequest<BrandRule>(`/api/brand-rules/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });

export const approveBrandRule = (id: string): Promise<BrandRule> =>
  apiRequest<BrandRule>(`/api/brand-rules/${encodeURIComponent(id)}/approve`, { method: "POST" });

export const retireBrandRule = (id: string): Promise<BrandRule> =>
  apiRequest<BrandRule>(`/api/brand-rules/${encodeURIComponent(id)}/retire`, { method: "POST" });
