import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Check, Loader2, X } from "lucide-react";
import {
  approveInsight,
  rejectInsight,
  type GuidelineInsight,
} from "@/api/intake";
import { ConfidenceBar } from "@/components/shared/ConfidenceBar";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/*  InsightCard – a single insight row with approve / reject actions   */
/* ------------------------------------------------------------------ */

type InsightCardProps = {
  insight: GuidelineInsight;
  canManage: boolean;
  conflicting: boolean;
  onUpdated: (updated: GuidelineInsight) => void;
};

export function InsightCard({ insight, canManage, conflicting, onUpdated }: InsightCardProps) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAction(action: "approve" | "reject") {
    setBusy(true);
    setError(null);
    try {
      const updated =
        action === "approve"
          ? await approveInsight(insight.id)
          : await rejectInsight(insight.id);
      onUpdated(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Action failed.");
    } finally {
      setBusy(false);
    }
  }

  const statusStyle: Record<string, string> = {
    draft: "bg-amber-50 text-amber-700",
    approved: "bg-emerald-50 text-emerald-800",
    rejected: "bg-slate-100 text-slate-500",
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium text-slate-800">{insight.value}</p>
          {insight.evidence && (
            <blockquote className="mt-1.5 rounded border-l-2 border-slate-300 bg-slate-50 p-2 text-[11px] italic text-slate-600">
              "{insight.evidence}"
            </blockquote>
          )}
          <div className="mt-2 max-w-[160px]">
            <ConfidenceBar value={insight.confidence} showLabel />
          </div>
        </div>
        <span
          className={cn(
            "shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold capitalize",
            statusStyle[insight.status] ?? "bg-slate-100 text-slate-600",
          )}
        >
          {insight.status}
        </span>
      </div>

      {conflicting && (
        <div className="mt-2 flex items-center gap-1.5 rounded border border-amber-200 bg-amber-50 px-2 py-1 text-[11px] text-amber-800">
          <AlertTriangle size={12} aria-hidden="true" className="shrink-0 text-amber-600" />
          <span>This field has conflicting insights. Check which one is current.</span>
        </div>
      )}

      {error && (
        <p role="alert" className="mt-1.5 text-[11px] font-medium text-red-600">
          {error}
        </p>
      )}

      {canManage && insight.status === "draft" && (
        <div className="mt-2.5 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => void handleAction("approve")}
            className="focus-ring inline-flex h-7 items-center gap-1 rounded-md bg-emerald-600 px-2.5 text-[11px] font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {busy ? (
              <Loader2 size={11} aria-hidden="true" className="animate-spin" />
            ) : (
              <Check size={11} aria-hidden="true" />
            )}
            Approve
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => void handleAction("reject")}
            className="focus-ring inline-flex h-7 items-center gap-1 rounded-md border border-slate-200 px-2.5 text-[11px] font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-50"
          >
            {busy ? (
              <Loader2 size={11} aria-hidden="true" className="animate-spin" />
            ) : (
              <X size={11} aria-hidden="true" />
            )}
            Reject
          </button>
        </div>
      )}

      {insight.status !== "draft" && (insight.reviewedBy || insight.reviewedAt) && (
        <p className="mt-2 text-[10px] text-slate-400">
          {insight.reviewedBy ? `Reviewed by ${insight.reviewedBy}` : ""}
          {insight.reviewedBy && insight.reviewedAt ? " · " : ""}
          {insight.reviewedAt ? new Date(insight.reviewedAt).toLocaleString() : ""}
        </p>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  InsightReview – grouped insight lists for managers / read-only     */
/* ------------------------------------------------------------------ */

type InsightReviewProps = {
  insights: GuidelineInsight[];
  approvedInsights?: GuidelineInsight[];
  canManage: boolean;
  onUpdated: (updated: GuidelineInsight) => void;
};

/**
 * Renders insight cards grouped by field. Managers see approve / reject;
 * creators and reviewers see approved insights only (caller filters).
 */
export function InsightReview({
  insights,
  approvedInsights = [],
  canManage,
  onUpdated,
}: InsightReviewProps) {
  if (insights.length === 0) return null;

  // Group by fieldId
  const groups = useMemo(() => {
    const groupedMap = new Map<string, { label: string; insights: GuidelineInsight[] }>();
    for (const ins of insights) {
      let group = groupedMap.get(ins.fieldId);
      if (!group) {
        group = { label: ins.fieldLabel, insights: [] };
        groupedMap.set(ins.fieldId, group);
      }
      group.insights.push(ins);
    }
    return [...groupedMap.entries()];
  }, [insights]);

  // Conflict detection: if one field has approved insights from more than one document
  const conflictFields = useMemo(() => {
    const conflictSet = new Set<string>();
    const docsByField = new Map<string, Set<string>>();

    // Check across all approved insights
    const allApproved = approvedInsights.length > 0
      ? approvedInsights
      : insights.filter((i) => i.status === "approved");

    for (const ins of allApproved) {
      if (ins.status === "approved") {
        let docs = docsByField.get(ins.fieldId);
        if (!docs) {
          docs = new Set();
          docsByField.set(ins.fieldId, docs);
        }
        docs.add(ins.documentId);
      }
    }

    for (const [fieldId, docs] of docsByField.entries()) {
      if (docs.size > 1) {
        conflictSet.add(fieldId);
      }
    }

    return conflictSet;
  }, [insights, approvedInsights]);

  return (
    <div className="space-y-4">
      {groups.map(([fieldId, group]) => (
        <div key={fieldId} className="space-y-2">
          <h4 className="text-xs font-semibold text-slate-700">{group.label}</h4>
          <div className="space-y-2">
            {group.insights.map((ins) => (
              <InsightCard
                key={ins.id}
                insight={ins}
                canManage={canManage}
                conflicting={conflictFields.has(fieldId)}
                onUpdated={onUpdated}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  CategoryInsightDrawer – per-category side panel for managers       */
/* ------------------------------------------------------------------ */

type CategoryInsightDrawerProps = {
  category: { id: string; label: string };
  draftInsights: GuidelineInsight[];
  approvedInsights: GuidelineInsight[];
  canManage: boolean;
  onClose: () => void;
  onUpdated: (updated: GuidelineInsight) => void;
};

export function CategoryInsightDrawer({
  category,
  draftInsights,
  approvedInsights,
  canManage,
  onClose,
  onUpdated,
}: CategoryInsightDrawerProps) {
  const [activeTab, setActiveTab] = useState<"draft" | "approved">(
    draftInsights.length > 0 ? "draft" : "approved",
  );

  // Close on Escape key
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-900/30 backdrop-blur-xs transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Side panel */}
      <div className="relative flex h-full w-full max-w-lg flex-col border-l border-slate-200 bg-white shadow-2xl">
        {/* Panel Header */}
        <header className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <div>
            <h2 className="text-sm font-semibold text-navy">
              {category.label} — Insight Review
            </h2>
            <p className="mt-0.5 text-[11px] text-slate-500">
              Review draft insights extracted from uploaded documents.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close panel"
            className="focus-ring flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          >
            <X size={16} aria-hidden="true" />
          </button>
        </header>

        {/* Tab selection */}
        <div className="flex border-b border-slate-200 px-5">
          <button
            type="button"
            onClick={() => setActiveTab("draft")}
            className={cn(
              "border-b-2 py-2.5 text-xs font-semibold transition",
              activeTab === "draft"
                ? "border-[#2F5BEA] text-[#2F5BEA]"
                : "border-transparent text-slate-500 hover:text-slate-800",
            )}
          >
            Draft insights ({draftInsights.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("approved")}
            className={cn(
              "ml-6 border-b-2 py-2.5 text-xs font-semibold transition",
              activeTab === "approved"
                ? "border-[#2F5BEA] text-[#2F5BEA]"
                : "border-transparent text-slate-500 hover:text-slate-800",
            )}
          >
            Approved insights ({approvedInsights.length})
          </button>
        </div>

        {/* Panel Content */}
        <div className="flex-1 overflow-y-auto p-5">
          {activeTab === "draft" ? (
            draftInsights.length === 0 ? (
              <p className="text-center text-xs text-slate-500">
                No draft insights for this category. Upload documents to extract insights.
              </p>
            ) : (
              <InsightReview
                insights={draftInsights}
                approvedInsights={approvedInsights}
                canManage={canManage}
                onUpdated={onUpdated}
              />
            )
          ) : approvedInsights.length === 0 ? (
            <p className="text-center text-xs text-slate-500">
              No approved insights for this category yet.
            </p>
          ) : (
            <InsightReview
              insights={approvedInsights}
              approvedInsights={approvedInsights}
              canManage={false}
              onUpdated={onUpdated}
            />
          )}
        </div>
      </div>
    </div>
  );
}
