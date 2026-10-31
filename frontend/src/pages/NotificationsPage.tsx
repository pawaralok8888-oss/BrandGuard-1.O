import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { listNotifications, type NotificationItem, type NotificationStatus } from "@/api/notifications";
import { getHealth, type HealthResponse, type ServiceState } from "@/api/health";
import { PageHeader } from "@/components/shared/PageHeader";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { LoadingState } from "@/components/shared/LoadingState";
import type { UserRole } from "@/types";
import { cn } from "@/lib/utils";

const FILTERS: { value: NotificationStatus | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "sent", label: "Sent" },
  { value: "failed", label: "Failed" },
  { value: "skipped", label: "Skipped" },
];

const STATUS_STYLE: Record<string, string> = {
  sent: "bg-emerald-50 text-emerald-800",
  failed: "bg-red-50 text-red-700",
  skipped: "bg-amber-50 text-amber-800",
  queued: "bg-slate-100 text-slate-600",
  read: "bg-slate-100 text-slate-600",
};

const SERVICE_LABEL: Record<keyof HealthResponse["services"], string> = {
  slack: "Slack",
  email: "Email",
  ai: "AI checks",
};

function formatWhen(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

/** Alert delivery log. Every attempt is recorded, including the ones that were skipped and why. */
export default function NotificationsPage({ role }: { role: UserRole }) {
  const canView = role === "manager" || role === "admin";
  const [filter, setFilter] = useState<NotificationStatus | "all">("all");
  const [items, setItems] = useState<NotificationItem[] | null>(null);
  const [services, setServices] = useState<HealthResponse["services"] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      const [log, health] = await Promise.all([
        listNotifications(filter === "all" ? undefined : filter),
        getHealth().catch(() => null),
      ]);
      setItems(log);
      setServices(health?.services ?? null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "The notification log could not be loaded.");
    }
  }

  useEffect(() => {
    if (canView) void load();
  }, [canView, filter]);

  if (!canView) {
    return (
      <div className="space-y-4">
        <PageHeader title="Notifications" description="Alert delivery history." />
        <EmptyState title="Not available for your role" description="Ask a manager to review notification delivery." />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto pb-6">
      <PageHeader
        title="Notifications"
        description="Every alert delivery attempt. A skipped message means the channel is not set up on the server, and the reason is shown."
        actions={
          <button type="button" onClick={() => void load()} className="focus-ring inline-flex h-9 items-center gap-2 rounded-lg border border-slate-200 px-3 text-xs font-semibold text-slate-600 hover:bg-slate-50">
            <RefreshCw size={13} aria-hidden="true" /> Refresh
          </button>
        }
      />

      {services && (
        <div className="grid gap-2 sm:grid-cols-3">
          {(Object.keys(SERVICE_LABEL) as (keyof HealthResponse["services"])[]).map((key) => {
            const state: ServiceState = services[key];
            return (
              <div key={key} className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-3">
                <span className="text-xs font-medium text-slate-700">{SERVICE_LABEL[key]}</span>
                <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-semibold", state === "configured" ? "bg-emerald-50 text-emerald-800" : "bg-amber-50 text-amber-800")}>
                  {state === "configured" ? "Configured" : "Not configured"}
                </span>
              </div>
            );
          })}
        </div>
      )}

      <div role="tablist" aria-label="Filter by status" className="flex flex-wrap gap-2">
        {FILTERS.map((item) => (
          <button
            key={item.value}
            role="tab"
            aria-selected={filter === item.value}
            onClick={() => setFilter(item.value)}
            className={cn(
              "focus-ring h-8 rounded-full border px-3 text-[11px] font-semibold",
              filter === item.value ? "border-blue-200 bg-blue-50 text-blue-700" : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50",
            )}
          >
            {item.label}
          </button>
        ))}
      </div>

      {error ? (
        <ErrorState description={error} onRetry={() => void load()} />
      ) : items === null ? (
        <LoadingState label="Loading notifications" rows={4} />
      ) : items.length === 0 ? (
        <EmptyState title="No notifications" description="Alerts appear here after a fact used in a published post changes." />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="min-w-full text-left text-[11px]">
            <thead className="border-b border-slate-100 bg-slate-50 text-slate-500">
              <tr>
                <th className="px-3 py-2 font-semibold">When</th>
                <th className="px-3 py-2 font-semibold">Channel</th>
                <th className="px-3 py-2 font-semibold">Subject</th>
                <th className="px-3 py-2 font-semibold">Status</th>
                <th className="px-3 py-2 font-semibold">Reason</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {items.map((item) => (
                <tr key={item.id}>
                  <td className="whitespace-nowrap px-3 py-2 text-slate-500">{formatWhen(item.createdAt)}</td>
                  <td className="px-3 py-2 capitalize text-slate-700">{item.channel}</td>
                  <td className="max-w-xs truncate px-3 py-2 text-slate-800" title={item.subject}>{item.subject}</td>
                  <td className="px-3 py-2">
                    <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-semibold capitalize", STATUS_STYLE[item.status] ?? STATUS_STYLE.queued)}>{item.status}</span>
                  </td>
                  <td className="px-3 py-2 text-slate-500">{item.error || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
