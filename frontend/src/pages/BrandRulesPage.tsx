import { useEffect, useMemo, useState } from "react";
import { Check, Pencil, Plus, Undo2, X } from "lucide-react";
import {
  approveBrandRule,
  createBrandRule,
  listBrandRules,
  retireBrandRule,
  updateBrandRule,
  type BrandRule,
  type BrandRuleChannel,
  type BrandRuleInput,
  type BrandRuleKind,
  type BrandRuleSeverity,
  type BrandRuleStatus,
} from "@/api/brandRules";
import { ApiError } from "@/api/client";
import { PageHeader } from "@/components/shared/PageHeader";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { LoadingState } from "@/components/shared/LoadingState";
import type { UserRole } from "@/types";
import { cn } from "@/lib/utils";

const KIND_HELP: Record<BrandRuleKind, string> = {
  phrase: "A word or phrase that must not appear. The replacement is suggested in its place.",
  regex: "A regular expression. Checked before saving, so an invalid pattern is refused.",
  name_variant: "A spelling of a product or company name that must be corrected.",
  required_text: "Text that must appear in the content, such as a disclaimer.",
};

const STATUS_FILTERS: { value: BrandRuleStatus | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "draft", label: "Draft" },
  { value: "approved", label: "Approved" },
  { value: "retired", label: "Retired" },
];

const STATUS_STYLE: Record<BrandRuleStatus, string> = {
  draft: "bg-amber-50 text-amber-800",
  approved: "bg-emerald-50 text-emerald-800",
  retired: "bg-slate-100 text-slate-600",
};

const EMPTY_FORM: BrandRuleInput = {
  title: "",
  kind: "phrase",
  pattern: "",
  replacement: "",
  reason: "",
  channel: null,
  severity: "warning",
};

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : fallback;
}

/**
 * Brand rules: draft, approved, retired. A manager creates a rule, and a different person approves it.
 * Only approved rules are checked. Retired rules stop being checked, and that cannot be undone.
 */
