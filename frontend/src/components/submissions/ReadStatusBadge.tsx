import { AlertTriangle, CheckCircle2, Loader2, ShieldAlert, XCircle, Clock } from "lucide-react";
import type { ReadStatus } from "@/api/submissions";
import { cn } from "@/lib/utils";

type ReadStatusBadgeProps = { status: ReadStatus; className?: string };

const config: Record<ReadStatus, { label: string; className: string; icon: typeof Clock; spin?: boolean }> = {
  pending: { label: "Waiting", className: "border-slate-200 bg-slate-100 text-slate-700", icon: Clock },
  reading: { label: "Reading", className: "border-blue-200 bg-blue-50 text-blue-700", icon: Loader2, spin: true },
  ready: { label: "Read", className: "border-green-200 bg-green-50 text-green-800", icon: CheckCircle2 },
  held: { label: "Held for manager", className: "border-amber-200 bg-amber-50 text-amber-900", icon: ShieldAlert },
  failed: { label: "Could not read", className: "border-red-200 bg-red-50 text-red-700", icon: XCircle },
  partial: { label: "Partly read", className: "border-orange-200 bg-orange-50 text-orange-800", icon: AlertTriangle },
};

export function ReadStatusBadge({ status, className }: ReadStatusBadgeProps) {
  const item = config[status];
  const Icon = item.icon;
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center gap-1 whitespace-nowrap rounded-full border px-2 text-[11px] font-semibold",
        item.className,
        className,
      )}
    >
      <Icon aria-hidden="true" size={11} strokeWidth={2.2} className={item.spin ? "animate-spin" : undefined} />
      {item.label}
    </span>
  );
}
