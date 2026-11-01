import { useRef, useState, type DragEvent } from "react";
import { UploadCloud } from "lucide-react";
import { SUBMISSION_LIMITS } from "@/api/submissions";
import { cn } from "@/lib/utils";

export type FileCheck = { accepted: File[]; errors: string[] };

const MB = 1024 * 1024;

/** Checks files against the limits in phase2_contract.md section 4.3. Pure, so it can be tested. */
export function validateFiles(files: File[], existingCount: number): FileCheck {
  const accepted: File[] = [];
  const errors: string[] = [];
  let count = existingCount;

  for (const file of files) {
    const dot = file.name.lastIndexOf(".");
    const extension = dot >= 0 ? file.name.slice(dot).toLowerCase() : "";
    if (!SUBMISSION_LIMITS.acceptedExtensions.includes(extension as never)) {
      errors.push(`${file.name}: type not allowed. Use ${SUBMISSION_LIMITS.acceptedExtensions.join(", ")}.`);
      continue;
    }
    if (file.size === 0) {
      errors.push(`${file.name}: the file is empty.`);
      continue;
    }
    if (file.size > SUBMISSION_LIMITS.maxFileMb * MB) {
      errors.push(`${file.name}: larger than ${SUBMISSION_LIMITS.maxFileMb} MB.`);
      continue;
    }
    if (count >= SUBMISSION_LIMITS.maxFiles) {
      errors.push(`Only ${SUBMISSION_LIMITS.maxFiles} files can be attached to one submission.`);
      break;
    }
    accepted.push(file);
    count += 1;
  }
  return { accepted, errors };
}

type FileDropZoneProps = {
  existingCount: number;
  disabled?: boolean;
  onFiles: (files: File[]) => void;
  className?: string;
};

export function FileDropZone({ existingCount, disabled = false, onFiles, className }: FileDropZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);

  function handle(files: File[]) {
    const result = validateFiles(files, existingCount);
    setErrors(result.errors);
    if (result.accepted.length > 0) onFiles(result.accepted);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    if (!disabled) handle(Array.from(event.dataTransfer.files));
  }

  return (
    <div className={cn("space-y-2", className)}>
      <div
        onDragOver={(event) => {
          event.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "flex flex-col items-center justify-center rounded-xl border border-dashed px-5 py-7 text-center",
          dragging ? "border-brand bg-brand-soft" : "border-slate-300 bg-white",
          disabled && "opacity-60",
        )}
      >
        <UploadCloud aria-hidden="true" size={22} className="mb-2 text-slate-500" />
        <p className="text-sm font-medium text-slate-800">Drop files here, or choose files</p>
        <p className="mt-1 text-xs text-slate-500">
          {SUBMISSION_LIMITS.acceptedExtensions.join(", ")} · up to {SUBMISSION_LIMITS.maxFileMb} MB each ·
          up to {SUBMISSION_LIMITS.maxFiles} files
        </p>
        <button
          type="button"
          disabled={disabled}
          onClick={() => inputRef.current?.click()}
          className="mt-3 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-800 hover:bg-slate-50 disabled:cursor-not-allowed"
        >
          Choose files
        </button>
        <input
          ref={inputRef}
          type="file"
          multiple
          className="sr-only"
          accept={SUBMISSION_LIMITS.acceptedExtensions.join(",")}
          disabled={disabled}
          onChange={(event) => {
            handle(Array.from(event.target.files ?? []));
            event.target.value = "";
          }}
          aria-label="Choose files to attach"
        />
      </div>
      {errors.length > 0 && (
        <ul role="alert" className="space-y-1 rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-xs text-red-800">
          {errors.map((message) => (
            <li key={message}>{message}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
