import { useEffect, useState } from "react";
import { Check, Info, Pencil } from "lucide-react";
import { deleteRulePattern, getRulePatterns, updateRulePattern, type RulePatternItem } from "@/api/knowledge";
import { ApiError } from "@/api/client";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { LoadingState } from "@/components/shared/LoadingState";
import { cn } from "@/lib/utils";

/** What the last upload produced, so the reviewer can see what was not turned into a rule. */
export type UploadSummary = {
  guideline: string;
  ruleCandidates: number;
  unparsedLines: string[];
};

type DraftRulesPanelProps = {
  summary: UploadSummary | null;
  onChanged: () => void;
};

const KIND_LABELS: Record<RulePatternItem["kind"], string> = {
  phrase: "Banned phrase",
  regex: "Pattern",
  name_variant: "Name variant",
  confidential_term: "Confidential",
  required_text: "Required text",
};

type EditDraft = { pattern: string; replacement: string; note: string };

/**
 * Review draft rules drafted from uploaded guidelines. Nothing here affects checks until a
 * manager approves it. The list comes from the server; nothing is shown that the server did not return.
 */
export function DraftRulesPanel({ summary, onChanged }: DraftRulesPanelProps) {
  const [drafts, setDrafts] = useState<RulePatternItem[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<EditDraft>({ pattern: "", replacement: "", note: "" });
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  async function load() {
    setLoadError(null);
    setForbidden(false);
    try {
      const items = await getRulePatterns({ state: "draft" });
      setDrafts(items);
      setSelected((current) => new Set([...current].filter((id) => items.some((item) => item.id === id))));
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 403) {
        setForbidden(true);
      } else {
        setLoadError(error instanceof Error ? error.message : "The draft rules could not be loaded.");
      }
    }
  }

  useEffect(() => {
    void load();
  }, [summary]);

  function toggle(id: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function approve(ids: string[]) {
    if (!ids.length) return;
    setBusy(true);
    setActionError(null);
    try {
      await Promise.all(ids.map((id) => updateRulePattern(id, { is_active: true })));
      setSelected(new Set());
      await load();
      onChanged();
    } catch (error: unknown) {
      setActionError(error instanceof Error ? error.message : "Approval failed. Nothing else was changed.");
    } finally {
      setBusy(false);
    }
  }

  function startEdit(rule: RulePatternItem) {
    setEditingId(rule.id);
    setEditDraft({ pattern: rule.pattern, replacement: rule.replacement, note: rule.note });
    setActionError(null);
  }

  async function remove(rule: RulePatternItem) {
    if (!window.confirm(`Delete the draft rule "${rule.pattern}"? This cannot be undone.`)) return;
    setBusy(true);
    setActionError(null);
    try {
      await deleteRulePattern(rule.id);
      setSelected((current) => {
        const next = new Set(current);
        next.delete(rule.id);
        return next;
      });
      await load();
    } catch (error: unknown) {
      setActionError(error instanceof Error ? error.message : "The rule could not be deleted.");
    } finally {
      setBusy(false);
    }
  }

  async function saveEdit(rule: RulePatternItem) {
    if (!editDraft.pattern.trim()) {
      setActionError("A rule needs text to match.");
      return;
    }
    setBusy(true);
    setActionError(null);
    try {
      await updateRulePattern(rule.id, {
        pattern: editDraft.pattern.trim(),
        replacement: editDraft.replacement.trim(),
        note: editDraft.note.trim(),
      });
      setEditingId(null);
      await load();
    } catch (error: unknown) {
      setActionError(error instanceof Error ? error.message : "The rule could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  if (forbidden) {
    return (
      <EmptyState
        title="Only managers can review draft rules"
        description="Ask a manager or admin to approve the rules drafted from uploaded guidelines."
      />
    );
  }
  if (loadError) {
    return <ErrorState description={loadError} onRetry={() => void load()} />;
  }
  if (drafts === null) {
    return <LoadingState label="Loading draft rules" rows={3} />;
  }

  return (
    <div className="space-y-4">
      {summary && (
        <div className="rounded-xl border border-blue-100 bg-blue-50/60 p-4">
          <p className="text-xs font-semibold text-slate-800">
            {summary.guideline}: {summary.ruleCandidates} draft {summary.ruleCandidates === 1 ? "rule" : "rules"} found
          </p>
          {summary.unparsedLines.length > 0 && (
            <div className="mt-3">
              <p className="text-[11px] font-medium text-slate-700">
                These lines were not turned into rules. Write the ones that matter as rules in the Rules tab.
              </p>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-[11px] text-slate-600">
                {summary.unparsedLines.map((line, index) => (
                  <li key={`${index}-${line}`}>{line}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <div className="flex items-start gap-2 rounded-lg bg-slate-50 p-3">
        <Info size={15} className="mt-0.5 shrink-0 text-slate-500" />
        <p className="text-[11px] leading-5 text-slate-600">
          Draft rules do not affect checks until a manager approves them. Check the wording before approving.
        </p>
      </div>

      {actionError && (
        <div role="alert" className="rounded-lg border border-red-100 bg-red-50 p-3 text-[11px] text-red-700">
          {actionError}
        </div>
      )}

      {drafts.length === 0 ? (
        <EmptyState
          title="No draft rules"
          description="Upload a guideline with quoted banned terms or a disclaimers section, and the rules it contains will appear here."
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 p-3">
            <span className="text-[11px] text-slate-500">
              {selected.size} of {drafts.length} selected
            </span>
            <button
              type="button"
              disabled={busy || selected.size === 0}
              onClick={() => void approve([...selected])}
              className="focus-ring inline-flex h-9 items-center gap-2 rounded-lg bg-[#2F5BEA] px-3 text-xs font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Check size={14} aria-hidden="true" />
              Approve selected
            </button>
          </div>

          <ul className="divide-y divide-slate-100">
            {drafts.map((rule) => (
              <li key={rule.id} className="p-3">
                {editingId === rule.id ? (
                  <div className="space-y-2">
                    <label className="block text-[11px] font-medium text-slate-600">
                      Text to match
                      <input
                        value={editDraft.pattern}
                        onChange={(event) => setEditDraft({ ...editDraft, pattern: event.target.value })}
                        className="mt-1 h-9 w-full rounded-lg border border-slate-200 px-2 text-xs font-mono"
                      />
                    </label>
                    <label className="block text-[11px] font-medium text-slate-600">
                      Use instead
                      <input
                        value={editDraft.replacement}
                        onChange={(event) => setEditDraft({ ...editDraft, replacement: event.target.value })}
                        className="mt-1 h-9 w-full rounded-lg border border-slate-200 px-2 text-xs"
                      />
                    </label>
                    <label className="block text-[11px] font-medium text-slate-600">
                      Note
                      <input
                        value={editDraft.note}
                        onChange={(event) => setEditDraft({ ...editDraft, note: event.target.value })}
                        className="mt-1 h-9 w-full rounded-lg border border-slate-200 px-2 text-xs"
                      />
                    </label>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void saveEdit(rule)}
                        className="focus-ring h-8 rounded-md bg-[#2F5BEA] px-3 text-[11px] font-semibold text-white disabled:opacity-50"
                      >
                        Save
                      </button>
                      <button
                        type="button"
                        onClick={() => setEditingId(null)}
                        className="focus-ring h-8 rounded-md border border-slate-200 px-3 text-[11px] font-semibold text-slate-600"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start">
                    <label className="flex min-w-0 flex-1 cursor-pointer items-start gap-2.5">
                      <input
                        type="checkbox"
                        checked={selected.has(rule.id)}
                        onChange={() => toggle(rule.id)}
                        aria-label={`Select rule ${rule.pattern}`}
                        className="mt-0.5 h-4 w-4 rounded border-slate-300 text-[#2F5BEA]"
                      />
                      <span className="min-w-0">
                        <span className="block font-mono text-xs text-slate-800">{rule.pattern}</span>
                        <span className="mt-0.5 block text-[11px] text-slate-500">
                          {KIND_LABELS[rule.kind]}
                          {rule.replacement && <> · use &ldquo;{rule.replacement}&rdquo;</>}
                          {rule.note && <> · {rule.note}</>}
                          {rule.guidelineId && <> · from {rule.guidelineId}</>}
                        </span>
                      </span>
                    </label>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => startEdit(rule)}
                        disabled={busy}
                        className="focus-ring inline-flex h-8 items-center gap-1.5 rounded-md border border-slate-200 px-2.5 text-[11px] font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-50"
                      >
                        <Pencil size={12} aria-hidden="true" />
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => void approve([rule.id])}
                        disabled={busy}
                        className={cn(
                          "focus-ring inline-flex h-8 items-center gap-1.5 rounded-md bg-emerald-600 px-2.5 text-[11px] font-semibold text-white hover:bg-emerald-700 disabled:opacity-50",
                        )}
                      >
                        <Check size={12} aria-hidden="true" />
                        Approve
                      </button>
                      <button
                        type="button"
                        onClick={() => void remove(rule)}
                        disabled={busy}
                        className="focus-ring inline-flex h-8 items-center gap-1.5 rounded-md border border-red-200 px-2.5 text-[11px] font-semibold text-red-700 hover:bg-red-50 disabled:opacity-50"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
