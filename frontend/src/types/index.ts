export type Finding = {
  id: string;
  contentId: string;
  type: "rule" | "claim" | "tone" | "image" | "accessibility" | "security";
  start: number | null;
  end: number | null;
  bbox: [number, number, number, number] | null;
  severity: "critical" | "warning" | "info";
  title: string;
  reason: string;
  sourceId: string;
  sourceVersion: number;
  originalText: string;
  suggestedFix: string;
  confidence: number;
  aiGenerated: boolean;
  needsHumanReview: boolean;
  status: "open" | "accepted" | "edited" | "rejected" | "resolved";
};

export type UserRole = "creator" | "manager" | "reviewer" | "admin";
export type ContentStatus = "Draft" | "Checked" | "Fixing" | "In Review" | "Changes requested" | "Approved" | "Published" | "Needs revalidation";

export type DemoUser = { id: string; name: string; initials: string; role: UserRole; title: string };
export type SourceVersion = { version: number; date: string; note: string; owner: string };
export type BrandSource = {
  id: string;
  title: string;
  category: "Guideline" | "Product fact" | "Disclaimer" | "Asset";
  version: number;
  updatedAt: string;
  owner: string;
  status: "Active" | "Needs review";
  excerpt: string;
  versionHistory?: SourceVersion[];
  expiryDate?: string;
  usedInCount?: number;
};
export type ContentItem = { id: string; title: string; channel: "Website" | "Instagram" | "Paid ad" | "Email"; owner: string; updatedAt: string; status: ContentStatus; findingCount: number; severity?: Finding["severity"] };
export type BrandAlert = { id: string; factId: string; title: string; oldValue: string; newValue: string; affectedCount: number; createdAt: string; status: "New" | "In progress" | "Resolved" };
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
