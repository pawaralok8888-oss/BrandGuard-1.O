// Phase 2 API types. Must match phase2_contract.md exactly.
// Functions that call the backend are added when the endpoints are merged.

import type { Finding } from "../types";

export type SubmissionKind = "post" | "script" | "marketing_idea" | "design" | "image";
export type SubmissionChannel = "Website" | "Instagram" | "Email" | "Ad" | "General";
export type AttachmentKind = "image" | "pdf" | "docx" | "text";
export type ReadStatus = "pending" | "reading" | "ready" | "held" | "failed" | "partial";

export type ReadSummary = {
  attachments: number;
  pending: number;
  reading: number;
  ready: number;
  held: number;
  failed: number;
  partial: number;
};

export type SubmissionHold = {
  reason: "confidential_term";
  routedTo: "manager";
  message: string;
};

export type Submission = {
  id: string;
  title: string;
  kind: SubmissionKind;
  channel: SubmissionChannel;
  team: string;
  status: string;
  bodyText: string;
  ownerId: string;
  ownerName: string;
  readSummary: ReadSummary;
  hold: SubmissionHold | null;
  createdAt: string;
  updatedAt: string;
};

export type Attachment = {
  id: string;
  contentId: string;
  filename: string;
  mimeType: string;
  kind: AttachmentKind;
  sizeBytes: number;
  sha256: string;
  pageCount: number;
  readStatus: ReadStatus;
  readMessage: string;
  uploadedBy: string;
  uploadedAt: string;
};

export type SubmitResponse = {
  submissionId: string;
  checkRunId: string;
  queued: number;
};

// Re-exported so Phase 2 screens import one place.
export type SubmissionFinding = Finding;

// Limits shown to the creator. Must match backend settings.
export const SUBMISSION_LIMITS = {
  maxFileMb: 10,
  maxFiles: 10,
  maxPdfPages: 20,
  acceptedExtensions: [".png", ".jpg", ".jpeg", ".pdf", ".docx", ".txt"],
} as const;
