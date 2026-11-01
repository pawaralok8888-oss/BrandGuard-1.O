import { useCallback, useEffect, useRef, useState } from "react";
import { Check, Minus, RotateCcw, Save } from "lucide-react";
import {
  getGapReport,
  setIntakeResponse,
  listCategoryDocuments,
  deleteIntakeDocument,
  reprocessDocument,
  listInsights,
  type GapReport,
  type IntakeCategory,
  type IntakeDocument,
  type IntakeField,
  type IntakeFieldStatus,
  type GuidelineInsight,
} from "@/api/intake";
import { ApiError } from "@/api/client";
import { PageHeader } from "@/components/shared/PageHeader";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { LoadingState } from "@/components/shared/LoadingState";
import { UploadBox } from "@/components/intake/UploadBox";
import { DocumentList } from "@/components/intake/DocumentList";
import {
  CategoryInsightDrawer,
  InsightReview,
} from "@/components/intake/InsightReview";
import type { UserRole } from "@/types";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/*  Lookup tables                                                     */
/* ------------------------------------------------------------------ */

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

/* ------------------------------------------------------------------ */
/*  Helpers                                                           */
/* ------------------------------------------------------------------ */

/** Per-category counts for the card header. Covered means covered by data or marked provided. */
function summariseCategory(category: IntakeCategory) {
  const fields = category.fields;
  return {
    total: fields.length,
    covered: fields.filter((f) => f.status === "covered" || f.status === "provided").length,
    notApplicable: fields.filter((f) => f.status === "not_applicable").length,
    requiredGaps: fields.filter((f) => f.required && f.status === "gap").length,
  };
}

/* ------------------------------------------------------------------ */
/*  Read-only view for creators and reviewers                         */
/* ------------------------------------------------------------------ */

