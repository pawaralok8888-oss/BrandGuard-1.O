
import { SHOW_DEV_TOOLS } from "@/lib/devTools";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  getAlerts,
  updateAlertStatus as apiUpdateAlert,
  type AlertItem as ApiAlertItem,
} from "@/api/alerts";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Bell,
  Check,
  CheckCheck,
  CheckCircle2,
  ChevronDown,
  Clock3,
  FileText,
  Filter,
  MessageSquare,
  RefreshCw,
  Search,
  Send,
  ShieldAlert,
  Sparkles,
  X,
  XCircle,
} from "lucide-react";

type Priority = "High" | "Medium";
type AlertStatus = "Open" | "Updated" | "Dismissed";
type AlertTab = "Open" | "Updated" | "Dismissed";

type AlertItem = {
  id: string;
  title: string;
  channel: string;
  priority: Priority;
  status: AlertStatus;
  thumbnail: string;
  thumbnailLabel: string;
  reason: string;
  fact: string;
  oldValue: string;
  newValue: string;
  oldSentence: string;
  correctedSentence: string;
  owner: string;
  initials: string;
  ownerColor: string;
  sentAt: string;
  reminderSent: boolean;
  read: boolean;
};

const initialAlerts: AlertItem[] = [];

function HighlightedSentence({ text, value }: { text: string; value: string }) {
  const index = text.toLowerCase().indexOf(value.toLowerCase());
  if (index === -1) return <>{text}</>;

  return (
    <>
      {text.slice(0, index)}
      <mark className="rounded bg-emerald-100 px-0.5 font-semibold text-emerald-900">
        {text.slice(index, index + value.length)}
      </mark>
      {text.slice(index + value.length)}
    </>
  );
}

function Avatar({ item, size = "md" }: { item: AlertItem; size?: "sm" | "md" }) {
  return (
    <div
      title={item.owner}
      aria-label={`Owner: ${item.owner}`}
      className={`flex shrink-0 items-center justify-center rounded-full font-semibold ${
        size === "sm" ? "h-6 w-6 text-[9px]" : "h-8 w-8 text-[10px]"
      } ${item.ownerColor}`}
    >
      {item.initials}
    </div>
  );
}

function StatusPill({ status }: { status: AlertStatus }) {
  const styles: Record<AlertStatus, string> = {
    Open: "bg-blue-50 text-blue-700 ring-blue-200",
    Updated: "bg-emerald-50 text-emerald-700 ring-emerald-200",
    Dismissed: "bg-slate-100 text-slate-600 ring-slate-200",
  };

  return (
    <span className={`inline-flex items-center rounded-full px-2 py-1 text-[10px] font-medium ring-1 ring-inset ${styles[status]}`}>
      {status === "Updated" && <Check size={11} className="mr-1" />}
      {status}
    </span>
  );
}

function ContentThumbnail({ item }: { item: AlertItem }) {
  return (
    <div className={`relative flex h-[76px] w-[92px] shrink-0 flex-col justify-between overflow-hidden rounded-lg bg-gradient-to-br ${item.thumbnail} p-2.5`}>
      <div className="absolute -right-3 -top-4 h-14 w-14 rounded-full border-[8px] border-white/40" />
      <div className="absolute -bottom-4 -left-2 h-12 w-12 rounded-full bg-white/30" />
      <div className="relative flex items-center gap-1 text-[8px] font-bold tracking-wide text-slate-700">
        <ShieldAlert size={11} />
        BRANDGUARD
      </div>
      <div className="relative max-w-full truncate text-[10px] font-extrabold tracking-wide text-slate-800">
        {item.thumbnailLabel}
      </div>
    </div>
  );
}

