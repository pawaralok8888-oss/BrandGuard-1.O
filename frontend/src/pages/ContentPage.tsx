import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { deleteContent, listContent, type ContentRecord } from "@/api/content";
import {
  Search,
  Plus,
  LayoutGrid,
  List,
  FileText,
  Globe,
  Instagram,
  Mail,
  Copy,
  ExternalLink,
  AlertTriangle,
  CheckCircle2,
  X,
  RotateCcw,
  Trash2,
} from "lucide-react";
import { LoadingState } from "@/components/shared/LoadingState";
import { ErrorState } from "@/components/shared/ErrorState";
import { EmptyState } from "@/components/shared/EmptyState";

type Status = "Draft" | "Checked" | "Fixing" | "In Review" | "Changes requested" | "Approved" | "Published" | "Needs revalidation";

type ContentItem = {
  id: string;
  title: string;
  channel: "General" | "Website" | "Instagram" | "Email" | "Ad";
  status: Status;
  owner: string;
  initials: string;
  edited: string;
  high: number;
  medium: number;
  low: number;
  reason?: string;
  thumbnail: string;
};

const statuses: Array<"All" | Status> = [
  "All",
  "Draft",
  "Checked",
  "Fixing",
  "In Review",
  "Changes requested",
  "Approved",
  "Published",
  "Needs revalidation",
];

const statusStyles: Record<Status, string> = {
  Draft: "border-slate-200 bg-slate-50 text-slate-600",
  Checked: "border-blue-200 bg-blue-50 text-blue-700",
  Fixing: "border-amber-200 bg-amber-50 text-amber-700",
  "In Review": "border-blue-200 bg-blue-50 text-blue-700",
  "Changes requested": "border-amber-200 bg-amber-50 text-amber-700",
  Approved: "border-emerald-200 bg-emerald-50 text-emerald-700",
  Published: "border-violet-200 bg-violet-50 text-violet-700",
  "Needs revalidation": "border-red-300 bg-white text-red-700",
};

function ChannelIcon({ channel, size = 15 }: { channel: ContentItem["channel"]; size?: number }) {
  if (channel === "Instagram") return <Instagram size={size} />;
  if (channel === "Email") return <Mail size={size} />;
  if (channel === "Ad") return <Globe size={size} />;
  return <Globe size={size} />;
}

function IssueBadges({ item }: { item: ContentItem }) {
  const total = item.high + item.medium + item.low;

  if (!total) {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] text-emerald-700">
        <CheckCircle2 size={12} /> No issues
      </span>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-1">
      {item.high > 0 && (
        <span title="High severity issues" className="rounded-md bg-red-50 px-1.5 py-1 text-[10px] font-medium text-red-700">
          {item.high} high
        </span>
      )}
      {item.medium > 0 && (
        <span title="Medium severity issues" className="rounded-md bg-amber-50 px-1.5 py-1 text-[10px] font-medium text-amber-700">
          {item.medium} med
        </span>
      )}
      {item.low > 0 && (
        <span title="Low severity issues" className="rounded-md bg-slate-100 px-1.5 py-1 text-[10px] font-medium text-slate-600">
          {item.low} low
        </span>
      )}
    </div>
  );
}

function toContentItem(record: ContentRecord): ContentItem {
  const owner = record.ownerId || "Unknown owner";
  const date = new Date(record.updatedAt);
  const edited = Number.isNaN(date.getTime()) ? "Recently" : date.toLocaleString();
  const thumbnailByArt: Record<string, string> = {
    sunscreen: "from-orange-100 to-rose-100",
    facewash: "from-emerald-100 to-teal-100",
    serum: "from-violet-100 to-fuchsia-100",
    email: "from-blue-100 to-indigo-100",
    routine: "from-sky-100 to-cyan-100",
    offer: "from-amber-100 to-yellow-100",
  };
  return {
    id: record.id,
    title: record.title,
    channel: record.channel,
    status: record.status,
    owner,
    initials: owner.slice(0, 2).toUpperCase(),
    edited,
    high: 0,
    medium: 0,
    low: 0,
    thumbnail: thumbnailByArt[record.thumbnailArt ?? ""] ?? "from-blue-100 to-violet-100",
  };
}

