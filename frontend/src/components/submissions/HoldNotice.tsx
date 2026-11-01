import { ShieldAlert } from "lucide-react";
import type { SubmissionHold } from "@/api/submissions";

/**
 * Shows the warning for a held submission. It shows only the message, never the term or any
 * detail about what matched (phase2_contract.md section 1 and section 5).
 */
export function HoldNotice({ hold }: { hold: SubmissionHold | null }) {
  if (!hold) return null;
  return (
    <div role="status" className="flex gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">
      <ShieldAlert aria-hidden="true" size={18} className="mt-0.5 shrink-0" />
      <p>{hold.message}</p>
    </div>
  );
}
