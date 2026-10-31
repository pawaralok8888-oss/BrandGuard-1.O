import { useEffect, useState } from "react";
import { getHealth, type HealthResponse, type ServiceState } from "@/api/health";
import { PageHeader } from "@/components/shared/PageHeader";
import { ErrorState } from "@/components/shared/ErrorState";
import { LoadingState } from "@/components/shared/LoadingState";
import type { DemoUser } from "@/types";
import { cn } from "@/lib/utils";

const ROLE_LABEL: Record<DemoUser["role"], string> = {
  creator: "Creator",
  manager: "Manager",
  reviewer: "Reviewer",
  admin: "Admin",
};

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 border-t border-slate-100 py-2.5 first:border-t-0">
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="text-xs font-medium text-slate-800">{value}</dd>
    </div>
  );
}

function StatePill({ state, okLabel = "Connected", offLabel = "Not configured" }: { state: "ok" | "down" | ServiceState; okLabel?: string; offLabel?: string }) {
  const good = state === "ok" || state === "configured";
  return (
    <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-semibold", good ? "bg-emerald-50 text-emerald-800" : "bg-amber-50 text-amber-800")}>
      {good ? okLabel : offLabel}
    </span>
  );
}

/** Your account, and the state of the services the app depends on. Values are set on the server, not here. */
export default function SettingsPage({ user }: { user: DemoUser }) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      setHealth(await getHealth());
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "The server could not be reached.");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto pb-6">
      <PageHeader title="Settings" description="Your account and the status of the services BrandGuard uses." />

      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="text-xs font-semibold text-slate-800">Your account</h2>
        <dl className="mt-2">
          <Row label="Name" value={user.name} />
          <Row label="Role" value={ROLE_LABEL[user.role]} />
          <Row label="Title" value={user.title} />
        </dl>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="text-xs font-semibold text-slate-800">Services</h2>
        {error ? (
          <div className="mt-3">
            <ErrorState title="Cannot reach the BrandGuard server" description={error} onRetry={() => void load()} />
          </div>
        ) : health === null ? (
          <div className="mt-3"><LoadingState label="Checking services" rows={3} /></div>
        ) : (
          <dl className="mt-2">
            <Row label="Server" value="Reachable" />
            <div className="flex items-center justify-between gap-4 border-t border-slate-100 py-2.5">
              <dt className="text-xs text-slate-500">Database</dt>
              <dd><StatePill state={health.database} /></dd>
            </div>
            <div className="flex items-center justify-between gap-4 border-t border-slate-100 py-2.5">
              <dt className="text-xs text-slate-500">AI checks</dt>
              <dd><StatePill state={health.services.ai} okLabel="Configured" offLabel="Rules only" /></dd>
            </div>
            <div className="flex items-center justify-between gap-4 border-t border-slate-100 py-2.5">
              <dt className="text-xs text-slate-500">Slack alerts</dt>
              <dd><StatePill state={health.services.slack} okLabel="Configured" /></dd>
            </div>
            <div className="flex items-center justify-between gap-4 border-t border-slate-100 py-2.5">
              <dt className="text-xs text-slate-500">Email alerts</dt>
              <dd><StatePill state={health.services.email} okLabel="Configured" /></dd>
            </div>
          </dl>
        )}
        <p className="mt-3 text-[11px] leading-5 text-slate-500">
          These services are set up by the administrator on the server. Nothing here changes them. Keys and tokens are never shown.
        </p>
      </section>
    </div>
  );
}