function CreatorView() {
  const [insights, setInsights] = useState<GuidelineInsight[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await listInsights({ status: "approved" });
      // Client-side filter: only approved, even if the API returns others
      setInsights(data.filter((i) => i.status === "approved"));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not load approved insights.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto pb-6">
      <PageHeader
        title="Brand intake"
        description="The brand information the checks depend on."
      />

      <p className="text-[12px] text-slate-500">
        Approved brand guidelines. Only managers and admins can add or change them.
      </p>

      {error ? (
        <ErrorState description={error} onRetry={() => void load()} />
      ) : insights === null ? (
        <LoadingState label="Loading approved insights" rows={3} />
      ) : insights.length === 0 ? (
        <EmptyState
          title="No approved insights yet"
          description="Managers or admins will approve insights from uploaded brand documents."
        />
      ) : (
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <InsightReview
            insights={insights}
            approvedInsights={insights}
            canManage={false}
            onUpdated={() => void load()}
          />
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Manager / admin view                                              */
/* ------------------------------------------------------------------ */

export default function IntakePage({ role }: { role: UserRole }) {
  const canManage = role === "manager" || role === "admin";

  /* ---- state: gap report ---- */
  const [report, setReport] = useState<GapReport | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  /* ---- state: field editing ---- */
  const [editing, setEditing] = useState<Editing | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  /* ---- state: documents per category ---- */
  const [docsByCategory, setDocsByCategory] = useState<Record<string, IntakeDocument[]>>({});
  const [docBusyIds, setDocBusyIds] = useState<Set<string>>(new Set());

  /* ---- state: insights ---- */
  const [draftInsights, setDraftInsights] = useState<GuidelineInsight[]>([]);
  const [approvedInsights, setApprovedInsights] = useState<GuidelineInsight[]>([]);

  /* ---- state: review drawer ---- */
  const [reviewCategory, setReviewCategory] = useState<IntakeCategory | null>(null);

  /* ---- refs for cleanup ---- */
  const mountedRef = useRef(true);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  /* ---- load gap report ---- */
  const loadReport = useCallback(async () => {
    setLoadError(null);
    try {
      const data = await getGapReport();
      if (mountedRef.current) setReport(data);
    } catch (error: unknown) {
      if (!mountedRef.current) return;
      setLoadError(
        error instanceof ApiError && error.status === 403
          ? "Only managers and admins can see the intake report."
          : error instanceof Error
            ? error.message
            : "The intake report could not be loaded.",
      );
    }
  }, []);

  /* ---- load documents for all categories ---- */
  const loadDocuments = useCallback(
    async (categoryIds: string[]) => {
      try {
        const results = await Promise.all(
          categoryIds.map(async (catId) => {
            const docs = await listCategoryDocuments(catId);
            return [catId, docs] as const;
          }),
        );
        if (!mountedRef.current) return;
        setDocsByCategory((prev) => {
          const next = { ...prev };
          for (const [catId, docs] of results) {
            next[catId] = docs;
          }
          return next;
        });
      } catch {
        // Silently retry on next poll
      }
    },
    [],
  );

  /* ---- load insights ---- */
  const loadInsights = useCallback(async () => {
    try {
      const [draft, approved] = await Promise.all([
        listInsights({ status: "draft" }),
        listInsights({ status: "approved" }),
      ]);
      if (!mountedRef.current) return;
      setDraftInsights(draft);
      setApprovedInsights(approved);
    } catch {
      // best effort
    }
  }, []);

  /* ---- initial load ---- */
  useEffect(() => {
    mountedRef.current = true;
    if (canManage) {
      void loadReport();
      void loadInsights();
    }
    return () => {
      mountedRef.current = false;
    };
  }, [canManage, loadReport, loadInsights]);

  /* ---- load documents when we know category ids ---- */
  useEffect(() => {
    if (!canManage || !report) return;
    const catIds = report.categories.map((c) => c.id);
    void loadDocuments(catIds);
  }, [canManage, report, loadDocuments]);

  /* ---- polling: reload docs while any are processing ---- */
  useEffect(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }

    if (!canManage || !report) return;

    const allDocs = Object.values(docsByCategory).flat();
    const hasProcessing = allDocs.some((d) => d.status === "processing");

    if (!hasProcessing) return;

    const catIds = report.categories.map((c) => c.id);
    pollRef.current = setInterval(() => {
      void loadDocuments(catIds);
      void loadInsights();
      void loadReport();
    }, 3000);

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [canManage, report, docsByCategory, loadDocuments, loadInsights, loadReport]);

  /* ---- creators / reviewers ---- */
  if (!canManage) {
    return <CreatorView />;
  }

  /* ---- field save ---- */
  async function save(field: IntakeField, status: "provided" | "not_applicable" | null, note = "") {
    setBusy(true);
    setNotice(null);
    try {
      await setIntakeResponse(field.id, { status, note });
      setEditing(null);
      await loadReport();
    } catch (error: unknown) {
      setNotice(error instanceof Error ? error.message : "The answer could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  /* ---- document actions ---- */
  async function handleDelete(docId: string) {
    setDocBusyIds((prev) => new Set(prev).add(docId));
    try {
      await deleteIntakeDocument(docId);
      // Refresh docs and gap report (deleting removes coverage)
      if (report) {
        await loadDocuments(report.categories.map((c) => c.id));
      }
      await loadReport();
      await loadInsights();
    } catch {
      // error is visible from state
    } finally {
      setDocBusyIds((prev) => {
        const next = new Set(prev);
        next.delete(docId);
        return next;
      });
    }
  }

  async function handleReprocess(docId: string) {
    setDocBusyIds((prev) => new Set(prev).add(docId));
    try {
      await reprocessDocument(docId);
      if (report) {
        await loadDocuments(report.categories.map((c) => c.id));
      }
    } catch {
      // best effort
    } finally {
      setDocBusyIds((prev) => {
        const next = new Set(prev);
        next.delete(docId);
        return next;
      });
    }
  }

  function handleUploaded(categoryId: string) {
    // Refresh that category's docs, the gap report, and insights
    void loadDocuments([categoryId]);
    void loadReport();
    void loadInsights();
  }

  function handleInsightUpdated(updated: GuidelineInsight) {
    // Update in place in draft and approved lists
    setDraftInsights((prev) =>
      prev.map((i) => (i.id === updated.id ? updated : i)).filter((i) => i.status === "draft"),
    );
    setApprovedInsights((prev) => {
      const without = prev.filter((i) => i.id !== updated.id);
      if (updated.status === "approved") return [...without, updated];
      return without;
    });
    // Refresh gap report since approved insights change coverage
    void loadReport();
  }

  /* ---- render ---- */
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
        <ErrorState description={loadError} onRetry={() => void loadReport()} />
      ) : report === null ? (
        <LoadingState label="Loading intake report" rows={4} />
      ) : (
        <>
          {/* Summary stats */}
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

          {/* Category cards */}
          {report.categories.map((category) => {
            const counts = summariseCategory(category);
            const categoryDocs = docsByCategory[category.id] ?? [];
            const categoryDraftInsights = draftInsights.filter((i) => i.categoryId === category.id);
            const categoryApprovedInsights = approvedInsights.filter((i) => i.categoryId === category.id);

            return (
              <section key={category.id} className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
                {/* Category header */}
                <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-3">
                  <div className="flex flex-wrap items-center gap-3">
                    <h2 className="text-sm font-semibold text-navy">{category.label}</h2>
                    <div className="flex flex-wrap gap-2.5 text-[11px] text-slate-500">
                      <span>{counts.covered} of {counts.total} covered</span>
                      {counts.notApplicable > 0 && <span>{counts.notApplicable} not applicable</span>}
                      <span className={counts.requiredGaps > 0 ? "font-semibold text-red-700" : undefined}>
                        {counts.requiredGaps} required gaps
                      </span>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <UploadBox
                      categoryId={category.id}
                      onUploaded={() => handleUploaded(category.id)}
                    />
                    <button
                      type="button"
                      onClick={() => setReviewCategory(category)}
                      className="focus-ring inline-flex h-7 items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2.5 text-[11px] font-semibold text-slate-700 shadow-xs hover:bg-slate-50 transition"
                    >
                      Review insights
                      {categoryDraftInsights.length > 0 && (
                        <span className="rounded-full bg-amber-100 px-1.5 py-0.2 text-[10px] font-bold text-amber-800">
                          {categoryDraftInsights.length}
                        </span>
                      )}
                    </button>
                  </div>
                </header>

                {/* Document list */}
                <DocumentList
                  documents={categoryDocs}
                  onDelete={(id) => void handleDelete(id)}
                  onReprocess={(id) => void handleReprocess(id)}
                  busyIds={docBusyIds}
                />

                {/* Field rows */}
                <ul className="space-y-2">
                  {category.fields.map((field) => {
                    const isEditing = editing?.fieldId === field.id;
                    const hasAnswer = field.status === "provided" || field.status === "not_applicable";
                    return (
                      <li key={field.id} className="rounded-lg border border-slate-100 p-3">
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
                            {(field.approvedInsightCount ?? 0) > 0 && (
                              <p className="mt-0.5 text-[10px] text-emerald-700">
                                Approved from uploaded documents: {field.approvedInsightCount}
                              </p>
                            )}
                            {field.note && <p className="mt-1 text-[11px] text-slate-600">Note: {field.note}</p>}
                          </div>

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
            );
          })}

          {/* Per-category side panel for reviewing insights */}
          {reviewCategory && (
            <CategoryInsightDrawer
              category={reviewCategory}
              draftInsights={draftInsights.filter((i) => i.categoryId === reviewCategory.id)}
              approvedInsights={approvedInsights.filter((i) => i.categoryId === reviewCategory.id)}
              canManage={canManage}
              onClose={() => setReviewCategory(null)}
              onUpdated={handleInsightUpdated}
            />
          )}
        </>
      )}
    </div>
  );
}
