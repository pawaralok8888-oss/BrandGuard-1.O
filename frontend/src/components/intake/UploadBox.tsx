import { useCallback, useRef, useState } from "react";
import { Loader2, Upload } from "lucide-react";
import { uploadIntakeDocument, type IntakeDocument } from "@/api/intake";
import { ApiError } from "@/api/client";
import { cn } from "@/lib/utils";

type UploadBoxProps = {
  categoryId: string;
  onUploaded: (doc: IntakeDocument) => void;
};

export function UploadBox({ categoryId, onUploaded }: UploadBoxProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const handleFile = useCallback(
    async (file: File) => {
      setError(null);
      setUploading(true);
      try {
        const doc = await uploadIntakeDocument(categoryId, file);
        onUploaded(doc);
      } catch (err: unknown) {
        if (err instanceof ApiError) {
          if (err.status === 413) {
            setError(err.message || "File size exceeds the 10 MB limit.");
          } else if (err.status === 415) {
            setError(err.message || "Unsupported file type: only .pdf and .docx files are accepted.");
          } else if (err.status === 403) {
            setError(err.message || "Only managers and admins can upload brand documents.");
          } else {
            setError(err.message);
          }
        } else {
          setError(err instanceof Error ? err.message : "Upload failed.");
        }
      } finally {
        setUploading(false);
        if (inputRef.current) inputRef.current.value = "";
      }
    },
    [categoryId, onUploaded],
  );

  const onInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) void handleFile(file);
    },
    [handleFile],
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragOver(false);
      const file = e.dataTransfer.files?.[0];
      if (file) void handleFile(file);
    },
    [handleFile],
  );

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setDragOver(true);
        }}
        onDragEnter={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setDragOver(true);
        }}
        onDragLeave={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setDragOver(false);
        }}
        onDrop={onDrop}
        className={cn(
          "inline-flex items-center gap-2 rounded-lg border border-dashed px-2.5 py-1.5 transition text-[11px]",
          dragOver
            ? "border-brand bg-blue-50 text-brand"
            : "border-slate-300 bg-slate-50/70 hover:border-slate-400 text-slate-600",
          uploading && "pointer-events-none opacity-60",
        )}
      >
        <Upload size={13} aria-hidden="true" className="shrink-0 text-slate-400" />
        <span className="text-[10px] text-slate-500">
          .pdf, .docx · Max 10 MB
        </span>
        <label
          className={cn(
            "focus-ring inline-flex h-6 shrink-0 cursor-pointer items-center gap-1 rounded bg-[#2F5BEA] px-2 text-[10px] font-semibold text-white hover:bg-blue-700 transition",
            uploading && "pointer-events-none opacity-50",
          )}
        >
          {uploading ? (
            <>
              <Loader2 size={10} aria-hidden="true" className="animate-spin" />
              <span>Uploading…</span>
            </>
          ) : (
            <span>Upload document</span>
          )}
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.docx"
            disabled={uploading}
            onChange={onInputChange}
            className="sr-only"
          />
        </label>
      </div>

      {error && (
        <span role="alert" className="text-[11px] font-medium text-red-600">
          {error}
        </span>
      )}
    </div>
  );
}
