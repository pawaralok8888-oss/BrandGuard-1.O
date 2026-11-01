import { FileImage, FileText, Trash2 } from "lucide-react";
import type { Attachment } from "@/api/submissions";
import { cn } from "@/lib/utils";
import { ReadStatusBadge } from "./ReadStatusBadge";

/** Human-readable size, such as "412 KB" or "1.2 MB". */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

type AttachmentListProps = {
  attachments: Attachment[];
  canDelete?: boolean;
  onDelete?: (attachmentId: string) => void;
  className?: string;
};

export function AttachmentList({ attachments, canDelete = false, onDelete, className }: AttachmentListProps) {
  if (attachments.length === 0) {
    return <p className={cn("text-sm text-slate-500", className)}>No files attached yet.</p>;
  }

  return (
    <ul className={cn("divide-y divide-slate-200 rounded-xl border border-slate-200 bg-white", className)}>
      {attachments.map((attachment) => {
        const Icon = attachment.kind === "image" ? FileImage : FileText;
        return (
          <li key={attachment.id} className="flex items-start gap-3 px-4 py-3">
            <Icon aria-hidden="true" size={18} className="mt-0.5 shrink-0 text-slate-500" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-slate-900" title={attachment.filename}>
                {attachment.filename}
              </p>
              <p className="mt-0.5 text-xs text-slate-500">
                {formatBytes(attachment.sizeBytes)}
                {attachment.kind === "pdf" && ` · ${attachment.pageCount} page${attachment.pageCount === 1 ? "" : "s"}`}
              </p>
              {attachment.readMessage && (
                <p className="mt-1 text-xs text-slate-600">{attachment.readMessage}</p>
              )}
            </div>
            <ReadStatusBadge status={attachment.readStatus} />
            {canDelete && onDelete && (
              <button
                type="button"
                onClick={() => onDelete(attachment.id)}
                aria-label={`Remove ${attachment.filename}`}
                className="rounded-md p-1 text-slate-500 hover:bg-slate-100 hover:text-red-700"
              >
                <Trash2 aria-hidden="true" size={15} />
              </button>
            )}
          </li>
        );
      })}
    </ul>
  );
}