export default function ContentPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<ContentItem[]>([]);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("All");
  const [channelFilter, setChannelFilter] = useState("All");
  const [activeTab, setActiveTab] = useState<"All" | Status>("All");
  const [view, setView] = useState<"grid" | "list">("grid");
  const [state, setState] = useState<"ready" | "loading" | "empty" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [openedItem, setOpenedItem] = useState<ContentItem | null>(null);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let cancelled = false;
    void listContent().then((records) => {
      if (cancelled) return;
      const mapped = records.map(toContentItem);
      setItems(mapped);
      setState(mapped.length > 0 ? "ready" : "empty");
    }).catch((err: unknown) => {
      if (!cancelled) {
        setErrorMessage(err instanceof Error ? err.message : "Failed to load content.");
        setState("error");
      }
    });
    return () => { cancelled = true; };
  }, []);

  function openContent(item: ContentItem) {
    navigate(`/content/compose?id=${encodeURIComponent(item.id)}`);
  }

  function reloadContent() {
    setState("loading");
    setErrorMessage("");
    void listContent().then((records) => {
      const mapped = records.map(toContentItem);
      setItems(mapped);
      setState(mapped.length > 0 ? "ready" : "empty");
    }).catch((err: unknown) => {
      setErrorMessage(err instanceof Error ? err.message : "Failed to load content.");
      setState("error");
    });
  }

  const counts = useMemo(() => {
    const result: Record<string, number> = { All: items.length };
    statuses.slice(1).forEach((status) => {
      result[status] = items.filter((item) => item.status === status).length;
    });
    return result;
  }, [items]);

  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      const matchesSearch = item.title.toLowerCase().includes(search.toLowerCase());
      const matchesTab = activeTab === "All" || item.status === activeTab;
      const matchesStatus = statusFilter === "All" || item.status === statusFilter;
      const matchesChannel = channelFilter === "All" || item.channel === channelFilter;
      return matchesSearch && matchesTab && matchesStatus && matchesChannel;
    });
  }, [items, search, activeTab, statusFilter, channelFilter]);

  function addSampleDraft() {
    navigate("/content/compose");
  }

  function duplicateItem(item: ContentItem) {
    const copy: ContentItem = {
      ...item,
      id: `local_${Date.now()}`,
      title: `${item.title} (copy)`,
      status: "Draft",
      edited: "Just now",
      reason: undefined,
    };
    setItems((current) => [copy, ...current]);
    setNotice("Content duplicated as a new draft.");
  }

  async function removeItem(item: ContentItem) {
    if (!window.confirm(`Delete "${item.title}"? This cannot be undone.`)) return;
    try {
      if (!item.id.startsWith("local_")) await deleteContent(item.id);
      setItems((current) => current.filter((c) => c.id !== item.id));
      setNotice("Content deleted.");
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Could not delete content.");
    }
  }

  function resetFilters() {
    setSearch("");
    setStatusFilter("All");
    setChannelFilter("All");
    setActiveTab("All");
  }

  return (
    <div className="h-full space-y-4 overflow-y-auto pb-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-[#14213D]">Content</h1>
          <p className="mt-1 text-xs text-slate-500">
            Manage drafts, reviews, and published brand content.
          </p>
          <p className="mt-1 text-[11px] text-slate-400">Showing your team's content.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
          <label className="flex min-h-[40px] sm:min-h-[36px] w-full sm:w-auto sm:min-w-44 items-center gap-2 rounded-lg border border-[#E3E8F2] bg-white px-3 focus-within:ring-2 focus-within:ring-blue-200">
            <Search size={14} className="shrink-0 text-slate-400" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search content..."
              aria-label="Search content"
              className="w-full bg-transparent text-xs outline-none placeholder:text-slate-400"
            />
          </label>

          <select
            aria-label="Filter by status"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            className="min-h-[40px] sm:min-h-[36px] flex-1 sm:flex-none rounded-lg border border-[#E3E8F2] bg-white px-2 text-xs outline-none"
          >
            <option value="All">Status: All</option>
            {statuses.slice(1).map((status) => <option key={status}>{status}</option>)}
          </select>

          <select
            aria-label="Filter by channel"
            value={channelFilter}
            onChange={(event) => setChannelFilter(event.target.value)}
            className="min-h-[40px] sm:min-h-[36px] flex-1 sm:flex-none rounded-lg border border-[#E3E8F2] bg-white px-2 text-xs outline-none"
          >
            <option value="All">Channel: All</option>
            <option>Website</option>
            <option>Instagram</option>
            <option>Email</option>
            <option>Ad</option>
          </select>

          <div className="flex min-h-[40px] sm:min-h-[36px] items-center rounded-lg border border-[#E3E8F2] bg-white p-1">
            <button
              onClick={() => setView("grid")}
              aria-label="Grid view"
              aria-pressed={view === "grid"}
              className={`min-h-[32px] min-w-[32px] rounded-md p-1.5 flex items-center justify-center ${view === "grid" ? "bg-blue-50 text-[#2F5BEA]" : "text-slate-400 hover:bg-slate-50"}`}
            >
              <LayoutGrid size={15} />
            </button>
            <button
              onClick={() => setView("list")}
              aria-label="List view"
              aria-pressed={view === "list"}
              className={`min-h-[32px] min-w-[32px] rounded-md p-1.5 flex items-center justify-center ${view === "list" ? "bg-blue-50 text-[#2F5BEA]" : "text-slate-400 hover:bg-slate-50"}`}
            >
              <List size={15} />
            </button>
          </div>

          <button
            onClick={() => navigate("/content/compose")}
            className="inline-flex min-h-[40px] sm:min-h-[36px] w-full sm:w-auto justify-center items-center gap-2 rounded-lg bg-[#2F5BEA] px-3 text-xs font-semibold text-white hover:bg-blue-700"
          >
            <Plus size={15} /> New content
          </button>
        </div>
      </header>

      {notice && (
        <div className="flex items-center justify-between rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
          <span>{notice}</span>
          <button onClick={() => setNotice("")} aria-label="Dismiss message"><X size={14} /></button>
        </div>
      )}

      <div className="flex gap-1 overflow-x-auto border-b border-[#E3E8F2] max-w-full" role="tablist" aria-label="Content status">
        {statuses.map((status) => (
          <button
            key={status}
            role="tab"
            aria-selected={activeTab === status}
            onClick={() => setActiveTab(status)}
            className={`flex shrink-0 min-h-[40px] sm:min-h-[36px] items-center gap-2 border-b-2 px-3 py-2 text-xs font-medium ${
              activeTab === status
                ? "border-[#2F5BEA] text-[#2F5BEA]"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            {status}
            <span className={`rounded-md px-1.5 py-0.5 text-[10px] ${activeTab === status ? "bg-blue-50 text-blue-700" : "bg-slate-100 text-slate-500"}`}>
              {counts[status] ?? 0}
            </span>
          </button>
        ))}
      </div>

      {state === "loading" && <LoadingState label="Loading content library" rows={6} className="m-2" />}

      {state === "error" && (
        <ErrorState
          title="Could not load content"
          description={errorMessage || "Try again to reload the content library."}
          onRetry={reloadContent}
          className="m-4"
        />
      )}

      {state === "empty" && (
        <EmptyState
          title="No content yet — start with a new draft"
          description="Create your first content draft to run brand checks and explore the review workflow."
          actionLabel="New content"
          onAction={addSampleDraft}
          icon={<FileText size={19} aria-hidden="true" />}
          className="m-4"
        />
      )}

      {state === "ready" && filteredItems.length === 0 && (
        <EmptyState
          title="No matching content"
          description="Try changing your search term, channel filter, or status tab."
          actionLabel="Clear filters"
          onAction={resetFilters}
          icon={<Search size={19} aria-hidden="true" />}
          className="m-4"
        />
      )}

      {state === "ready" && filteredItems.length > 0 && view === "grid" && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {filteredItems.map((item) => (
            <article key={item.id} className="group min-w-0 overflow-hidden rounded-xl border border-[#E3E8F2] bg-white transition-shadow hover:shadow-md">
              <div className={`relative flex h-28 items-center justify-center bg-gradient-to-br ${item.thumbnail}`}>
                <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-white/70 bg-white/80 text-slate-600 shadow-sm">
                  <FileText size={23} />
                </div>
                <div className="absolute right-2 top-2 flex gap-1 opacity-100 transition-opacity sm:opacity-0 sm:group-hover:opacity-100">
                  <button onClick={() => openContent(item)} title="Open content" aria-label={`Open ${item.title}`} className="rounded-md border border-white bg-white p-1.5 text-slate-600 shadow-sm hover:text-blue-700 min-h-[32px] min-w-[32px] flex items-center justify-center">
                    <ExternalLink size={13} />
                  </button>
                  <button onClick={() => duplicateItem(item)} title="Duplicate content" aria-label={`Duplicate ${item.title}`} className="rounded-md border border-white bg-white p-1.5 text-slate-600 shadow-sm hover:text-blue-700 min-h-[32px] min-w-[32px] flex items-center justify-center">
                    <Copy size={13} />
                  </button>
                </div>
              </div>

              <div className="space-y-3 p-3">
                <div className="flex items-start justify-between gap-2">
                  <h2 className="line-clamp-2 text-sm font-semibold leading-5 text-[#14213D]">{item.title}</h2>
                  <span className="inline-flex shrink-0 items-center gap-1 text-slate-400" title={item.channel}>
                    <ChannelIcon channel={item.channel} />
                  </span>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <span className={`rounded-full border px-2 py-1 text-[10px] font-medium ${statusStyles[item.status]}`}>
                    {item.status}
                  </span>
                </div>

                {item.status === "Needs revalidation" && item.reason && (
                  <div className="flex items-start gap-1.5 text-[11px] leading-4 text-red-700">
                    <AlertTriangle size={13} className="mt-0.5 shrink-0" />
                    <span>{item.reason}</span>
                  </div>
                )}

                <IssueBadges item={item} />

                <div className="flex items-center justify-between border-t border-slate-100 pt-3">
                  <div className="flex min-w-0 items-center gap-2">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#E8EDFF] text-[10px] font-semibold text-[#2F5BEA]">
                      {item.initials}
                    </span>
                    <span className="truncate text-[11px] text-slate-600">{item.owner}</span>
                  </div>
                  <span className="shrink-0 text-[10px] text-slate-400">{item.edited}</span>
                </div>

                <div className="flex gap-2">
                  <button onClick={() => openContent(item)} className="min-h-[40px] sm:min-h-[36px] flex-1 rounded-lg border border-[#E3E8F2] py-2 text-xs font-semibold text-slate-700 hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700">
                    Open content
                  </button>
                  <button onClick={() => void removeItem(item)} aria-label={`Delete ${item.title}`} className="inline-flex min-h-[40px] sm:min-h-[36px] items-center gap-1.5 rounded-lg border border-red-200 px-3 text-xs font-semibold text-red-600 hover:bg-red-50">
                    <Trash2 size={13} /> Delete
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}

      {state === "ready" && filteredItems.length > 0 && view === "list" && (
        <div className="overflow-x-auto rounded-xl border border-[#E3E8F2] bg-white">
          <table className="w-full min-w-[850px] border-collapse text-left">
            <thead className="bg-slate-50">
              <tr className="text-[11px] font-medium text-slate-500">
                <th className="px-4 py-3">Content</th>
                <th className="px-3 py-3">Channel</th>
                <th className="px-3 py-3">Status</th>
                <th className="px-3 py-3">Issues</th>
                <th className="px-3 py-3">Owner</th>
                <th className="px-3 py-3">Last edited</th>
                <th className="px-3 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredItems.map((item) => (
                <tr key={item.id} onClick={() => openContent(item)} onKeyDown={(event) => { if (event.key === "Enter") openContent(item); }} tabIndex={0} className="cursor-pointer border-t border-slate-100 text-xs hover:bg-slate-50/70">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br ${item.thumbnail}`}>
                        <FileText size={16} className="text-slate-600" />
                      </div>
                      <div className="min-w-0">
                        <div className="font-semibold text-[#14213D]">{item.title}</div>
                        {item.reason && item.status === "Needs revalidation" && (
                          <div className="mt-1 text-[10px] text-red-700">{item.reason}</div>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="px-3 py-3">
                    <span className="inline-flex items-center gap-1.5 text-slate-600">
                      <ChannelIcon channel={item.channel} /> {item.channel}
                    </span>
                  </td>
                  <td className="px-3 py-3">
                    <span className={`inline-block rounded-full border px-2 py-1 text-[10px] font-medium ${statusStyles[item.status]}`}>
                      {item.status}
                    </span>
                  </td>
                  <td className="px-3 py-3"><IssueBadges item={item} /></td>
                  <td className="px-3 py-3">
                    <span className="inline-flex items-center gap-2 whitespace-nowrap">
                      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#E8EDFF] text-[9px] font-semibold text-[#2F5BEA]">{item.initials}</span>
                      {item.owner}
                    </span>
                  </td>
                  <td className="px-3 py-3 whitespace-nowrap text-slate-500">{item.edited}</td>
                  <td className="px-3 py-3">
                    <div className="flex justify-end gap-1">
                      <button onClick={(event) => { event.stopPropagation(); openContent(item); }} title="Open" aria-label={`Open ${item.title}`} className="rounded-md p-2 text-slate-500 hover:bg-blue-50 hover:text-blue-700 min-h-[36px] min-w-[36px] flex items-center justify-center">
                        <ExternalLink size={14} />
                      </button>
                      <button onClick={(event) => { event.stopPropagation(); duplicateItem(item); }} title="Duplicate" aria-label={`Duplicate ${item.title}`} className="rounded-md p-2 text-slate-500 hover:bg-blue-50 hover:text-blue-700 min-h-[36px] min-w-[36px] flex items-center justify-center">
                        <Copy size={14} />
                      </button>
                      <button onClick={(event) => { event.stopPropagation(); void removeItem(item); }} title="Delete" aria-label={`Delete ${item.title}`} className="rounded-md p-2 text-red-500 hover:bg-red-50 min-h-[36px] min-w-[36px] flex items-center justify-center">
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {state === "ready" && (
        <div className="flex flex-wrap items-center justify-between gap-3 text-[11px] text-slate-400">
          <span>Showing {filteredItems.length} of {items.length} content items</span>
          <div className="flex flex-wrap items-center gap-3">
            <button onClick={addSampleDraft} className="font-medium text-[#2F5BEA] hover:underline">
              + Add sample draft
            </button>
            <button onClick={() => setState("loading")} className="inline-flex items-center gap-1 hover:text-slate-700">
              <RotateCcw size={12} /> Simulate loading
            </button>
            <button onClick={() => setState("empty")} className="hover:text-slate-700">Simulate empty</button>
            <button onClick={() => setState("error")} className="hover:text-slate-700">Simulate error</button>
          </div>
        </div>
      )}

      {openedItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/30 p-4" role="dialog" aria-modal="true" aria-label="Content preview">
          <div className="w-full max-w-lg rounded-xl border border-[#E3E8F2] bg-white p-5 shadow-xl">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[11px] text-slate-500">Content preview</p>
                <h2 className="mt-1 text-base font-semibold text-[#14213D]">{openedItem.title}</h2>
              </div>
              <button onClick={() => setOpenedItem(null)} aria-label="Close preview" className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100">
                <X size={17} />
              </button>
            </div>
            <div className="mt-4 space-y-3 rounded-lg bg-slate-50 p-4">
              <div className="flex items-center gap-2 text-xs text-slate-600"><ChannelIcon channel={openedItem.channel} /> {openedItem.channel}</div>
              <div><span className="text-[11px] text-slate-500">Status</span><p className="mt-1 text-xs font-medium">{openedItem.status}</p></div>
              <div><span className="text-[11px] text-slate-500">Owner</span><p className="mt-1 text-xs font-medium">{openedItem.owner}</p></div>
              <div><span className="text-[11px] text-slate-500">Detected issues</span><div className="mt-2"><IssueBadges item={openedItem} /></div></div>
              {openedItem.reason && <p className="text-xs text-red-700">Revalidation reason: {openedItem.reason}</p>}
              <p className="text-xs leading-5 text-slate-600">This is a local demo preview. Connect the content editor and backend to load and edit the full content.</p>
            </div>
            <div className="mt-4 flex flex-wrap justify-end gap-2">
              <button onClick={() => duplicateItem(openedItem)} className="inline-flex min-h-[40px] sm:min-h-[36px] items-center gap-2 rounded-lg border border-[#E3E8F2] px-3 text-xs font-medium hover:bg-slate-50">
                <Copy size={13} /> Duplicate
              </button>
              <button onClick={() => setOpenedItem(null)} className="min-h-[40px] sm:min-h-[36px] rounded-lg bg-[#2F5BEA] px-4 text-xs font-semibold text-white hover:bg-blue-700">
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}