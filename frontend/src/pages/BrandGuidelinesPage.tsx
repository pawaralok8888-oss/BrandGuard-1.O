
import { SHOW_DEV_TOOLS } from "@/lib/devTools";
import type { UserRole } from "@/types";
import { DraftRulesPanel, type UploadSummary } from "@/components/guidelines/DraftRulesPanel";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  getGuidelines,
  getGuidelineVersions,
  getGlossary,
  getGuidelineCategories,
  uploadGuidelinesFile,
  type GuidelineCategoryName,
  type GuidelineItem,
  type GuidelineVersionItem,
  type GlossaryItem,
} from "@/api/knowledge";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock3,
  Copy,
  FileText,
  FileUp,
  Filter,
  History,
  Image as ImageIcon,
  Info,
  Loader2,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  Type,
  Upload,
  X,
  XCircle,
} from "lucide-react";

type Tab = "Rules" | "Drafts" | "Glossary" | "Brand Assets" | "Upload";

const UPLOAD_LIMIT_MB = { text: 1, binary: 10 } as const;
type Severity = "Critical" | "High" | "Medium" | "Low";
type Rule = {
  id: string;
  rule: string;
  severity: Severity;
  category: string;
  version: string;
  rejectionRate: number;
  updated: string;
  history: { version: string; date: string; change: string; author: string }[];
};

type Term = {
  id: string;
  approved: string;
  avoid: string[];
  note: string;
};

const initialRules: Rule[] = [];

const initialTerms: Term[] = [];

const initialLogos = [
  { name: "Primary logo", version: "v3.2", status: "Approved", kind: "primary" },
  { name: "White logo", version: "v2.1", status: "Approved", kind: "white" },
  { name: "Legacy logo", version: "v1.4", status: "Outdated", kind: "legacy" },
];

const initialColors = [
  { name: "Brand blue", hex: "#2F5BEA" },
  { name: "Deep navy", hex: "#14213D" },
  { name: "Success green", hex: "#16845B" },
  { name: "Soft background", hex: "#F6F8FC" },
  { name: "Body text", hex: "#344054" },
];

const initialFonts = [
  { name: "Inter", usage: "Primary font", sample: "Clear ideas. Consistent experiences." },
  { name: "Georgia", usage: "Editorial accent", sample: "Built on trust, designed for people." },
];

const categories = [
  "All categories",
  "Terminology",
  "Claims & Legal",
  "Tone of Voice",
  "Formatting",
  "Accessibility",
];

const severityClasses: Record<Severity, string> = {
  Critical: "bg-red-50 text-red-700 ring-red-200",
  High: "bg-orange-50 text-orange-700 ring-orange-200",
  Medium: "bg-amber-50 text-amber-700 ring-amber-200",
  Low: "bg-slate-100 text-slate-600 ring-slate-200",
};