function EmptyState({ onReset }: { onReset: () => void }) {
  return (
    <div className="flex min-h-[300px] flex-col items-center justify-center px-5 py-12 text-center">
      <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-50 text-emerald-600">
        <CheckCheck size={24} />
      </div>
      <h3 className="text-sm font-semibold text-slate-800">
        You're all caught up — no content needs updating
      </h3>
      <p className="mt-1 max-w-sm text-xs leading-5 text-slate-500">
        When an approved fact or rule changes, content you own that needs attention will appear here.
      </p>
      <button
        onClick={onReset}
        className="mt-4 h-9 rounded-lg border border-slate-200 bg-white px-3 text-xs font-medium text-slate-600 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-400"
      >
        View all alerts
      </button>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="space-y-3 p-4" aria-label="Loading alerts">
      {Array.from({ length: 3 }).map((_, index) => (
        <div key={index} className="animate-pulse rounded-xl border border-slate-200 bg-white p-4">
          <div className="flex gap-3">
            <div className="h-[76px] w-[92px] rounded-lg bg-slate-200" />
            <div className="flex-1 space-y-3 pt-1">
              <div className="h-3 w-2/3 rounded bg-slate-200" />
              <div className="h-3 w-1/2 rounded bg-slate-100" />
              <div className="h-8 w-full rounded bg-slate-100" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export function AlertsBellDropdown({
  alerts,
  onMarkRead,
  onMarkAllRead,
  onViewAll,
}: {
  alerts: AlertItem[];
  onMarkRead: (id: string) => void;
  onMarkAllRead: () => void;
  onViewAll: () => void;
}) {
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const unreadCount = alerts.filter((item) => !item.read).length;
  const latest = [...alerts].sort((a, b) => {
    const priority = (status: AlertItem) => status.status === "Open" ? 0 : 1;
    return priority(a) - priority(b);
  }).slice(0, 5);

  useEffect(() => {
    function closeOnOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", closeOnOutside);
    return () => document.removeEventListener("mousedown", closeOnOutside);
  }, []);

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setOpen((current) => !current)}
        aria-label={`Notifications${unreadCount ? `, ${unreadCount} unread` : ""}`}
        aria-expanded={open}
        className="relative flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-400"
      >
        <Bell size={17} />
        {unreadCount > 0 && (
          <>
            <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-red-500 ring-2 ring-white" />
            <span className="sr-only">{unreadCount} unread alerts</span>
          </>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-11 z-50 w-[min(360px,calc(100vw-32px))] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
            <div>
              <h3 className="text-xs font-semibold text-slate-800">Notifications</h3>
              <p className="mt-0.5 text-[10px] text-slate-500">
                {unreadCount ? `${unreadCount} unread alerts` : "You're all caught up"}
              </p>
            </div>
            <button
              onClick={onMarkAllRead}
              disabled={!unreadCount}
              className="text-[10px] font-medium text-[#2F5BEA] hover:underline disabled:text-slate-300 disabled:no-underline"
            >
              Mark all as read
            </button>
          </div>

          <div className="max-h-[360px] overflow-y-auto">
            {latest.length === 0 ? (
              <div className="p-6 text-center text-xs text-slate-500">No notifications yet.</div>
            ) : (
              latest.map((item) => (
                <button
                  key={item.id}
                  onClick={() => {
                    onMarkRead(item.id);
                    setOpen(false);
                    onViewAll();
                  }}
                  className={`flex w-full items-start gap-3 border-b border-slate-100 px-4 py-3 text-left transition hover:bg-slate-50 ${
                    !item.read ? "bg-blue-50/40" : ""
                  }`}
                >
                  <div className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${!item.read ? "bg-[#2F5BEA]" : "bg-transparent"}`} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-semibold text-slate-800">{item.title}</p>
                    <p className="mt-1 line-clamp-2 text-[11px] leading-4 text-slate-500">
                      {item.fact}: {item.oldValue} → {item.newValue}
                    </p>
                    <p className="mt-1.5 text-[10px] text-slate-400">{item.sentAt}</p>
                  </div>
                  <ChevronDown size={13} className="-rotate-90 mt-1 shrink-0 text-slate-300" />
                </button>
              ))
            )}
          </div>
          <div className="p-2">
            <button
              onClick={() => {
                setOpen(false);
                onViewAll();
              }}
              className="flex h-9 w-full items-center justify-center gap-2 rounded-lg text-xs font-semibold text-[#2F5BEA] transition hover:bg-blue-50 focus:outline-none focus:ring-2 focus:ring-blue-400"
            >
              View all alerts
              <ArrowRight size={14} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<AlertItem[]>(initialAlerts);
  const [activeTab, setActiveTab] = useState<AlertTab>("Open");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [emptyMode, setEmptyMode] = useState(false);
  const [selectedAlert, setSelectedAlert] = useState<AlertItem | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editorText, setEditorText] = useState("");
  const [, setEditorSaved] = useState(false);
  const [dismissOpen, setDismissOpen] = useState(false);
  const [dismissReason, setDismissReason] = useState("");
  const [dismissTarget, setDismissTarget] = useState<AlertItem | null>(null);
  const [toast, setToast] = useState("");
  const [search, setSearch] = useState("");
  const [filterPriority, setFilterPriority] = useState<"All" | Priority>("All");

  async function loadAlerts() {
    setLoading(true);
    setError(false);
    try {
      const data = await getAlerts();
      const mapped: AlertItem[] = data.map((a) => {
        const rawStatus = (a.status || "open").toLowerCase();
        const displayStatus: AlertStatus =
          rawStatus === "updated"
            ? "Updated"
            : rawStatus === "dismissed"
              ? "Dismissed"
              : "Open";

        return {
          id: a.id,
          title: a.title,
          channel: a.contentId ? `Content: ${a.contentId}` : "Campaign Post",
          priority: a.priority || "Medium",
          status: displayStatus,
          thumbnail: "from-blue-100 via-indigo-50 to-slate-100",
          thumbnailLabel: "UPDATE NEEDED",
          reason: a.reason || "Approved fact changed.",
          fact: a.title,
          oldValue: a.oldValue || "-",
          newValue: a.newValue || "-",
          oldSentence: a.oldValue ? `Previous value: ${a.oldValue}` : "",
          correctedSentence: a.newValue ? `New approved value: ${a.newValue}` : "",
          owner: "Content Owner",
          initials: "CO",
          ownerColor: "bg-blue-100 text-blue-700",
          sentAt: a.createdAt ? new Date(a.createdAt).toLocaleDateString() : "Recent",
          reminderSent: false,
          read: a.status !== "open",
        };
      });
      setAlerts(mapped);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadAlerts();
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 4000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const counts = useMemo(() => ({
    Open: alerts.filter((item) => item.status === "Open").length,
    Updated: alerts.filter((item) => item.status === "Updated").length,
    Dismissed: alerts.filter((item) => item.status === "Dismissed").length,
  }), [alerts]);

  const filteredAlerts = useMemo(() => alerts.filter((item) => {
    const matchesTab = item.status === activeTab;
    const matchesSearch = `${item.title} ${item.channel} ${item.fact} ${item.owner}`.toLowerCase().includes(search.toLowerCase());
    const matchesPriority = filterPriority === "All" || item.priority === filterPriority;
    return matchesTab && matchesSearch && matchesPriority;
  }), [alerts, activeTab, search, filterPriority]);

  const highAlerts = filteredAlerts.filter((item) => item.priority === "High");
  const mediumAlerts = filteredAlerts.filter((item) => item.priority === "Medium");
  const attentionCount = alerts.filter((item) => item.status === "Open").length;

  async function updateAlertStatus(item: AlertItem, status: AlertStatus) {
    try {
      const apiStatus = status === "Updated" ? "updated" : "dismissed";
      await apiUpdateAlert(item.id, apiStatus);
      setToast(`Alert marked as ${status.toLowerCase()}.`);
      await loadAlerts();
    } catch (err: any) {
      setToast(err?.message || "Failed to update alert");
    }
  }

  function openEditor(item: AlertItem) {
    setSelectedAlert(item);
    setEditorText(item.correctedSentence);
    setEditorSaved(false);
    setEditorOpen(true);
  }

  async function applyCorrection() {
    if (!selectedAlert) return;
    try {
      await apiUpdateAlert(selectedAlert.id, "updated");
      setToast("Correction applied. Alert marked as updated.");
      await loadAlerts();
    } catch (err: any) {
      setToast(err?.message || "Failed to apply correction");
    }
    setEditorSaved(true);
    setEditorOpen(false);
  }

  function openDismissDialog(item: AlertItem) {
    setDismissTarget(item);
    setDismissReason("");
    setDismissOpen(true);
  }

  async function confirmDismiss() {
    if (!dismissTarget || !dismissReason.trim()) return;
    try {
      await apiUpdateAlert(dismissTarget.id, "dismissed");
      setToast("Alert dismissed with your reason.");
      await loadAlerts();
    } catch (err: any) {
      setToast(err?.message || "Failed to dismiss alert");
    }
    setDismissOpen(false);
    setDismissTarget(null);
  }

  function markAllRead() {
    setAlerts((current) => current.map((item) => ({ ...item, read: true })));
    setToast("All notifications marked as read.");
  }

  function resetToOpen() {
    setActiveTab("Open");
    setSearch("");
    setFilterPriority("All");
    setEmptyMode(false);
  }

  function renderAlertCard(item: AlertItem) {
    return (
      <article key={item.id} className="overflow-hidden rounded-xl border border-[#E3E8F2] bg-white shadow-sm transition hover:border-slate-300">
        <div className="p-4">
          <div className="flex flex-col gap-3 sm:flex-row">
            <ContentThumbnail item={item} />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-xs font-semibold text-slate-900">{item.title}</h3>
                    <StatusPill status={item.status} />
                  </div>
                  <p className="mt-1 text-[11px] text-slate-500">{item.channel}</p>
                </div>
                <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-[10px] font-semibold ${
                  item.priority === "High" ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-800"
                }`}>
                  <span className={`h-1.5 w-1.5 rounded-full ${item.priority === "High" ? "bg-red-500" : "bg-amber-500"}`} />
                  {item.priority} priority
                </span>
              </div>

              <div className="mt-3 flex flex-wrap items-center gap-1.5 text-[11px]">
                <span className="font-medium text-slate-500">Why this needs updating:</span>
                <span className="text-slate-700">{item.reason}</span>
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <span className="text-[10px] font-medium text-slate-500">Changed fact</span>
                <span className="inline-flex items-center gap-1 rounded-md border border-blue-100 bg-blue-50 px-2 py-1 text-[10px] font-medium text-blue-700">
                  <FileText size={11} />
                  {item.fact}
                </span>
              </div>
            </div>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
            <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-3">
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-slate-500">Approved fact changed</p>
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="text-slate-400 line-through decoration-red-400 decoration-2">{item.oldValue}</span>
                <ArrowRight size={14} className="text-slate-400" />
                <span className="font-semibold text-slate-900">{item.newValue}</span>
              </div>
              <p className="mt-2 border-t border-slate-200 pt-2 text-[10px] leading-4 text-slate-500">
                Published copy currently uses the outdated value.
              </p>
            </div>

            <div className="rounded-lg border border-emerald-200 bg-emerald-50/60 p-3">
              <p className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-800">
                <Sparkles size={12} />
                Suggested correction
              </p>
              <p className="text-xs leading-5 text-slate-700">
                <HighlightedSentence text={item.correctedSentence} value={item.newValue} />
              </p>
            </div>
          </div>

          <div className="mt-4 flex flex-col gap-3 border-t border-slate-100 pt-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
              <div className="flex items-center gap-2">
                <Avatar item={item} />
                <div>
                  <p className="text-[11px] font-medium text-slate-700">{item.owner}</p>
                  <p className="text-[10px] text-slate-400">Content owner</p>
                </div>
              </div>
              <span className="hidden h-7 w-px bg-slate-200 sm:block" />
              <span className="inline-flex items-center gap-1 text-[10px] text-slate-500">
                <Clock3 size={12} />
                Alert sent {item.sentAt}
              </span>
              {item.priority === "High" && item.status === "Open" && item.reminderSent && (
                <span className="inline-flex items-center gap-1 rounded-full border border-red-100 bg-red-50 px-2 py-1 text-[10px] font-medium text-red-700">
                  <Send size={10} />
                  Reminder sent
                </span>
              )}
            </div>

            {item.status === "Open" ? (
              <div className="flex flex-wrap items-center gap-2">
                <button
                  onClick={() => openEditor(item)}
                  className="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg bg-[#2F5BEA] px-3 text-[11px] font-semibold text-white transition hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2"
                >
                  <Check size={13} />
                  Apply correction
                </button>
                <button
                  onClick={() => {
                    updateAlertStatus(item, "Updated");
                    setToast("Alert marked as updated.");
                  }}
                  className="inline-flex h-8 items-center justify-center rounded-lg border border-slate-200 bg-white px-3 text-[11px] font-medium text-slate-600 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-400"
                >
                  Mark as updated
                </button>
                <button
                  onClick={() => openDismissDialog(item)}
                  className="inline-flex h-8 items-center justify-center rounded-lg px-2 text-[11px] font-medium text-slate-500 transition hover:bg-red-50 hover:text-red-700 focus:outline-none focus:ring-2 focus:ring-red-300"
                >
                  Dismiss
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-[11px] text-slate-500">
                {item.status === "Updated" ? <CheckCircle2 size={14} className="text-emerald-600" /> : <XCircle size={14} />}
                {item.status === "Updated" ? "Correction acknowledged" : "Alert dismissed"}
                <button
                  onClick={() => updateAlertStatus(item, "Open")}
                  className="ml-1 font-medium text-[#2F5BEA] hover:underline"
                >
                  Reopen
                </button>
              </div>
            )}
          </div>
        </div>
      </article>
    );
  }

  return (
    <div className="min-h-screen bg-[#F6F8FC] text-[#14213D]">
      <div className="mx-auto max-w-[1600px] px-5 py-5 lg:px-7">
        <header className="mb-5 flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
          <div>
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-50 text-[#2F5BEA]">
                <Bell size={17} />
              </div>
              <h1 className="text-[18px] font-semibold tracking-[-0.02em]">Alerts</h1>
            </div>
            <p className="mt-1 max-w-2xl pl-10 text-[12px] leading-5 text-slate-500">
              Published content that needs an update because an approved fact or rule changed.
            </p>
          </div>
          <div className="flex items-center gap-2 self-end sm:self-start">
            <button
              onClick={() => {
                setLoading(true);
                setError(false);
                window.setTimeout(() => setLoading(false), 650);
              }}
              aria-label="Refresh alerts"
              className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-400"
            >
              <RefreshCw size={15} />
            </button>
            <AlertsBellDropdown
              alerts={alerts}
              onMarkRead={(id) => setAlerts((current) => current.map((item) => item.id === id ? { ...item, read: true } : item))}
              onMarkAllRead={markAllRead}
              onViewAll={resetToOpen}
            />
          </div>
        </header>

        <div className="mb-4 flex flex-col gap-3 rounded-xl border border-blue-100 bg-blue-50/70 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white text-[#2F5BEA] shadow-sm">
              <AlertTriangle size={17} />
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-900">
                {attentionCount} {attentionCount === 1 ? "item needs" : "items need"} your attention
              </p>
              <p className="mt-0.5 text-[11px] text-slate-600">
                You only see alerts for content you own.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 self-start rounded-full bg-white/80 px-2.5 py-1.5 text-[10px] font-medium text-slate-600 sm:self-center">
            <ShieldAlert size={13} className="text-blue-600" />
            Fact & rule change monitoring
          </div>
        </div>

        <div className="mb-4 flex flex-col gap-3 border-b border-slate-200 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex gap-1 overflow-x-auto" role="tablist" aria-label="Alert status">
            {(["Open", "Updated", "Dismissed"] as AlertTab[]).map((tab) => (
              <button
                key={tab}
                role="tab"
                aria-selected={activeTab === tab}
                onClick={() => setActiveTab(tab)}
                className={`relative -mb-px inline-flex items-center gap-2 whitespace-nowrap border-b-2 px-4 py-3 text-xs font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${
                  activeTab === tab
                    ? "border-[#2F5BEA] text-[#2F5BEA]"
                    : "border-transparent text-slate-500 hover:text-slate-800"
                }`}
              >
                {tab}
                <span className={`rounded-full px-1.5 py-0.5 text-[10px] ${activeTab === tab ? "bg-blue-50 text-blue-700" : "bg-slate-100 text-slate-500"}`}>
                  {counts[tab]}
                </span>
              </button>
            ))}
          </div>

          <div className="flex gap-2 pb-2 sm:pb-0">
            <div className="relative min-w-0 flex-1 sm:w-52 sm:flex-none">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search alerts..."
                aria-label="Search alerts"
                className="h-9 w-full rounded-lg border border-slate-200 bg-white pl-9 pr-3 text-xs outline-none placeholder:text-slate-400 focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
              />
            </div>
            <div className="relative">
              <Filter size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <select
                value={filterPriority}
                onChange={(event) => setFilterPriority(event.target.value as "All" | Priority)}
                aria-label="Filter by priority"
                className="h-9 appearance-none rounded-lg border border-slate-200 bg-white pl-8 pr-7 text-xs text-slate-600 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
              >
                <option value="All">All priorities</option>
                <option value="High">High</option>
                <option value="Medium">Medium</option>
              </select>
              <ChevronDown size={12} className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
            </div>
          </div>
        </div>

        {error ? (
          <div className="rounded-xl border border-red-200 bg-white px-6 py-12 text-center shadow-sm">
            <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-red-50 text-red-600">
              <AlertCircle size={22} />
            </div>
            <h2 className="text-sm font-semibold text-slate-800">Couldn't load alerts</h2>
            <p className="mt-1 text-xs text-slate-500">Your alerts couldn't be retrieved. Please try again.</p>
            <button
              onClick={() => {
                setError(false);
                setLoading(true);
                window.setTimeout(() => setLoading(false), 650);
              }}
              className="mt-4 h-9 rounded-lg bg-[#2F5BEA] px-4 text-xs font-semibold text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2"
            >
              Try again
            </button>
          </div>
        ) : loading ? (
          <LoadingState />
        ) : emptyMode || filteredAlerts.length === 0 ? (
          <div className="rounded-xl border border-[#E3E8F2] bg-white shadow-sm">
            <EmptyState onReset={resetToOpen} />
          </div>
        ) : (
          <div className="space-y-5">
            {highAlerts.length > 0 && (
              <section>
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="flex items-center gap-2 text-xs font-semibold text-slate-800">
                    <span className="h-2 w-2 rounded-full bg-red-500" />
                    High priority
                    <span className="rounded-full bg-red-50 px-1.5 py-0.5 text-[10px] font-medium text-red-700">{highAlerts.length}</span>
                  </h2>
                  <p className="text-[10px] text-slate-400">Resolve these first</p>
                </div>
                <div className="space-y-3">{highAlerts.map(renderAlertCard)}</div>
              </section>
            )}

            {mediumAlerts.length > 0 && (
              <section>
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="flex items-center gap-2 text-xs font-semibold text-slate-800">
                    <span className="h-2 w-2 rounded-full bg-amber-500" />
                    Medium priority
                    <span className="rounded-full bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-800">{mediumAlerts.length}</span>
                  </h2>
                  <p className="text-[10px] text-slate-400">Review when convenient</p>
                </div>
                <div className="space-y-3">{mediumAlerts.map(renderAlertCard)}</div>
              </section>
            )}

            <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white px-4 py-3">
              <p className="text-[11px] text-slate-500">
                Showing {filteredAlerts.length} {filteredAlerts.length === 1 ? "alert" : "alerts"} · Only content you own is shown.
              </p>
              <div className="flex items-center gap-3">
                {SHOW_DEV_TOOLS && (
                  <button onClick={() => setError(true)} className="text-[10px] text-slate-400 underline decoration-dotted underline-offset-2 hover:text-slate-600">
                    Simulate load error
                  </button>
                )}
                {SHOW_DEV_TOOLS && (
                  <button onClick={() => setEmptyMode(true)} className="text-[10px] text-slate-400 underline decoration-dotted underline-offset-2 hover:text-slate-600">
                    Preview empty state
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Correction editor */}
      {editorOpen && selectedAlert && (
        <div className="fixed inset-0 z-40 flex justify-end">
          <button aria-label="Close correction editor" onClick={() => setEditorOpen(false)} className="absolute inset-0 bg-slate-950/30" />
          <aside className="relative z-10 flex h-full w-full max-w-[520px] flex-col border-l border-slate-200 bg-white shadow-2xl">
            <div className="flex items-start justify-between border-b border-slate-100 px-5 py-4">
              <div>
                <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-2 py-1 text-[10px] font-medium text-blue-700">
                  <Sparkles size={11} />
                  Suggested correction
                </span>
                <h2 className="mt-2 text-sm font-semibold text-slate-900">Update published content</h2>
                <p className="mt-1 text-[11px] text-slate-500">{selectedAlert.title}</p>
              </div>
              <button onClick={() => setEditorOpen(false)} aria-label="Close editor" className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-400">
                <X size={16} />
              </button>
            </div>

            <div className="flex-1 space-y-5 overflow-y-auto p-5">
              <div className="rounded-lg border border-amber-200 bg-amber-50/70 p-3">
                <p className="flex items-center gap-1.5 text-xs font-semibold text-amber-900">
                  <AlertTriangle size={14} />
                  Why this change is needed
                </p>
                <p className="mt-1.5 text-[11px] leading-5 text-amber-900/80">{selectedAlert.reason}</p>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px]">
                  <span className="rounded-md border border-amber-200 bg-white px-2 py-1 text-slate-600">{selectedAlert.fact}</span>
                  <span className="text-slate-400 line-through">{selectedAlert.oldValue}</span>
                  <ArrowRight size={12} className="text-slate-400" />
                  <span className="font-semibold text-slate-800">{selectedAlert.newValue}</span>
                </div>
              </div>

              <div>
                <label htmlFor="correction-text" className="mb-1.5 block text-xs font-semibold text-slate-700">
                  Content editor
                </label>
                <textarea
                  id="correction-text"
                  value={editorText}
                  onChange={(event) => setEditorText(event.target.value)}
                  rows={6}
                  className="w-full resize-y rounded-lg border border-slate-200 px-3 py-3 text-sm leading-6 text-slate-800 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
                />
                <p className="mt-1.5 text-[10px] text-slate-400">The suggested correction has been pre-filled. Review it before applying.</p>
              </div>

              <div className="rounded-lg border border-emerald-200 bg-emerald-50/60 p-3">
                <p className="flex items-center gap-1.5 text-[11px] font-semibold text-emerald-800">
                  <CheckCircle2 size={13} />
                  Approved value
                </p>
                <p className="mt-1.5 text-xs text-slate-700">{selectedAlert.fact}: <strong>{selectedAlert.newValue}</strong></p>
              </div>

              <div>
                <h3 className="mb-2 text-xs font-semibold text-slate-800">Change preview</h3>
                <div className="space-y-2 rounded-lg border border-slate-200 p-3">
                  <div>
                    <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-slate-400">Before</p>
                    <p className="text-xs leading-5 text-slate-500 line-through">{selectedAlert.oldSentence}</p>
                  </div>
                  <div className="border-t border-slate-100 pt-2">
                    <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-emerald-700">After</p>
                    <p className="text-xs leading-5 text-slate-800">{editorText}</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 p-4">
              <button onClick={() => setEditorOpen(false)} className="h-9 rounded-lg border border-slate-200 px-3 text-xs font-medium text-slate-600 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-400">
                Cancel
              </button>
              <button
                onClick={applyCorrection}
                disabled={!editorText.trim()}
                className="inline-flex h-9 items-center gap-2 rounded-lg bg-[#2F5BEA] px-4 text-xs font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2"
              >
                <Check size={14} />
                Apply correction
              </button>
            </div>
          </aside>
        </div>
      )}

      {/* Dismiss reason dialog */}
      {dismissOpen && dismissTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/35 p-4">
          <div role="dialog" aria-modal="true" aria-labelledby="dismiss-alert-title" className="w-full max-w-md rounded-xl border border-slate-200 bg-white shadow-2xl">
            <div className="flex items-start justify-between border-b border-slate-100 px-5 py-4">
              <div>
                <div className="mb-2 flex h-8 w-8 items-center justify-center rounded-lg bg-amber-50 text-amber-700">
                  <MessageSquare size={16} />
                </div>
                <h2 id="dismiss-alert-title" className="text-sm font-semibold text-slate-900">Dismiss this alert?</h2>
                <p className="mt-1 text-[11px] text-slate-500">Add a reason so the decision can be understood later.</p>
              </div>
              <button onClick={() => setDismissOpen(false)} aria-label="Close dismiss dialog" className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-400">
                <X size={16} />
              </button>
            </div>
            <div className="p-5">
              <p className="mb-3 text-xs font-medium text-slate-700">{dismissTarget.title}</p>
              <label htmlFor="dismiss-reason" className="mb-1.5 block text-xs font-medium text-slate-700">
                Reason for dismissal <span className="text-red-500">*</span>
              </label>
              <textarea
                id="dismiss-reason"
                autoFocus
                value={dismissReason}
                onChange={(event) => setDismissReason(event.target.value)}
                rows={3}
                placeholder="e.g. This content has already been removed from the channel..."
                className="w-full resize-y rounded-lg border border-slate-200 px-3 py-2.5 text-xs leading-5 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
              />
              <p className="mt-1.5 text-[10px] text-slate-400">The reason is stored with this alert in the current page state.</p>
            </div>
            <div className="flex justify-end gap-2 border-t border-slate-100 p-4">
              <button onClick={() => setDismissOpen(false)} className="h-9 rounded-lg border border-slate-200 px-3 text-xs font-medium text-slate-600 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-400">
                Cancel
              </button>
              <button
                onClick={confirmDismiss}
                disabled={!dismissReason.trim()}
                className="h-9 rounded-lg bg-red-600 px-4 text-xs font-semibold text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-red-400 focus:ring-offset-2"
              >
                Dismiss alert
              </button>
            </div>
          </div>
        </div>
      )}

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
                resetToOpen();
              }}
              className="mt-1 text-[11px] font-semibold text-[#2F5BEA] hover:underline"
            >
              View alerts <ArrowRight className="ml-1 inline" size={12} />
            </button>
          </div>
          <button onClick={() => setToast("")} aria-label="Dismiss notification" className="rounded-md p-1 text-slate-400 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-400">
            <X size={14} />
          </button>
        </div>
      )}

      <div className="mx-auto max-w-[1600px] px-5 pb-4 text-right lg:px-7">
        {SHOW_DEV_TOOLS && (
          <button
            onClick={() => setEmptyMode((current) => !current)}
            className="text-[10px] text-slate-400 underline decoration-dotted underline-offset-2 hover:text-slate-600"
          >
            {emptyMode ? "Exit empty state" : "Preview empty state"}
          </button>
        )}
      </div>
    </div>
  );
}
