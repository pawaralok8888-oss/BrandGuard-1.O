import { FileText, Loader2, RotateCcw, Trash2 } from "lucide-react";
import type { IntakeDocument } from "@/api/intake";
import { cn } from "@/lib/utils";

type DocumentListProps = {
  documents: IntakeDocument[];
  onDelete: (docId: string) => void;
  onReprocess: (docId: string) => void;
  busyIds: Set<string>;
};

const DOC_STATUS_STYLE: Record<string, string> = {
  processing: "bg-amber-50 text-amber-700",
  ready: "bg-emerald-50 text-emerald-800",
  failed: "bg-red-50 text-red-700",
};

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function DocumentList({ documents, onDelete, onReprocess, busyIds }: DocumentListProps) {
  if (documents.length === 0) return null;

  return (
    <ul className="space-y-1.5">
      {documents.map((doc) => {
        const isBusy = busyIds.has(doc.id);
        const hasReprocess = doc.status === "failed" || doc.status === "ready";

        return (
          <li
            key={doc.id}
            className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-100 bg-slate-50/60 px-3 py-2 text-[11px]"
          >
            <FileText size={13} aria-hidden="true" className="shrink-0 text-slate-400" />

            <div className="min-w-0 flex-1">
              <p className="truncate font-medium text-slate-800">{doc.filename}</p>
              <p className="text-[10px] text-slate-400">
                {formatBytes(doc.sizeBytes)}
                {doc.uploadedBy ? ` · ${doc.uploadedBy}` : ""}
                {doc.uploadedAt ? ` · ${formatTime(doc.uploadedAt)}` : ""}
              </p>
            </div>

            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-[10px] font-semibold",
                DOC_STATUS_STYLE[doc.status] ?? "bg-slate-100 text-slate-600",
              )}
            >
              {doc.status === "processing" && (
                <Loader2 size={10} aria-hidden="true" className="mr-1 inline animate-spin" />
              )}
              {doc.status}
            </span>

            {doc.insightCount != null && (
              <span className="text-[10px] text-slate-500">
                {doc.insightCount} {doc.insightCount === 1 ? "insight" : "insights"}
              </span>
            )}

            {doc.status === "failed" && doc.errorMessage && (
              <p className="w-full text-[10px] text-red-600">{doc.errorMessage}</p>
            )}

            <div className="flex shrink-0 items-center gap-1.5">
              {hasReprocess && (
                <button
                  type="button"
                  disabled={isBusy}
                  onClick={() => onReprocess(doc.id)}
                  title="Reprocess document"
                  className="focus-ring inline-flex h-6 items-center gap-1 rounded border border-slate-200 px-2 text-[10px] font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-50"
                >
                  <RotateCcw size={10} aria-hidden="true" /> Reprocess
                </button>
              )}
              <button
                type="button"
                disabled={isBusy}
                onClick={() => onDelete(doc.id)}
                title="Delete document"
                className="focus-ring inline-flex h-6 items-center gap-1 rounded border border-red-200 px-2 text-[10px] font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
              >
                <Trash2 size={10} aria-hidden="true" /> Delete
              </button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