function SeverityPill({ severity }: { severity: Severity }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-1 text-[11px] font-semibold ring-1 ring-inset ${severityClasses[severity]}`}
    >
      {severity}
    </span>
  );
}

function EmptyState({
  title,
  description,
  action,
  onAction,
}: {
  title: string;
  description: string;
  action: string;
  onAction: () => void;
}) {
  return (
    <div className="flex min-h-[280px] flex-col items-center justify-center px-6 py-10 text-center">
      <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100 text-slate-500">
        <FileText size={22} />
      </div>
      <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
      <p className="mt-1 max-w-sm text-xs leading-5 text-slate-500">{description}</p>
      <button
        onClick={onAction}
        className="mt-4 inline-flex h-9 items-center gap-2 rounded-lg bg-[#2F5BEA] px-3 text-xs font-semibold text-white transition hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2"
      >
        <Plus size={15} />
        {action}
      </button>
    </div>
  );
}

function SkeletonRows() {
  return (
    <div className="animate-pulse space-y-3 p-4" aria-label="Loading brand guidelines">
      {Array.from({ length: 5 }).map((_, index) => (
        <div key={index} className="grid grid-cols-12 items-center gap-4 border-b border-slate-100 pb-4">
          <div className="col-span-1 h-3 rounded bg-slate-200" />
          <div className="col-span-5 h-3 rounded bg-slate-200" />
          <div className="col-span-2 h-5 rounded-full bg-slate-200" />
          <div className="col-span-2 h-3 rounded bg-slate-200" />
          <div className="col-span-2 h-3 rounded bg-slate-200" />
        </div>
      ))}
    </div>
  );
}

export default function BrandGuidelinesPage({ role }: { role: UserRole }) {
  // Uploading guidelines and reviewing their draft rules are for managers and admins.
  const canEdit = role === "manager" || role === "admin";
  const [activeTab, setActiveTab] = useState<Tab>("Rules");
  const [rules, setRules] = useState<Rule[]>(initialRules);
  const [terms, setTerms] = useState<Term[]>(initialTerms);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("All categories");
  const [selectedRule, setSelectedRule] = useState<Rule | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [newRuleOpen, setNewRuleOpen] = useState(false);
  const [newTermOpen, setNewTermOpen] = useState(false);
  const [ruleDraft, setRuleDraft] = useState("");
  const [ruleSeverity, setRuleSeverity] = useState<Severity>("Medium");
  const [ruleCategory, setRuleCategory] = useState("Tone of Voice");
  const [termDraft, setTermDraft] = useState("");
  const [avoidDraft, setAvoidDraft] = useState("");
  const [noteDraft, setNoteDraft] = useState("");
  const [suggestionDismissed, setSuggestionDismissed] = useState(false);
  const [toast, setToast] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [emptyMode, setEmptyMode] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadCategory, setUploadCategory] = useState<GuidelineCategoryName>("");
  const [categories, setCategories] = useState<string[]>([]);
  const [uploadSummary, setUploadSummary] = useState<UploadSummary | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const [uploadError, setUploadError] = useState("");

  async function loadGuidelinesData() {
    setLoading(true);
    setError(false);
    try {
      const [apiGuidelines, apiGlossary] = await Promise.all([
        getGuidelines(),
        getGlossary().catch(() => []),
      ]);
      const mappedRules: Rule[] = apiGuidelines.map((g) => ({
        id: g.id,
        rule: g.text || g.title,
        severity: (g.severity.charAt(0).toUpperCase() + g.severity.slice(1).toLowerCase()) as Severity,
        category: g.category,
        version: `v${g.version}.0`,
        rejectionRate: 0,
        updated: g.updatedAt
          ? new Date(g.updatedAt).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
          : "Active",
        history: [],
      }));
      setRules(mappedRules);
      const mappedTerms: Term[] = apiGlossary.map((t) => ({
        id: t.id,
        approved: t.approvedTerm,
        avoid: t.avoidTerms || [],
        note: t.explanation || "",
      }));
      setTerms(mappedTerms);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadGuidelinesData();
  }, []);

  // Load the category list from the server, and default the upload to the first one.
  useEffect(() => {
    if (!canEdit) return;
    getGuidelineCategories()
      .then((list) => {
        setCategories(list);
        setUploadCategory((current) => current || list[0] || "");
      })
      .catch(() => setToast("Could not load guideline categories."));
  }, [canEdit]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 4000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const filteredRules = rules.filter((rule) => {
    const matchesSearch =
      `${rule.id} ${rule.rule} ${rule.category}`.toLowerCase().includes(search.toLowerCase());
    const matchesCategory = category === "All categories" || rule.category === category;
    return matchesSearch && matchesCategory;
  });

  async function openRule(rule: Rule) {
    setSelectedRule({ ...rule });
    setRuleDraft(rule.rule);
    setRuleSeverity(rule.severity);
    setRuleCategory(rule.category);
    setDrawerOpen(true);
    try {
      const versions = await getGuidelineVersions(rule.id);
      setSelectedRule((current) => {
        if (!current || current.id !== rule.id) return current;
        return {
          ...current,
          history: versions.map((v) => ({
            version: `v${v.version}.0`,
            date: v.changedAt
              ? new Date(v.changedAt).toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                  year: "numeric",
                })
              : "",
            change: v.changeNote || "Guideline policy version",
            author: v.changedByName || v.changedBy || "Manager",
          })),
        };
      });
    } catch {
      // keep existing
    }
  }

  function saveRule() {
    if (!selectedRule || !ruleDraft.trim()) return;
    setRules((current) =>
      current.map((rule) =>
        rule.id === selectedRule.id
          ? {
              ...rule,
              rule: ruleDraft.trim(),
              severity: ruleSeverity,
              category: ruleCategory,
              version: `v${Number(rule.version.replace("v", "").split(".")[0]) + 1}.0`,
              updated: "Oct 25, 2026",
              history: [
                {
                  version: `v${Number(rule.version.replace("v", "").split(".")[0]) + 1}.0`,
                  date: "Oct 25, 2026",
                  change: "Rule updated.",
                  author: "You",
                },
                ...rule.history,
              ],
            }
          : rule
      )
    );
    setDrawerOpen(false);
    setToast("Rule updated successfully.");
  }

  function addRule() {
    if (!ruleDraft.trim()) return;
    const rule: Rule = {
      id: `R-${String(rules.length + 1).padStart(3, "0")}`,
      rule: ruleDraft.trim(),
      severity: ruleSeverity,
      category: ruleCategory,
      version: "v1.0",
      rejectionRate: 0,
      updated: "Oct 25, 2026",
      history: [
        { version: "v1.0", date: "Oct 25, 2026", change: "Rule created.", author: "You" },
      ],
    };
    setRules((current) => [rule, ...current]);
    setNewRuleOpen(false);
    setRuleDraft("");
    setToast("New rule added.");
  }

  function addTerm() {
    if (!termDraft.trim()) return;
    setTerms((current) => [
      ...current,
      {
        id: `G-${String(current.length + 1).padStart(3, "0")}`,
        approved: termDraft.trim(),
        avoid: avoidDraft.split(",").map((word) => word.trim()).filter(Boolean),
        note: noteDraft.trim() || "No additional guidance added.",
      },
    ]);
    setNewTermOpen(false);
    setTermDraft("");
    setAvoidDraft("");
    setNoteDraft("");
    setToast("Glossary term added.");
  }

  function applySuggestion() {
    const target = rules.find((rule) => rule.id === "R-002");
    if (!target) return;
    setRules((current) =>
      current.map((rule) =>
        rule.id === "R-002"
          ? {
              ...rule,
              rule: "Only make claims supported by approved evidence. Never guarantee results.",
              version: "v3.2",
              updated: "Oct 25, 2026",
              history: [
                {
                  version: "v3.2",
                  date: "Oct 25, 2026",
                  change: "Clarified following rejection feedback.",
                  author: "You",
                },
                ...rule.history,
              ],
            }
          : rule
      )
    );
    setSuggestionDismissed(true);
    setToast("Suggested wording applied.");
  }

  async function startUpload(file?: File) {
    if (!file) return;
    if (!uploadCategory) {
      setToast("Categories are still loading. Try again in a moment.");
      return;
    }
    const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
    if (!["txt", "md", "pdf", "docx"].includes(extension)) {
      setToast("Please choose a .txt, .md, .pdf or .docx file.");
      return;
    }
    const limitMb = ["pdf", "docx"].includes(extension) ? UPLOAD_LIMIT_MB.binary : UPLOAD_LIMIT_MB.text;
    if (file.size > limitMb * 1024 * 1024) {
      setToast(`That file is larger than ${limitMb} MB.`);
      return;
    }
    setUploadFile(file);
    setUploadError("");
    setUploadSummary(null);
    setUploading(true);
    try {
      const saved = await uploadGuidelinesFile(file, uploadCategory);
      setUploadSummary({
        guideline: saved.shortName || saved.title,
        ruleCandidates: saved.ruleCandidates,
        unparsedLines: saved.unparsedLines,
      });
      setUploadFile(null);
      setToast(
        saved.ruleCandidates > 0
          ? `Guideline saved. ${saved.ruleCandidates} draft ${saved.ruleCandidates === 1 ? "rule" : "rules"} ready to review.`
          : "Guideline saved. No rules could be drafted from it; see the lines listed below.",
      );
      await loadGuidelinesData();
      setActiveTab("Drafts");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Upload failed. Please check the server logs.";
      setUploadError(message);
      setToast(message);
    } finally {
      setUploading(false);
    }
  }

  const tabs: Tab[] = canEdit
    ? ["Rules", "Drafts", "Glossary", "Brand Assets", "Upload"]
    : ["Rules", "Glossary", "Brand Assets"];

  return (
    <div className="min-h-screen bg-[#F6F8FC] text-[#14213D]">
      <div className="mx-auto max-w-[1600px] px-5 py-5 lg:px-7">
        <header className="mb-5 flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
          <div>
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-50 text-[#2F5BEA]">
                <ShieldCheck size={17} />
              </div>
              <h1 className="text-[18px] font-semibold tracking-[-0.02em]">Brand Guidelines</h1>
            </div>
            <p className="mt-1 pl-10 text-[12px] text-slate-500">
              Manage the rules, language, and assets that keep your brand consistent.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1.5 text-[11px] font-medium text-emerald-700">
              <CheckCircle2 size={13} />
              Guidelines active
            </span>
          </div>
        </header>

        <div className="mb-4 flex gap-1 overflow-x-auto border-b border-slate-200" role="tablist" aria-label="Brand guideline sections">
          {tabs.map((tab) => (
            <button
              key={tab}
              role="tab"
              aria-selected={activeTab === tab}
              onClick={() => setActiveTab(tab)}
              className={`relative -mb-px whitespace-nowrap px-4 py-3 text-xs font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${
                activeTab === tab
                  ? "border-b-2 border-[#2F5BEA] text-[#2F5BEA]"
                  : "border-b-2 border-transparent text-slate-500 hover:text-slate-800"
              }`}
            >
              {tab}
              {tab === "Rules" && (
                <span className={`ml-2 rounded-full px-1.5 py-0.5 text-[10px] ${activeTab === tab ? "bg-blue-50 text-blue-700" : "bg-slate-100 text-slate-500"}`}>
                  {rules.length}
                </span>
              )}
            </button>
          ))}
        </div>

        {error ? (
          <section className="rounded-xl border border-red-200 bg-white p-10 text-center shadow-sm">
            <AlertCircle className="mx-auto mb-3 text-red-500" size={28} />
            <h2 className="text-sm font-semibold text-slate-800">Couldn't load brand guidelines</h2>
            <p className="mt-1 text-xs text-slate-500">Something went wrong while loading this section.</p>
            <button
              onClick={() => {
                setError(false);
                setLoading(true);
                window.setTimeout(() => setLoading(false), 600);
              }}
              className="mt-4 h-9 rounded-lg bg-[#2F5BEA] px-4 text-xs font-semibold text-white hover:bg-blue-700"
            >
              Try again
            </button>
          </section>
        ) : (
          <>
            {activeTab === "Rules" && (
              <section>
                <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
                  <div className="rounded-xl border border-[#E3E8F2] bg-white p-3.5">
                    <div className="flex items-center justify-between">
                      <p className="text-xs text-slate-500">Total rules</p>
                      <FileText size={16} className="text-slate-400" />
                    </div>
                    <div className="mt-1.5 flex items-baseline gap-2">
                      <span className="text-[22px] font-semibold">{rules.length}</span>
                      <span className="text-[11px] text-slate-500">approved rules</span>
                    </div>
                  </div>
                  <div className="rounded-xl border border-[#E3E8F2] bg-white p-3.5">
                    <div className="flex items-center justify-between">
                      <p className="text-xs text-slate-500">Critical / high severity</p>
                      <AlertTriangle size={16} className="text-orange-500" />
                    </div>
                    <div className="mt-1.5 flex items-baseline gap-2">
                      <span className="text-[22px] font-semibold">{rules.filter((r) => r.severity === "Critical" || r.severity === "High").length}</span>
                      <span className="text-[11px] text-slate-500">need close attention</span>
                    </div>
                  </div>
                  <div className="rounded-xl border border-[#E3E8F2] bg-white p-3.5">
                    <div className="flex items-center justify-between">
                      <p className="text-xs text-slate-500">Glossary terms</p>
                      <Type size={16} className="text-slate-400" />
                    </div>
                    <div className="mt-1.5 flex items-baseline gap-2">
                      <span className="text-[22px] font-semibold">{terms.length}</span>
                      <span className="text-[11px] text-slate-500">approved terms</span>
                    </div>
                  </div>
                </div>

                {!suggestionDismissed && rules.some((r) => r.id === "R-002") && (
                  <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50/70 p-4">
                    <div className="mb-3 flex items-start gap-2.5">
                      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-amber-100 text-amber-700">
                        <Sparkles size={15} />
                      </div>
                      <div className="min-w-0 flex-1">
                        <h2 className="text-xs font-semibold text-amber-950">
                          This rule is rejected 40% of the time — people may find it unclear
                        </h2>
                        <p className="mt-1 text-[11px] leading-4 text-amber-800">
                          Based on content review feedback, a more specific instruction may be easier to follow.
                        </p>
                      </div>
                      <button
                        aria-label="Dismiss wording suggestion"
                        onClick={() => setSuggestionDismissed(true)}
                        className="rounded-md p-1 text-amber-700 hover:bg-amber-100 focus:outline-none focus:ring-2 focus:ring-amber-400"
                      >
                        <X size={15} />
                      </button>
                    </div>
                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="rounded-lg border border-amber-200 bg-white p-3">
                        <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-wide text-slate-400">Current wording</div>
                        <p className="text-xs leading-5 text-slate-600">
                          {rules.find((r) => r.id === "R-002")?.rule}
                        </p>
                      </div>
                      <div className="rounded-lg border border-emerald-200 bg-white p-3">
                        <div className="mb-1.5 flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-emerald-700">
                          <CheckCircle2 size={12} /> Suggested wording
                        </div>
                        <p className="text-xs leading-5 text-slate-700">
                          Only make claims supported by approved evidence. Never guarantee results.
                        </p>
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap items-center justify-end gap-2">
                      <button
                        onClick={() => setSuggestionDismissed(true)}
                        className="h-8 rounded-lg px-3 text-xs font-medium text-slate-600 hover:bg-amber-100 focus:outline-none focus:ring-2 focus:ring-amber-400"
                      >
                        Dismiss
                      </button>
                      <button
                        onClick={applySuggestion}
                        className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-[#2F5BEA] px-3 text-xs font-semibold text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2"
                      >
                        <Check size={13} />
                        Use suggestion
                      </button>
                    </div>
                  </div>
                )}

                <div className="overflow-hidden rounded-xl border border-[#E3E8F2] bg-white shadow-sm">
                  <div className="flex flex-col gap-3 border-b border-slate-100 p-4 md:flex-row md:items-center md:justify-between">
                    <div>
                      <h2 className="text-sm font-semibold">Brand rules</h2>
                      <p className="mt-0.5 text-[11px] text-slate-500">Review and maintain approved content rules.</p>
                    </div>
                    <button
                      onClick={() => {
                        setRuleDraft("");
                        setRuleSeverity("Medium");
                        setRuleCategory("Tone of Voice");
                        setNewRuleOpen(true);
                      }}
                      className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg bg-[#2F5BEA] px-3 text-xs font-semibold text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2"
                    >
                      <Plus size={15} />
                      Add rule
                    </button>
                  </div>
                  <div className="flex flex-col gap-2 border-b border-slate-100 p-3 sm:flex-row">
                    <div className="relative min-w-0 flex-1">
                      <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                      <input
                        value={search}
                        onChange={(event) => setSearch(event.target.value)}
                        placeholder="Search rules..."
                        aria-label="Search rules"
                        className="h-9 w-full rounded-lg border border-slate-200 bg-white pl-9 pr-3 text-xs outline-none transition placeholder:text-slate-400 focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
                      />
                    </div>
                    <div className="relative sm:w-48">
                      <Filter size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                      <select
                        value={category}
                        onChange={(event) => setCategory(event.target.value)}
                        aria-label="Filter by category"
                        className="h-9 w-full appearance-none rounded-lg border border-slate-200 bg-white pl-9 pr-8 text-xs text-slate-700 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
                      >
                        {categories.map((item) => <option key={item}>{item}</option>)}
                      </select>
                      <ChevronDown size={13} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    </div>
                  </div>

                  {loading ? (
                    <SkeletonRows />
                  ) : emptyMode || filteredRules.length === 0 ? (
                    <EmptyState
                      title={emptyMode ? "No rules yet" : "No matching rules"}
                      description={emptyMode ? "Add your first approved brand rule to help everyone create consistent content." : "Try another search term or category, or add a new rule."}
                      action="Add rule"
                      onAction={() => {
                        setEmptyMode(false);
                        setRuleDraft("");
                        setNewRuleOpen(true);
                      }}
                    />
                  ) : (
                    <>
                      <div className="overflow-x-auto">
                        <table className="w-full min-w-[760px] border-collapse text-left">
                          <thead>
                            <tr className="bg-slate-50/80 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                              <th className="px-4 py-3 font-semibold">ID</th>
                              <th className="px-4 py-3 font-semibold">Rule</th>
                              <th className="px-4 py-3 font-semibold">Severity</th>
                              <th className="px-4 py-3 font-semibold">Category</th>
                              <th className="px-4 py-3 font-semibold">Version</th>
                              <th className="px-4 py-3 font-semibold">Rejection rate</th>
                              <th className="w-9 px-2 py-3" />
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100">
                            {filteredRules.map((rule) => (
                              <tr
                                key={rule.id}
                                onClick={() => openRule(rule)}
                                tabIndex={0}
                                onKeyDown={(event) => {
                                  if (event.key === "Enter" || event.key === " ") {
                                    event.preventDefault();
                                    openRule(rule);
                                  }
                                }}
                                className="group cursor-pointer transition hover:bg-blue-50/40 focus:outline-none focus-visible:bg-blue-50/50"
                              >
                                <td className="whitespace-nowrap px-4 py-3.5 font-mono text-[11px] text-slate-500">{rule.id}</td>
                                <td className="max-w-[360px] px-4 py-3.5">
                                  <p className="truncate text-xs font-medium text-slate-800">{rule.rule}</p>
                                </td>
                                <td className="px-4 py-3.5"><SeverityPill severity={rule.severity} /></td>
                                <td className="whitespace-nowrap px-4 py-3.5 text-[11px] text-slate-600">{rule.category}</td>
                                <td className="px-4 py-3.5 font-mono text-[11px] text-slate-500">{rule.version}</td>
                                <td className="px-4 py-3.5">
                                  <div className="flex items-center gap-2">
                                    <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-100">
                                      <div
                                        className={`h-full rounded-full ${rule.rejectionRate >= 30 ? "bg-amber-500" : "bg-[#2F5BEA]"}`}
                                        style={{ width: `${rule.rejectionRate}%` }}
                                      />
                                    </div>
                                    <span className={`text-[11px] tabular-nums ${rule.rejectionRate >= 30 ? "font-semibold text-amber-700" : "text-slate-500"}`}>
                                      {rule.rejectionRate}%
                                    </span>
                                  </div>
                                </td>
                                <td className="px-2 py-3.5 text-right">
                                  <button
                                    aria-label={`Edit ${rule.id}`}
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      openRule(rule);
                                    }}
                                    className="rounded-md p-1.5 text-slate-400 opacity-0 transition hover:bg-white hover:text-[#2F5BEA] group-hover:opacity-100 group-focus-within:opacity-100 focus:opacity-100 focus:outline-none focus:ring-2 focus:ring-blue-400"
                                  >
                                    <ChevronRight size={15} />
                                  </button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 px-4 py-3">
                        <p className="text-[11px] text-slate-500">Showing {filteredRules.length} of {rules.length} rules</p>
                        {SHOW_DEV_TOOLS && (
                          <button
                            onClick={() => setError(true)}
                            className="text-[10px] text-slate-400 underline decoration-dotted underline-offset-2 hover:text-slate-600"
                          >
                            Simulate load error
                          </button>
                        )}
                      </div>
                    </>
                  )}
                </div>
              </section>
            )}

            {activeTab === "Drafts" && (
              <DraftRulesPanel summary={uploadSummary} onChanged={() => void loadGuidelinesData()} />
            )}
            {activeTab === "Glossary" && (
              <section className="overflow-hidden rounded-xl border border-[#E3E8F2] bg-white shadow-sm">
                <div className="flex flex-col gap-3 border-b border-slate-100 p-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h2 className="text-sm font-semibold">Approved glossary</h2>
                    <p className="mt-1 text-[11px] text-slate-500">Use consistent language across all content and channels.</p>
                  </div>
                  <button
                    onClick={() => setNewTermOpen(true)}
                    className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg bg-[#2F5BEA] px-3 text-xs font-semibold text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2"
                  >
                    <Plus size={15} />
                    Add term
                  </button>
                </div>
                <div className="grid grid-cols-1 gap-3 p-4 xl:grid-cols-2">
                  {loading ? (
                    <div className="col-span-full"><SkeletonRows /></div>
                  ) : emptyMode || terms.length === 0 ? (
                    <div className="col-span-full">
                      <EmptyState
                        title="No glossary terms yet"
                        description="Add an approved term and its banned variants to keep language consistent."
                        action="Add term"
                        onAction={() => {
                          setEmptyMode(false);
                          setNewTermOpen(true);
                        }}
                      />
                    </div>
                  ) : terms.map((term) => (
                    <article key={term.id} className="rounded-xl border border-slate-200 p-4 transition hover:border-slate-300">
                      <div className="mb-3 flex items-start justify-between gap-2">
                        <span className="font-mono text-[10px] text-slate-400">{term.id}</span>
                        <button
                          aria-label={`Remove glossary term ${term.approved}`}
                          onClick={() => {
                            setTerms((current) => current.filter((item) => item.id !== term.id));
                            setToast("Glossary term removed.");
                          }}
                          className="rounded-md p-1 text-slate-400 hover:bg-red-50 hover:text-red-600 focus:outline-none focus:ring-2 focus:ring-blue-400"
                        >
                          <X size={14} />
                        </button>
                      </div>
                      <div className="grid gap-4 sm:grid-cols-2">
                        <div>
                          <p className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-700">
                            <CheckCircle2 size={13} />
                            Use this
                          </p>
                          <div className="inline-flex max-w-full items-center gap-1.5 rounded-lg border border-emerald-200 bg-emerald-50 px-2.5 py-2 text-xs font-semibold text-emerald-800">
                            <Check size={13} />
                            <span className="break-words">{term.approved}</span>
                          </div>
                        </div>
                        <div>
                          <p className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-red-700">
                            <XCircle size={13} />
                            Avoid this
                          </p>
                          <div className="flex flex-wrap gap-1.5">
                            {term.avoid.length ? term.avoid.map((variant) => (
                              <span key={variant} className="rounded-md border border-red-100 bg-red-50 px-2 py-1 text-[10px] text-red-700">
                                {variant}
                              </span>
                            )) : <span className="text-[11px] text-slate-400">No banned variants</span>}
                          </div>
                        </div>
                      </div>
                      <div className="mt-4 flex items-start gap-2 rounded-lg bg-slate-50 p-2.5">
                        <Info size={13} className="mt-0.5 shrink-0 text-slate-400" />
                        <p className="text-[11px] leading-4 text-slate-600">{term.note}</p>
                      </div>
                    </article>
                  ))}
                </div>
                <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3">
                  <span className="text-[11px] text-slate-500">{terms.length} approved terms</span>
                  {SHOW_DEV_TOOLS && (
                    <button onClick={() => setError(true)} className="text-[10px] text-slate-400 underline decoration-dotted underline-offset-2 hover:text-slate-600">
                      Simulate load error
                    </button>
                  )}
                </div>
              </section>
            )}

            {activeTab === "Brand Assets" && (
              <div className="space-y-4">
                <section className="overflow-hidden rounded-xl border border-[#E3E8F2] bg-white shadow-sm">
                  <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3.5">
                    <div>
                      <h2 className="text-sm font-semibold">Logos</h2>
                      <p className="mt-1 text-[11px] text-slate-500">Use approved logo files for all branded materials.</p>
                    </div>
                    <button
                    onClick={() => setToast("Brand assets are added on the Brand Intake page.")}
                      
                      className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-slate-200 px-3 text-xs font-medium text-slate-600 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-400"
                    >
                      <Plus size={14} />
                      Add asset
                    </button>
                  </div>
                  {loading ? <SkeletonRows /> : emptyMode ? (
                    <EmptyState
                      title="No logos yet"
                      description="Upload approved logo files to make them available to your team."
                      action="Go to Brand Intake"
                      onAction={() => navigate("/intake")}
                    />
                  ) : (
                    <div className="grid grid-cols-1 gap-3 p-4 sm:grid-cols-2 xl:grid-cols-3">
                      {initialLogos.map((logo) => (
                        <article key={logo.name} className="overflow-hidden rounded-xl border border-slate-200">
                          <div className={`relative flex h-28 items-center justify-center ${logo.kind === "white" ? "bg-[#14213D]" : "bg-slate-50"}`}>
                            {logo.kind === "legacy" && (
                              <span className="absolute right-2 top-2 rounded-md bg-slate-200 px-2 py-1 text-[9px] font-semibold text-slate-600">
                                DO NOT USE
                              </span>
                            )}
                            <div className={`flex items-center gap-2 ${logo.kind === "white" ? "text-white" : logo.kind === "legacy" ? "text-slate-400" : "text-[#2F5BEA"}`}>
                              <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${logo.kind === "white" ? "bg-white/15" : "bg-blue-50"}`}>
                                <ShieldCheck size={23} />
                              </div>
                              <span className="text-lg font-bold tracking-tight">BrandGuard</span>
                            </div>
                            {logo.kind === "legacy" && <div className="absolute inset-0 bg-white/15" />}
                          </div>
                          <div className="p-3">
                            <div className="flex items-start justify-between gap-2">
                              <div>
                                <p className="text-xs font-semibold text-slate-800">{logo.name}</p>
                                <p className="mt-1 text-[10px] text-slate-500">Version {logo.version}</p>
                              </div>
                              <span className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-[10px] font-medium ${logo.status === "Approved" ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>
                                {logo.status === "Approved" ? <CheckCircle2 size={12} /> : <Clock3 size={12} />}
                                {logo.status}
                              </span>
                            </div>
                            <button
                              onClick={() => setToast(logo.status === "Approved" ? `${logo.name} is approved for use.` : "This legacy logo should not be used in new content.")}
                              className="mt-3 inline-flex h-8 w-full items-center justify-center gap-1.5 rounded-lg border border-slate-200 text-[11px] font-medium text-slate-600 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-400"
                            >
                              <ImageIcon size={13} />
                              View asset details
                            </button>
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                </section>

                <section className="overflow-hidden rounded-xl border border-[#E3E8F2] bg-white shadow-sm">
                  <div className="border-b border-slate-100 px-4 py-3.5">
                    <h2 className="text-sm font-semibold">Brand colours</h2>
                    <p className="mt-1 text-[11px] text-slate-500">Copy approved colour values directly into your design tools.</p>
                  </div>
                  {loading ? <SkeletonRows /> : emptyMode ? (
                    <EmptyState title="No brand colours yet" description="Add approved colour values so teams can use the right palette." action="Add colours" onAction={() => setToast("Colour management is ready for your next asset upload.")} />
                  ) : (
                    <div className="grid grid-cols-1 gap-3 p-4 sm:grid-cols-2 xl:grid-cols-5">
                      {initialColors.map((color) => (
                        <div key={color.hex} className="overflow-hidden rounded-xl border border-slate-200">
                          <div className="h-16 border-b border-black/5" style={{ backgroundColor: color.hex }} />
                          <div className="p-3">
                            <p className="text-xs font-semibold text-slate-800">{color.name}</p>
                            <div className="mt-2 flex items-center justify-between gap-2">
                              <code className="text-[11px] text-slate-500">{color.hex}</code>
                              <button
                                aria-label={`Copy ${color.name} hex`}
                                onClick={() => {
                                  if (navigator.clipboard?.writeText) {
                                    navigator.clipboard.writeText(color.hex).then(
                                      () => setToast(`${color.hex} copied to clipboard.`),
                                      () => setToast(`Colour value: ${color.hex}`)
                                    );
                                  } else {
                                    setToast(`Colour value: ${color.hex}`);
                                  }
                                }}
                                className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-[#2F5BEA] focus:outline-none focus:ring-2 focus:ring-blue-400"
                              >
                                <Copy size={14} />
                              </button>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </section>

                <section className="overflow-hidden rounded-xl border border-[#E3E8F2] bg-white shadow-sm">
                  <div className="border-b border-slate-100 px-4 py-3.5">
                    <h2 className="text-sm font-semibold">Typography</h2>
                    <p className="mt-1 text-[11px] text-slate-500">Approved font families and how they look in real content.</p>
                  </div>
                  {loading ? <SkeletonRows /> : emptyMode ? (
                    <EmptyState title="No fonts yet" description="Add your approved typefaces to keep typography consistent." action="Add font" onAction={() => setToast("Font management is ready for your next asset upload.")} />
                  ) : (
                    <div className="grid grid-cols-1 gap-3 p-4 lg:grid-cols-2">
                      {initialFonts.map((font) => (
                        <article key={font.name} className="rounded-xl border border-slate-200 p-4">
                          <div className="flex items-start justify-between">
                            <div>
                              <h3 className="text-sm font-semibold">{font.name}</h3>
                              <p className="mt-1 text-[11px] text-slate-500">{font.usage}</p>
                            </div>
                            <span className="rounded-full bg-emerald-50 px-2 py-1 text-[10px] font-medium text-emerald-700">Approved</span>
                          </div>
                          <p
                            className="mt-5 border-t border-slate-100 pt-4 text-xl text-slate-800"
                            style={{ fontFamily: font.name === "Georgia" ? "Georgia, serif" : "Inter, ui-sans-serif, system-ui, sans-serif" }}
                          >
                            {font.sample}
                          </p>
                          <p className="mt-2 text-[10px] text-slate-400">Sample preview · {font.name}</p>
                        </article>
                      ))}
                    </div>
                  )}
                </section>
                <div className="text-right">
                  {SHOW_DEV_TOOLS && (
                    <button onClick={() => setError(true)} className="text-[10px] text-slate-400 underline decoration-dotted underline-offset-2 hover:text-slate-600">
                      Simulate load error
                    </button>
                  )}
                </div>
              </div>
            )}

            {activeTab === "Upload" && (
              <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <div>
                  <h2 className="text-sm font-semibold">Upload brand guidelines</h2>
                  <p className="mt-1 text-[11px] text-slate-500">
                    Plain text, Markdown, a PDF with a text layer, or a Word (.docx) file. Scanned PDFs and
                    password-protected PDFs are not supported.
                  </p>
                </div>

                <label className="block text-[11px] font-medium text-slate-600">
                  Guideline category
                  <select
                    value={uploadCategory}
                    onChange={(event) => setUploadCategory(event.target.value)}
                    disabled={uploading}
                    className="mt-1 h-9 w-full rounded-lg border border-slate-200 bg-white px-2 text-xs"
                  >
                    {categories.map((category) => (
                      <option key={category} value={category}>{category}</option>
                    ))}
                  </select>
                </label>

                <div
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={(event) => {
                    event.preventDefault();
                    void startUpload(event.dataTransfer.files?.[0]);
                  }}
                  className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 p-8 text-center"
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".txt,.md,.pdf,.docx"
                    aria-label="Choose a guideline file"
                    className="sr-only"
                    onChange={(event) => void startUpload(event.target.files?.[0])}
                  />
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploading}
                    className="focus-ring inline-flex h-9 items-center gap-2 rounded-lg bg-[#2F5BEA] px-3 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
                  >
                    <Upload size={14} aria-hidden="true" />
                    Choose a file
                  </button>
                  <p className="mt-3 text-[10px] text-slate-400">
                    .txt, .md, .pdf, .docx · up to {UPLOAD_LIMIT_MB.text} MB for text, {UPLOAD_LIMIT_MB.binary} MB for PDF and Word
                  </p>
                </div>

                {uploadFile && (
                  <p className="flex items-center gap-2 text-xs text-slate-700">
                    {uploading && <Loader2 size={14} className="animate-spin" aria-hidden="true" />}
                    <span className="truncate font-medium">{uploadFile.name}</span>
                    <span className="text-slate-500">{uploading ? "Saving and reading the file…" : ""}</span>
                  </p>
                )}

                {uploadError && (
                  <div role="alert" className="flex items-start justify-between gap-2 rounded-lg border border-red-100 bg-red-50 p-3 text-[11px] text-red-700">
                    <span>{uploadError}</span>
                    <button onClick={() => setUploadError("")} className="font-semibold underline">Dismiss</button>
                  </div>
                )}

                <div className="flex items-start gap-2 rounded-lg bg-blue-50/70 p-3">
                  <Info size={15} className="mt-0.5 shrink-0 text-blue-600" />
                  <p className="text-[11px] leading-5 text-blue-900">
                    After upload, the rules found in the file appear in the Drafts tab. They stay inactive until a manager approves them.
                  </p>
                </div>
                {SHOW_DEV_TOOLS && (
                  <div className="text-right">
                    <button onClick={() => setError(true)} className="text-[10px] text-slate-400 underline decoration-dotted underline-offset-2 hover:text-slate-600">
                      Simulate load error
                    </button>
                  </div>
                )}
              </section>
            )}
          </>
        )}
      </div>

      {/* Rule detail drawer */}
      {drawerOpen && selectedRule && (
        <div className="fixed inset-0 z-40 flex justify-end">
          <button
            aria-label="Close rule details"
            onClick={() => setDrawerOpen(false)}
            className="absolute inset-0 cursor-default bg-slate-950/30"
          />
          <aside className="relative z-10 flex h-full w-full max-w-[480px] flex-col border-l border-slate-200 bg-white shadow-2xl">
            <div className="flex items-start justify-between border-b border-slate-100 px-5 py-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[10px] text-slate-400">{selectedRule.id}</span>
                  <SeverityPill severity={selectedRule.severity} />
                </div>
                <h2 className="mt-2 text-sm font-semibold">Edit brand rule</h2>
                <p className="mt-1 text-[11px] text-slate-500">Update the approved wording and review its history.</p>
              </div>
              <button
                onClick={() => setDrawerOpen(false)}
                aria-label="Close drawer"
                className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-400"
              >
                <X size={17} />
              </button>
            </div>
            <div className="flex-1 space-y-5 overflow-y-auto p-5">
              <div>
                <label className="mb-1.5 block text-xs font-medium text-slate-700">Rule wording</label>
                <textarea
                  value={ruleDraft}
                  onChange={(event) => setRuleDraft(event.target.value)}
                  rows={4}
                  className="w-full resize-y rounded-lg border border-slate-200 px-3 py-2.5 text-xs leading-5 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-slate-700">Severity</label>
                  <select
                    value={ruleSeverity}
                    onChange={(event) => setRuleSeverity(event.target.value as Severity)}
                    className="h-9 w-full rounded-lg border border-slate-200 bg-white px-2 text-xs outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
                  >
                    {(["Critical", "High", "Medium", "Low"] as Severity[]).map((item) => <option key={item}>{item}</option>)}
                  </select>
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-slate-700">Category</label>
                  <select
                    value={ruleCategory}
                    onChange={(event) => setRuleCategory(event.target.value)}
                    className="h-9 w-full rounded-lg border border-slate-200 bg-white px-2 text-xs outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
                  >
                    {categories.filter((item) => item !== "All categories").map((item) => <option key={item}>{item}</option>)}
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg border border-slate-200 p-3">
                  <p className="text-[10px] text-slate-500">Current version</p>
                  <p className="mt-1 text-sm font-semibold">{selectedRule.version}</p>
                </div>
                <div className="rounded-lg border border-slate-200 p-3">
                  <p className="text-[10px] text-slate-500">Rejection rate</p>
                  <p className={`mt-1 text-sm font-semibold ${selectedRule.rejectionRate >= 30 ? "text-amber-700" : "text-slate-800"}`}>{selectedRule.rejectionRate}%</p>
                </div>
              </div>
              <div>
                <div className="mb-3 flex items-center justify-between">
                  <h3 className="flex items-center gap-2 text-xs font-semibold">
                    <History size={14} className="text-slate-400" />
                    Version history
                  </h3>
                  <span className="text-[10px] text-slate-400">{selectedRule.history.length} versions</span>
                </div>
                <div className="space-y-0">
                  {selectedRule.history.map((item, index) => (
                    <div key={`${item.version}-${item.date}`} className="relative flex gap-3 pb-5 last:pb-0">
                      <div className="flex w-4 shrink-0 flex-col items-center">
                        <span className={`mt-1 h-2.5 w-2.5 rounded-full ring-4 ring-white ${index === 0 ? "bg-[#2F5BEA]" : "bg-slate-300"}`} />
                        {index !== selectedRule.history.length - 1 && <span className="mt-1 w-px flex-1 bg-slate-200" />}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-xs font-semibold text-slate-800">{item.version}</span>
                          {index === 0 && <span className="rounded-full bg-blue-50 px-1.5 py-0.5 text-[9px] font-medium text-blue-700">Latest</span>}
                          <span className="text-[10px] text-slate-400">{item.date}</span>
                        </div>
                        <p className="mt-1 text-[11px] leading-4 text-slate-600">{item.change}</p>
                        <p className="mt-1 text-[10px] text-slate-400">By {item.author}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="rounded-lg bg-slate-50 p-3">
                <p className="text-[10px] leading-4 text-slate-500">
                  Changes to approved rules can affect how future content is reviewed. Check wording and severity before saving.
                </p>
              </div>
            </div>
            <div className="flex items-center justify-between gap-3 border-t border-slate-100 p-4">
              <button
                onClick={() => setDrawerOpen(false)}
                className="h-9 rounded-lg border border-slate-200 px-3 text-xs font-medium text-slate-600 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-400"
              >
                Cancel
              </button>
              <button
                onClick={saveRule}
                disabled={!ruleDraft.trim()}
                className="inline-flex h-9 items-center gap-2 rounded-lg bg-[#2F5BEA] px-4 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2"
              >
                <Check size={14} />
                Save changes
              </button>
            </div>
          </aside>
        </div>
      )}

      {/* Add rule dialog */}
      {newRuleOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/35 p-4">
          <div role="dialog" aria-modal="true" aria-labelledby="add-rule-title" className="w-full max-w-lg rounded-xl border border-slate-200 bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
              <div>
                <h2 id="add-rule-title" className="text-sm font-semibold">Add brand rule</h2>
                <p className="mt-1 text-[11px] text-slate-500">Create a new rule for content review.</p>
              </div>
              <button onClick={() => setNewRuleOpen(false)} aria-label="Close dialog" className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-400">
                <X size={16} />
              </button>
            </div>
            <div className="space-y-4 p-5">
              <div>
                <label className="mb-1.5 block text-xs font-medium text-slate-700">Rule wording</label>
                <textarea
                  autoFocus
                  rows={3}
                  value={ruleDraft}
                  onChange={(event) => setRuleDraft(event.target.value)}
                  placeholder="Describe the requirement clearly..."
                  className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-xs outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-slate-700">Severity</label>
                  <select value={ruleSeverity} onChange={(event) => setRuleSeverity(event.target.value as Severity)} className="h-9 w-full rounded-lg border border-slate-200 bg-white px-2 text-xs outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100">
                    {(["Critical", "High", "Medium", "Low"] as Severity[]).map((item) => <option key={item}>{item}</option>)}
                  </select>
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-slate-700">Category</label>
                  <select value={ruleCategory} onChange={(event) => setRuleCategory(event.target.value)} className="h-9 w-full rounded-lg border border-slate-200 bg-white px-2 text-xs outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100">
                    {categories.filter((item) => item !== "All categories").map((item) => <option key={item}>{item}</option>)}
                  </select>
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-2 border-t border-slate-100 p-4">
              <button onClick={() => setNewRuleOpen(false)} className="h-9 rounded-lg border border-slate-200 px-3 text-xs font-medium text-slate-600 hover:bg-slate-50">Cancel</button>
              <button onClick={addRule} disabled={!ruleDraft.trim()} className="h-9 rounded-lg bg-[#2F5BEA] px-4 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50">Add rule</button>
            </div>
          </div>
        </div>
      )}

      {/* Add glossary term dialog */}
      {newTermOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/35 p-4">
          <div role="dialog" aria-modal="true" aria-labelledby="add-term-title" className="w-full max-w-lg rounded-xl border border-slate-200 bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
              <div>
                <h2 id="add-term-title" className="text-sm font-semibold">Add glossary term</h2>
                <p className="mt-1 text-[11px] text-slate-500">Define the preferred term and variants to avoid.</p>
              </div>
              <button onClick={() => setNewTermOpen(false)} aria-label="Close dialog" className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-400">
                <X size={16} />
              </button>
            </div>
            <div className="space-y-4 p-5">
              <div>
                <label className="mb-1.5 block text-xs font-medium text-slate-700">Approved term <span className="text-red-500">*</span></label>
                <input value={termDraft} onChange={(event) => setTermDraft(event.target.value)} placeholder="e.g. Customer" className="h-9 w-full rounded-lg border border-slate-200 px-3 text-xs outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100" />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-slate-700">Variants to avoid</label>
                <input value={avoidDraft} onChange={(event) => setAvoidDraft(event.target.value)} placeholder="e.g. Consumer, Buyer (comma-separated)" className="h-9 w-full rounded-lg border border-slate-200 px-3 text-xs outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100" />
                <p className="mt-1 text-[10px] text-slate-400">Separate each variant with a comma.</p>
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-slate-700">Usage note</label>
                <textarea value={noteDraft} onChange={(event) => setNoteDraft(event.target.value)} rows={2} placeholder="Explain when or how to use this term..." className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-xs outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100" />
              </div>
            </div>
            <div className="flex justify-end gap-2 border-t border-slate-100 p-4">
              <button onClick={() => setNewTermOpen(false)} className="h-9 rounded-lg border border-slate-200 px-3 text-xs font-medium text-slate-600 hover:bg-slate-50">Cancel</button>
              <button onClick={addTerm} disabled={!termDraft.trim()} className="h-9 rounded-lg bg-[#2F5BEA] px-4 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50">Add term</button>
            </div>
          </div>
        </div>
      )}

      {/* Toast notification */}
      {toast && (
        <div role="status" aria-live="polite" className="fixed bottom-5 right-5 z-[60] flex max-w-[calc(100vw-40px)] items-start gap-3 rounded-xl border border-slate-200 bg-white p-3.5 shadow-xl sm:max-w-sm">
          <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-emerald-50 text-emerald-700">
            <CheckCircle2 size={16} />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold text-slate-800">{toast}</p>
            <button
              onClick={() => {
                setToast("");
                setActiveTab("Rules");
                setSuggestionDismissed(false);
              }}
              className="mt-1 text-[11px] font-semibold text-[#2F5BEA] hover:underline"
            >
              View rules
              <ArrowRight className="ml-1 inline" size={12} />
            </button>
          </div>
          <button onClick={() => setToast("")} aria-label="Dismiss notification" className="rounded-md p-1 text-slate-400 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-400">
            <X size={14} />
          </button>
        </div>
      )}

      {/* Small development controls */}
      <div className="mx-auto max-w-[1600px] px-5 pb-4 text-right lg:px-7">
        {SHOW_DEV_TOOLS && (
          <button
            onClick={() => setEmptyMode((current) => !current)}
            className="text-[10px] text-slate-400 underline decoration-dotted underline-offset-2 hover:text-slate-600"
          >
            {emptyMode ? "Exit empty state" : "Preview empty states"}
          </button>
        )}
      </div>
    </div>
  );
}