export default function BrandRulesPage({ role, currentUserId }: { role: UserRole; currentUserId: string }) {
  const canManage = role === "manager" || role === "admin";
  const [rules, setRules] = useState<BrandRule[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [filter, setFilter] = useState<BrandRuleStatus | "all">("all");
  const [form, setForm] = useState<BrandRuleInput>(EMPTY_FORM);
  const [creating, setCreating] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<BrandRuleInput>(EMPTY_FORM);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: "ok" | "error"; text: string } | null>(null);

  async function load() {
    setLoadError(null);
    try {
      setRules(await listBrandRules());
    } catch (error: unknown) {
      setLoadError(errorMessage(error, "The brand rules could not be loaded."));
    }
  }

  useEffect(() => {
    if (canManage) void load();
  }, [canManage]);

  const visible = useMemo(
    () => (rules ?? []).filter((rule) => filter === "all" || rule.status === filter),
    [rules, filter],
  );
  const counts = useMemo(() => {
    const all = rules ?? [];
    return {
      all: all.length,
      draft: all.filter((r) => r.status === "draft").length,
      approved: all.filter((r) => r.status === "approved").length,
      retired: all.filter((r) => r.status === "retired").length,
    };
  }, [rules]);

  if (!canManage) {
    return (
      <div className="space-y-4">
        <PageHeader title="Brand rules" description="Only managers and admins can manage brand rules." />
        <EmptyState title="Not available for your role" description="Ask a manager to create or approve brand rules." />
      </div>
    );
  }

  async function run(id: string | null, action: () => Promise<unknown>, success: string) {
    setBusyId(id ?? "new");
    setNotice(null);
    try {
      await action();
      setNotice({ tone: "ok", text: success });
      await load();
    } catch (error: unknown) {
      setNotice({ tone: "error", text: errorMessage(error, "The change could not be saved.") });
    } finally {
      setBusyId(null);
    }
  }

  function submitNew(event: React.FormEvent) {
    event.preventDefault();
    if (!form.title.trim() || !form.pattern.trim()) {
      setNotice({ tone: "error", text: "A rule needs a title and the text it matches." });
      return;
    }
    void run(
      null,
      async () => {
        await createBrandRule({ ...form, title: form.title.trim(), pattern: form.pattern.trim() });
        setForm(EMPTY_FORM);
        setCreating(false);
      },
      "Draft rule created. Another manager must approve it before it is checked.",
    );
  }

  function saveEdit(rule: BrandRule) {
    void run(
      rule.id,
      async () => {
        await updateBrandRule(rule.id, {
          title: editDraft.title.trim(),
          pattern: editDraft.pattern.trim(),
          replacement: editDraft.replacement ?? "",
          reason: editDraft.reason ?? "",
          channel: editDraft.channel ?? null,
          severity: editDraft.severity,
        });
        setEditingId(null);
      },
      "Draft saved.",
    );
  }

  function startEdit(rule: BrandRule) {
    setEditingId(rule.id);
    setEditDraft({
      title: rule.title,
      kind: rule.kind,
      pattern: rule.pattern,
      replacement: rule.replacement,
      reason: rule.reason,
      channel: rule.channel,
      severity: rule.severity,
    });
  }

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto pb-6">
      <PageHeader
        title="Brand rules"
        description="A rule is a draft until someone else approves it. Only approved rules are checked. Retiring a rule is final."
        actions={
          <button
            type="button"
            onClick={() => {
              setCreating((open) => !open);
              setNotice(null);
            }}
            className="focus-ring inline-flex h-9 items-center gap-2 rounded-lg bg-[#2F5BEA] px-3 text-xs font-semibold text-white hover:bg-blue-700"
          >
            <Plus size={14} aria-hidden="true" />
            New rule
          </button>
        }
      />

      {notice && (
        <div
          role={notice.tone === "error" ? "alert" : "status"}
          className={cn(
            "flex items-start justify-between gap-2 rounded-lg border p-3 text-xs",
            notice.tone === "error" ? "border-red-100 bg-red-50 text-red-700" : "border-emerald-100 bg-emerald-50 text-emerald-800",
          )}
        >
          <span>{notice.text}</span>
          <button onClick={() => setNotice(null)} aria-label="Dismiss" className="shrink-0">
            <X size={14} aria-hidden="true" />
          </button>
        </div>
      )}

      {creating && (
        <form onSubmit={submitNew} className="grid gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:grid-cols-2">
          <label className="text-[11px] font-medium text-slate-600">
            Title
            <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="mt-1 h-9 w-full rounded-lg border border-slate-200 px-2 text-xs" />
          </label>
          <label className="text-[11px] font-medium text-slate-600">
            Kind
            <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as BrandRuleKind })} className="mt-1 h-9 w-full rounded-lg border border-slate-200 bg-white px-2 text-xs">
              <option value="phrase">Banned phrase</option>
              <option value="regex">Pattern (regex)</option>
              <option value="name_variant">Name variant</option>
              <option value="required_text">Required text</option>
            </select>
            <span className="mt-1 block text-[10px] font-normal text-slate-500">{KIND_HELP[form.kind]}</span>
          </label>
          <label className="text-[11px] font-medium text-slate-600 sm:col-span-2">
            Text to match
            <input value={form.pattern} onChange={(e) => setForm({ ...form, pattern: e.target.value })} className="mt-1 h-9 w-full rounded-lg border border-slate-200 px-2 font-mono text-xs" />
          </label>
          <label className="text-[11px] font-medium text-slate-600">
            Use instead
            <input value={form.replacement ?? ""} onChange={(e) => setForm({ ...form, replacement: e.target.value })} className="mt-1 h-9 w-full rounded-lg border border-slate-200 px-2 text-xs" />
          </label>
          <label className="text-[11px] font-medium text-slate-600">
            Reason
            <input value={form.reason ?? ""} onChange={(e) => setForm({ ...form, reason: e.target.value })} className="mt-1 h-9 w-full rounded-lg border border-slate-200 px-2 text-xs" />
          </label>
          <label className="text-[11px] font-medium text-slate-600">
            Channel
            <select value={form.channel ?? ""} onChange={(e) => setForm({ ...form, channel: (e.target.value || null) as BrandRuleChannel | null })} className="mt-1 h-9 w-full rounded-lg border border-slate-200 bg-white px-2 text-xs">
              <option value="">All channels</option>
              <option value="Website">Website</option>
              <option value="Instagram">Instagram</option>
              <option value="Email">Email</option>
              <option value="Ad">Ad</option>
            </select>
          </label>
          <label className="text-[11px] font-medium text-slate-600">
            Severity
            <select value={form.severity} onChange={(e) => setForm({ ...form, severity: e.target.value as BrandRuleSeverity })} className="mt-1 h-9 w-full rounded-lg border border-slate-200 bg-white px-2 text-xs">
              <option value="critical">Critical</option>
              <option value="warning">Warning</option>
              <option value="info">Info</option>
            </select>
          </label>
          <div className="flex gap-2 sm:col-span-2">
            <button type="submit" disabled={busyId !== null} className="focus-ring h-9 rounded-lg bg-[#2F5BEA] px-3 text-xs font-semibold text-white disabled:opacity-50">Save draft</button>
            <button type="button" onClick={() => setCreating(false)} className="focus-ring h-9 rounded-lg border border-slate-200 px-3 text-xs font-semibold text-slate-600">Cancel</button>
          </div>
        </form>
      )}

      <div role="tablist" aria-label="Filter by status" className="flex flex-wrap gap-2">
        {STATUS_FILTERS.map((item) => (
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
            {item.label} <span className="ml-1 text-slate-400">{counts[item.value === "all" ? "all" : item.value]}</span>
          </button>
        ))}
      </div>

      {loadError ? (
        <ErrorState description={loadError} onRetry={() => void load()} />
      ) : rules === null ? (
        <LoadingState label="Loading brand rules" rows={4} />
      ) : visible.length === 0 ? (
        <EmptyState title="No rules here" description="Create a rule, or change the filter to see rules in other states." />
      ) : (
        <ul className="space-y-2">
          {visible.map((rule) => {
            const isOwnRule = rule.createdBy === currentUserId;
            return (
              <li key={rule.id} className="rounded-xl border border-slate-200 bg-white p-4">
                {editingId === rule.id ? (
                  <div className="grid gap-3 sm:grid-cols-2">
                    <label className="text-[11px] font-medium text-slate-600">
                      Title
                      <input value={editDraft.title} onChange={(e) => setEditDraft({ ...editDraft, title: e.target.value })} className="mt-1 h-9 w-full rounded-lg border border-slate-200 px-2 text-xs" />
                    </label>
                    <label className="text-[11px] font-medium text-slate-600">
                      Text to match
                      <input value={editDraft.pattern} onChange={(e) => setEditDraft({ ...editDraft, pattern: e.target.value })} className="mt-1 h-9 w-full rounded-lg border border-slate-200 px-2 font-mono text-xs" />
                    </label>
                    <label className="text-[11px] font-medium text-slate-600">
                      Use instead
                      <input value={editDraft.replacement ?? ""} onChange={(e) => setEditDraft({ ...editDraft, replacement: e.target.value })} className="mt-1 h-9 w-full rounded-lg border border-slate-200 px-2 text-xs" />
                    </label>
                    <label className="text-[11px] font-medium text-slate-600">
                      Reason
                      <input value={editDraft.reason ?? ""} onChange={(e) => setEditDraft({ ...editDraft, reason: e.target.value })} className="mt-1 h-9 w-full rounded-lg border border-slate-200 px-2 text-xs" />
                    </label>
                    <div className="flex gap-2 sm:col-span-2">
                      <button type="button" disabled={busyId !== null} onClick={() => saveEdit(rule)} className="focus-ring h-8 rounded-md bg-[#2F5BEA] px-3 text-[11px] font-semibold text-white disabled:opacity-50">Save</button>
                      <button type="button" onClick={() => setEditingId(null)} className="focus-ring h-8 rounded-md border border-slate-200 px-3 text-[11px] font-semibold text-slate-600">Cancel</button>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-[10px] font-mono text-slate-400">{rule.id}</span>
                        <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-semibold capitalize", STATUS_STYLE[rule.status])}>{rule.status}</span>
                        <span className="text-[11px] text-slate-500">{rule.kind.replace("_", " ")} · {rule.channel ?? "All channels"} · {rule.severity}</span>
                      </div>
                      <h3 className="mt-1 text-xs font-semibold text-slate-800">{rule.title}</h3>
                      <p className="mt-0.5 font-mono text-[11px] text-slate-600">{rule.pattern}{rule.replacement && <span className="font-sans text-slate-500"> → {rule.replacement}</span>}</p>
                      {rule.reason && <p className="mt-0.5 text-[11px] text-slate-500">{rule.reason}</p>}
                      <p className="mt-1 text-[10px] text-slate-400">
                        Created by {rule.createdBy}
                        {rule.approvedBy && <> · approved by {rule.approvedBy}</>}
                      </p>
                    </div>
                    <div className="flex shrink-0 flex-wrap gap-2">
                      {rule.status === "draft" && (
                        <>
                          <button type="button" onClick={() => startEdit(rule)} disabled={busyId !== null} className="focus-ring inline-flex h-8 items-center gap-1.5 rounded-md border border-slate-200 px-2.5 text-[11px] font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-50">
                            <Pencil size={12} aria-hidden="true" /> Edit
                          </button>
                          <button
                            type="button"
                            disabled={busyId !== null || isOwnRule}
                            title={isOwnRule ? "You created this rule. Another manager must approve it." : undefined}
                            onClick={() => void run(rule.id, () => approveBrandRule(rule.id), "Rule approved. It is now checked.")}
                            className="focus-ring inline-flex h-8 items-center gap-1.5 rounded-md bg-emerald-600 px-2.5 text-[11px] font-semibold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            <Check size={12} aria-hidden="true" /> Approve
                          </button>
                        </>
                      )}
                      {rule.status === "approved" && (
                        <button
                          type="button"
                          disabled={busyId !== null}
                          onClick={() => {
                            if (window.confirm("Retire this rule? It will stop being checked, and retiring cannot be undone.")) {
                              void run(rule.id, () => retireBrandRule(rule.id), "Rule retired. It is no longer checked.");
                            }
                          }}
                          className="focus-ring inline-flex h-8 items-center gap-1.5 rounded-md border border-red-200 px-2.5 text-[11px] font-semibold text-red-700 hover:bg-red-50 disabled:opacity-50"
                        >
                          <Undo2 size={12} aria-hidden="true" /> Retire
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
