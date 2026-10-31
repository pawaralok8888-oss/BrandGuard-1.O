import { useEffect, useState } from "react";
import { Check, Minus, RotateCcw, Save } from "lucide-react";
import { getGapReport, setIntakeResponse, type GapReport, type IntakeField, type IntakeFieldStatus } from "@/api/intake";
import { ApiError } from "@/api/client";
import { PageHeader } from "@/components/shared/PageHeader";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { LoadingState } from "@/components/shared/LoadingState";
import type { UserRole } from "@/types";
import { cn } from "@/lib/utils";

const STATUS_LABEL: Record<IntakeFieldStatus, string> = {
  covered: "Covered by data",
  provided: "Marked provided",
  not_applicable: "Not applicable",
  gap: "Gap",
};

const STATUS_STYLE: Record<IntakeFieldStatus, string> = {
  covered: "bg-emerald-50 text-emerald-800",
  provided: "bg-blue-50 text-blue-800",
  not_applicable: "bg-slate-100 text-slate-600",
  gap: "bg-red-50 text-red-700",
};

type Editing = { fieldId: string; status: "provided" | "not_applicable"; note: string };

/**
 * Brand intake: the answers a brand needs before checks mean much. Fields backed by data are covered
 * automatically. A person can mark any field provided or not applicable, with a note.
 */
export default function IntakePage({ role }: { role: UserRole }) {
  const canEdit = role === "manager" || role === "admin";
  const [report, setReport] = useState<GapReport | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Editing | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  async function load() {
    setLoadError(null);
    try {
      setReport(await getGapReport());
    } catch (error: unknown) {
      setLoadError(error instanceof ApiError && error.status === 403
        ? "Only managers and admins can see the intake report."
        : error instanceof Error ? error.message : "The intake report could not be loaded.");
    }
  }

  useEffect(() => {
    if (canEdit) void load();
  }, [canEdit]);

  if (!canEdit) {
    return (
      <div className="space-y-4">
        <PageHeader title="Brand intake" description="The brand information the checks depend on." />
        <EmptyState title="Not available for your role" description="Ask a manager to review the intake report." />
      </div>
    );
  }

  async function save(field: IntakeField, status: "provided" | "not_applicable" | null, note = "") {
    setBusy(true);
    setNotice(null);
    try {
      await setIntakeResponse(field.id, { status, note });
      setEditing(null);
      await load();
    } catch (error: unknown) {
      setNotice(error instanceof Error ? error.message : "The answer could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto pb-6">
      <PageHeader
        title="Brand intake"
        description="Covered fields are backed by approved assets, facts, guidelines and rules. Everything else needs a person to confirm it."
      />

      {notice && (
        <div role="alert" className="rounded-lg border border-red-100 bg-red-50 p-3 text-xs text-red-700">{notice}</div>
      )}

      {loadError ? (
        <ErrorState description={loadError} onRetry={() => void load()} />
      ) : report === null ? (
        <LoadingState label="Loading intake report" rows={4} />
      ) : (
        <>
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              { label: "Covered by data", value: report.summary.covered },
              { label: "Marked provided", value: report.summary.provided },
              { label: "Gaps", value: report.summary.gaps },
              { label: "Required gaps", value: report.summary.requiredGaps },
            ].map((item) => (
              <div key={item.label} className="rounded-xl border border-slate-200 bg-white p-3">
                <dt className="text-[11px] text-slate-500">{item.label}</dt>
                <dd className="mt-1 text-xl font-semibold text-navy">{item.value}</dd>
              </div>
            ))}
          </dl>

          {report.categories.map((category) => (
            <section key={category.id} className="space-y-2">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">{category.label}</h2>
              <ul className="space-y-2">
                {category.fields.map((field) => {
                  const isEditing = editing?.fieldId === field.id;
                  const hasAnswer = field.status === "provided" || field.status === "not_applicable";
                  return (
                    <li key={field.id} className="rounded-xl border border-slate-200 bg-white p-4">
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="text-xs font-semibold text-slate-800">{field.label}</h3>
                            <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-semibold", STATUS_STYLE[field.status])}>{STATUS_LABEL[field.status]}</span>
                            {field.required ? (
                              <span className="text-[10px] font-medium text-slate-500">Required</span>
                            ) : (
                              <span className="text-[10px] text-slate-400">Optional</span>
                            )}
                          </div>
                          <p className="mt-0.5 text-[11px] text-slate-500">{field.description}</p>
                          {field.coverageCheck === "manual" && field.status !== "provided" && (
                            <p className="mt-0.5 text-[10px] text-slate-400">Cannot be checked automatically. Confirm it here.</p>
                          )}
                          {field.note && <p className="mt-1 text-[11px] text-slate-600">Note: {field.note}</p>}
                        </div>

                        {canEdit && (
                          <div className="flex shrink-0 flex-wrap gap-2">
                            {!hasAnswer && field.status !== "covered" && (
                              <>
                                <button type="button" disabled={busy} onClick={() => setEditing({ fieldId: field.id, status: "provided", note: "" })} className="focus-ring inline-flex h-8 items-center gap-1.5 rounded-md bg-[#2F5BEA] px-2.5 text-[11px] font-semibold text-white disabled:opacity-50">
                                  <Check size={12} aria-hidden="true" /> Mark provided
                                </button>
                                <button type="button" disabled={busy} onClick={() => setEditing({ fieldId: field.id, status: "not_applicable", note: "" })} className="focus-ring inline-flex h-8 items-center gap-1.5 rounded-md border border-slate-200 px-2.5 text-[11px] font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-50">
                                  <Minus size={12} aria-hidden="true" /> Not applicable
                                </button>
                              </>
                            )}
                            {hasAnswer && (
                              <button type="button" disabled={busy} onClick={() => void save(field, null)} className="focus-ring inline-flex h-8 items-center gap-1.5 rounded-md border border-slate-200 px-2.5 text-[11px] font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-50">
                                <RotateCcw size={12} aria-hidden="true" /> Clear answer
                              </button>
                            )}
                          </div>
                        )}
                      </div>

                      {isEditing && editing && (
                        <div className="mt-3 flex flex-col gap-2 border-t border-slate-100 pt-3 sm:flex-row sm:items-end">
                          <label className="flex-1 text-[11px] font-medium text-slate-600">
                            Note (optional, for example who confirmed it)
                            <input
                              value={editing.note}
                              onChange={(event) => setEditing({ ...editing, note: event.target.value })}
                              maxLength={500}
                              className="mt-1 h-9 w-full rounded-lg border border-slate-200 px-2 text-xs"
                            />
                          </label>
                          <div className="flex gap-2">
                            <button type="button" disabled={busy} onClick={() => void save(field, editing.status, editing.note.trim())} className="focus-ring inline-flex h-9 items-center gap-1.5 rounded-md bg-[#2F5BEA] px-3 text-[11px] font-semibold text-white disabled:opacity-50">
                              <Save size={12} aria-hidden="true" /> Save
                            </button>
                            <button type="button" onClick={() => setEditing(null)} className="focus-ring h-9 rounded-md border border-slate-200 px-3 text-[11px] font-semibold text-slate-600">Cancel</button>
                          </div>
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
        </>
      )}
    </div>
  );
}
