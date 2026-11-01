// Phase 2 API: types and calls. Types must match phase2_contract.md exactly.
// Calls use the shared request helper in ./client (not edited here).

import type { Finding } from "../types";
import { apiRequest } from "./client";

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

export type SubmissionFinding = Finding;

export type CreateSubmissionInput = {
  title: string;
  kind: SubmissionKind;
  team: string;
  channel: SubmissionChannel;
  bodyText?: string;
};

// Limits shown to the creator. Must match backend settings (config.py).
export const SUBMISSION_LIMITS = {
  maxFileMb: 10,
  maxFiles: 10,
  maxPdfPages: 20,
  acceptedExtensions: [".png", ".jpg", ".jpeg", ".pdf", ".docx", ".txt"],
} as const;

/** Create a submission. Returns the new submission. */
export function createSubmission(input: CreateSubmissionInput): Promise<Submission> {
  return apiRequest<Submission>("/api/submissions", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

/** One submission. The server returns 404 if it does not exist or is not visible to the caller. */
export function getSubmission(submissionId: string): Promise<Submission> {
  return apiRequest<Submission>(`/api/submissions/${encodeURIComponent(submissionId)}`);
}

/** Attach one file. A file identical to one already attached returns the existing attachment. */
export function uploadAttachment(submissionId: string, file: File): Promise<Attachment> {
  const form = new FormData();
  form.append("file", file);
  return apiRequest<Attachment>(`/api/submissions/${encodeURIComponent(submissionId)}/attachments`, {
    method: "POST",
    body: form,
  });
}

/** Attachments, oldest first, without deleted ones. */
export function listAttachments(submissionId: string): Promise<Attachment[]> {
  return apiRequest<Attachment[]>(`/api/submissions/${encodeURIComponent(submissionId)}/attachments`);
}

/** Soft-delete one attachment. Resolves when the server answers 204. */
export function deleteAttachment(submissionId: string, attachmentId: string): Promise<void> {
  return apiRequest<void>(
    `/api/submissions/${encodeURIComponent(submissionId)}/attachments/${encodeURIComponent(attachmentId)}`,
    { method: "DELETE" },
  );
}

/** Start the reading pipeline. Returns 202 with the check run id. Rejects with 409 if already running. */
export function submitForChecking(submissionId: string): Promise<SubmitResponse> {
  return apiRequest<SubmitResponse>(`/api/submissions/${encodeURIComponent(submissionId)}/submit`, {
    method: "POST",
  });
}

/** Findings for a submission. Uses the existing content findings endpoint. */
export function getSubmissionFindings(submissionId: string): Promise<Finding[]> {
  return apiRequest<Finding[]>(`/api/content/${encodeURIComponent(submissionId)}/findings`);
}

/**
 * Polls the attachment list every `intervalMs` while any attachment is pending or reading.
 * Returns a stop function. Call it when the screen unmounts.
 */
export function pollAttachments(
  submissionId: string,
  onUpdate: (attachments: Attachment[]) => void,
  intervalMs = 3000,
): () => void {
  let stopped = false;
  let timer: ReturnType<typeof setTimeout> | undefined;

  async function tick() {
    if (stopped) return;
    try {
      const attachments = await listAttachments(submissionId);
      if (stopped) return;
      onUpdate(attachments);
      const busy = attachments.some((a) => a.readStatus === "pending" || a.readStatus === "reading");
      if (busy) timer = setTimeout(tick, intervalMs);
    } catch {
      if (!stopped) timer = setTimeout(tick, intervalMs * 2);
    }
  }

  void tick();
  return () => {
    stopped = true;
    if (timer) clearTimeout(timer);
  };
}
