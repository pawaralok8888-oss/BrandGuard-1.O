import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { EditorContent, useEditor } from "@tiptap/react";
import { Extension } from "@tiptap/core";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";
import type { Node as ProseNode } from "@tiptap/pm/model";
import StarterKit from "@tiptap/starter-kit";
import Link from "@tiptap/extension-link";
import Underline from "@tiptap/extension-underline";
import { ArrowLeft, Check, CheckCheck, ChevronDown, CircleHelp, FileImage, History, Image as ImageIcon, Instagram, Link2, List, ListOrdered, LoaderCircle, Paperclip, Save, ShieldCheck, Sparkles, X } from "lucide-react";
import {
  ASSET_FORMAT_OPTIONS,
  createContent,
  deleteContentImage,
  getContent,
  loadContentImageUrl,
  updateContent,
  uploadContentImage,
  type AssetFormat,
  type ContentChannel,
  type ContentInput,
} from "@/api/content";
import { listFindings, runCheck as runCheckApi, type Finding } from "@/api/checks";
import { listSources } from "@/api/sources";
import { submitForReview } from "@/api/review";
import { decideFinding, type DecisionInput } from "@/api/findings";
import { wordDiff } from "@/lib/diff";
import type { BrandSource } from "@/types";
import { SeverityBadge } from "@/components/shared/SeverityBadge";
import { SourceChip } from "@/components/shared/SourceChip";
import SourceDrawer from "@/components/shared/SourceDrawer";
import { LoadingState } from "@/components/shared/LoadingState";
import { ErrorState } from "@/components/shared/ErrorState";
import { cn } from "@/lib/utils";

const SAMPLE_TITLE = "Face wash launch caption";
const SAMPLE_CHANNEL: ContentChannel = "Instagram";
const SAMPLE_TEXT = "Get naturally glowing skin with GreenGlow Tea Tree Face Wash! Removes all acne overnight and gives you 100% clear skin. Made with natural ingredients and dermatologically tested.";

type MainTab = "Content" | "Preview" | "History";
/** Statuses in which the creator may still edit the draft and its findings. */
const EDITABLE_STATUSES = ["Draft", "Checked", "Fixing", "Changes requested"];
type Filter = "All" | "Critical" | "Warning" | "Info" | "Resolved";
type RunState = "idle" | "loading" | "done" | "error";
type HighlightRange = { id: string; severity: Finding["severity"]; from: number; to: number };
type TextChunk = { text: string; from: number; plainStart: number };

const highlightKey = new PluginKey<DecorationSet>("findingHighlights");

/** Draws finding highlights as decorations. They are never saved into the HTML. */
const FindingHighlights = Extension.create({
  name: "findingHighlights",
  addProseMirrorPlugins() {
    return [
      new Plugin<DecorationSet>({
        key: highlightKey,
        state: {
          init: () => DecorationSet.empty,
          apply(tr, old) {
            const ranges = tr.getMeta(highlightKey) as HighlightRange[] | undefined;
            if (ranges) {
              return DecorationSet.create(
                tr.doc,
                ranges.map((r) =>
                  Decoration.inline(r.from, r.to, {
                    class: "finding-highlight",
                    "data-severity": r.severity,
                    "data-finding-id": r.id,
                  }),
                ),
              );
            }
            return tr.docChanged ? old.map(tr.mapping, tr.doc) : old;
          },
        },
        props: {
          decorations(state) {
            return highlightKey.getState(state);
          },
        },
      }),
    ];
  },
});

/**
 * Builds the plain text the backend sees, and maps each character back to a ProseMirror position.
 * Blocks are separated by "\n". The same function is used for body_text and for highlights, so offsets match.
 */
function textMapOf(doc: ProseNode): { plain: string; chunks: TextChunk[] } {
  const chunks: TextChunk[] = [];
  let plain = "";
  doc.descendants((node, pos) => {
    if (node.isTextblock && plain.length > 0) plain += "\n";
    if (node.isText && node.text) {
      chunks.push({ text: node.text, from: pos, plainStart: plain.length });
      plain += node.text;
    }
    return true;
  });
  return { plain, chunks };
}

function plainTextOf(doc: ProseNode): string {
  return textMapOf(doc).plain;
}

function toDocRange(chunks: TextChunk[], start: number, end: number): { from: number; to: number } | null {
  let from: number | null = null;
  let to: number | null = null;
  for (const c of chunks) {
    const cStart = c.plainStart;
    const cEnd = c.plainStart + c.text.length;
    if (cEnd <= start || cStart >= end) continue;
    const s = Math.max(start, cStart);
    const e = Math.min(end, cEnd);
    if (from === null) from = c.from + (s - cStart);
    to = c.from + (e - cStart);
  }
  return from !== null && to !== null && to > from ? { from, to } : null;
}

function escapeHtml(value: string): string {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function textToHtml(text: string): string {
  return text.split("\n").map((line) => `<p>${escapeHtml(line)}</p>`).join("");
}

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}

function Tool({ label, children, onClick }: { label: string; children: ReactNode; onClick: () => void }) {
  return <button type="button" title={label} aria-label={label} onClick={onClick} className="toolbar-btn min-h-[36px] min-w-[36px] sm:min-h-[27px] sm:min-w-[27px]">{children}</button>;
}

export default function ComposePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const contentId = searchParams.get("id");
  // Set when this page creates the draft itself, so the reload effect does not wipe fresh check results.
  const skipReloadId = useRef<string | null>(null);

  const [title, setTitle] = useState(SAMPLE_TITLE);
  const [channel, setChannel] = useState<string>(SAMPLE_CHANNEL);
  const [contentStatus, setContentStatus] = useState("Draft");
  const [tab, setTab] = useState<MainTab>("Content");
  const [findings, setFindings] = useState<Finding[]>([]);
  const [filter, setFilter] = useState<Filter>("All");
  const [activeId, setActiveId] = useState<string | null>(null);
  const [sourceId, setSourceId] = useState<string | null>(null);
  const [runState, setRunState] = useState<RunState>("idle");
  const [checkError, setCheckError] = useState("");
  const [aiFallback, setAiFallback] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [rejectId, setRejectId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [toast, setToast] = useState("");
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [attachment, setAttachment] = useState("");
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [format, setFormat] = useState<AssetFormat>("");
  const [pendingImage, setPendingImage] = useState<File | null>(null);
  const [hasSavedImage, setHasSavedImage] = useState(false);
  const [imageIsLogo, setImageIsLogo] = useState(false);
  const [sources, setSources] = useState<BrandSource[]>([]);
  const [altText, setAltText] = useState("GreenGlow sunscreen bottle on a light background with green leaves");

  const [sourcesLoading, setSourcesLoading] = useState(true);
  const [sourcesError, setSourcesError] = useState<string | null>(null);
  const [contentLoading, setContentLoading] = useState(Boolean(contentId));
  const [contentError, setContentError] = useState<string | null>(null);

  const notify = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(""), 2400);
  };

  const editor = useEditor({
    extensions: [StarterKit, Underline, Link.configure({ openOnClick: false }), FindingHighlights],
    content: "",
    editorProps: { attributes: { class: "compose-editor focus:outline-none", "aria-label": "Social media post editor" } },
  });

  /** Draws highlights for the open findings, using the same plain-text offsets the backend used. */
  const applyHighlights = (list: Finding[]) => {
    if (!editor) return;
    const { chunks } = textMapOf(editor.state.doc);
    const ranges: HighlightRange[] = [];
    for (const f of list) {
      if (f.status !== "open" || f.start === null || f.end === null) continue;
      const range = toDocRange(chunks, f.start, f.end);
      if (range) ranges.push({ id: f.id, severity: f.severity, ...range });
    }
    editor.view.dispatch(editor.state.tr.setMeta(highlightKey, ranges));
  };

  /** Uploads the picked image to the saved draft, so the image checks can read it on the next check. */
  const withPendingImage = async (id: string): Promise<string> => {
    if (pendingImage) {
      await uploadContentImage(id, pendingImage, altText.trim(), imageIsLogo);
      setPendingImage(null);
      setHasSavedImage(true);
    }
    return id;
  };

  const attachImage = (file: File) => {
    if (imageUrl?.startsWith("blob:")) URL.revokeObjectURL(imageUrl);
    setPendingImage(file);
    setAttachment(file.name);
    setImageUrl(URL.createObjectURL(file));
  };

  const removeImage = async () => {
    if (hasSavedImage && contentId) {
      try {
        await deleteContentImage(contentId);
      } catch (error: unknown) {
        notify(`Could not remove the image: ${errorText(error)}`);
        return;
      }
    }
    if (imageUrl?.startsWith("blob:")) URL.revokeObjectURL(imageUrl);
    setPendingImage(null);
    setAttachment("");
    setImageUrl(null);
    setHasSavedImage(false);
    setImageIsLogo(false);
  };

  /** Saves the draft (creates it if new). Returns the content ID, or null if saving failed. */
  const persistDraft = async (): Promise<string | null> => {
    if (!editor) {
      notify("The editor is not ready yet.");
      return null;
    }
    if (!title.trim()) {
      notify("Enter a title before saving.");
      return null;
    }
    const bodyText = plainTextOf(editor.state.doc);
    const bodyHtml = editor.getHTML();
    setSaving(true);
    try {
      if (contentId) {
        await updateContent(contentId, {
          title: title.trim(),
          channel: channel as ContentChannel,
          bodyText,
          bodyHtml,
          altText: altText.trim() || null,
          format,
        });
        return withPendingImage(contentId);
      }
      const input: ContentInput = {
        title: title.trim(),
        channel: channel as ContentChannel,
        team: "Marketing",
        bodyText,
        bodyHtml,
        altText: altText.trim() || null,
        format,
        imageUrl: null,
      };
      const created = await createContent(input);
      skipReloadId.current = created.id;
      setSearchParams((current) => {
        const next = new URLSearchParams(current);
        next.set("id", created.id);
        return next;
      }, { replace: true });
      return withPendingImage(created.id);
    } catch (error: unknown) {
      notify(`Save failed: ${errorText(error)}`);
      return null;
    } finally {
      setSaving(false);
    }
  };

  const saveDraft = async () => {
    const id = await persistDraft();
    if (id) notify("Draft saved successfully.");
  };

  const fetchSources = useCallback(async () => {
    setSourcesLoading(true);
    setSourcesError(null);
    try {
      const list = await listSources();
      setSources(list);
    } catch (error: unknown) {
      setSourcesError(errorText(error));
    } finally {
      setSourcesLoading(false);
    }
  }, []);

  const fetchContent = useCallback(async (id: string | null) => {
    if (!editor) return;
    if (!id) {
      setContentLoading(false);
      setContentError(null);
      setTitle(SAMPLE_TITLE);
      setChannel(SAMPLE_CHANNEL);
      setFindings([]);
      setFormat("");
      setPendingImage(null);
      setHasSavedImage(false);
      setRunState("idle");
      editor.commands.setContent(`<p>${escapeHtml(SAMPLE_TEXT)}</p>`);
      return;
    }
    if (skipReloadId.current === id) {
      skipReloadId.current = null;
      setContentLoading(false);
      setContentError(null);
      return;
    }
    setContentLoading(true);
    setContentError(null);
    try {
      const [record, existing] = await Promise.all([
        getContent(id),
        listFindings(id).catch(() => [] as Finding[]),
      ]);
      setTitle(record.title);
      setChannel(record.channel);
      setContentStatus(record.status);
      setAltText(record.altText ?? "");
      setFormat(record.format ?? "");
      setHasSavedImage(Boolean(record.imageUrl));
      setImageIsLogo(Boolean(record.imageIsLogo));
      setImageUrl(record.imageUrl ? await loadContentImageUrl(id).catch(() => null) : null);
      editor.commands.setContent(record.bodyHtml || textToHtml(record.bodyText));
      setFindings(existing);
      applyHighlights(existing);
    } catch (error: unknown) {
      setContentError(errorText(error));
    } finally {
      setContentLoading(false);
    }
  }, [editor]);

  // Load approved sources once so source chips and the drawer show the real database records.
  useEffect(() => {
    void fetchSources();
  }, [fetchSources]);

  // Load the draft (or the sample) when the page opens or the ID changes.
  useEffect(() => {
    if (editor) {
      void fetchContent(contentId);
    }
  }, [contentId, editor, fetchContent]);

  const handleRetryInitial = () => {
    void fetchSources();
    if (contentId) {
      void fetchContent(contentId);
    }
  };

  const initialLoading = sourcesLoading || contentLoading;
  const initialError = sourcesError || contentError;

  const handleRunCheck = async () => {
    setRunState("loading");
    setCheckError("");
    setAiFallback(false);
    const id = await persistDraft();
    if (!id) {
      setRunState("error");
      setCheckError("The draft could not be saved, so the check did not run.");
      return;
    }
    try {
      const result = await runCheckApi(id);
      setFindings(result.findings);
      setAiFallback(result.rulesOnlyFallback === true || result.aiStatus === "fallback");
      setActiveId(null);
      applyHighlights(result.findings);
      setRunState("done");
      // The check moves a draft to Checked on the server, so refresh the status shown here.
      const fresh = await getContent(id).catch(() => null);
      if (fresh) setContentStatus(fresh.status);
      const open = result.findings.filter((f) => f.status === "open").length;
      notify(open ? `${open} issue${open === 1 ? "" : "s"} found` : "No issues found");
    } catch (error: unknown) {
      setRunState("error");
      setCheckError(errorText(error));
    }
  };

  /** Applies accept, edit or reject. Accept and edit save the draft first so offsets match the stored text. */
  const decideOn = async (finding: Finding, input: DecisionInput) => {
    if (input.action !== "reject") {
      const id = await persistDraft();
      if (!id) return;
    }
    setBusyId(finding.id);
    try {
      const result = await decideFinding(finding.id, input);
      if (input.action !== "reject") editor?.commands.setContent(textToHtml(result.bodyText));
      setContentStatus(result.contentStatus);
      setFindings(result.findings);
      applyHighlights(result.findings);
      setEditId(null);
      setRejectId(null);
      notify(
        input.action === "reject" ? "Suggestion rejected"
          : input.action === "edit" ? "Edited suggestion applied"
          : "Suggestion applied to the draft",
      );
    } catch (error: unknown) {
      notify(`Could not apply the decision: ${errorText(error)}`);
    } finally {
      setBusyId(null);
    }
  };

  const jumpTo = (finding: Finding) => {
    setActiveId(finding.id);
    document.querySelector<HTMLElement>(`.compose-editor [data-finding-id="${finding.id}"]`)
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const handleSubmitForReview = async () => {
    if (criticalCount > 0) return;
    setSubmitting(true);
    try {
      const id = await persistDraft();
      if (!id) return;
      const result = await submitForReview(id);
      setContentStatus(result.status);
      notify("Submitted for review");
    } catch (error: unknown) {
      notify(`Could not submit: ${errorText(error)}`);
    } finally {
      setSubmitting(false);
    }
  };

  const handleEditorClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const el = (e.target as HTMLElement).closest<HTMLElement>("[data-finding-id]");
    const id = el?.dataset.findingId;
    if (!id) return;
    setActiveId(id);
    document.getElementById(`finding-card-${id}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const handleEditorHover = (e: React.MouseEvent<HTMLDivElement>) => {
    const id = (e.target as HTMLElement).closest<HTMLElement>("[data-finding-id]")?.dataset.findingId;
    if (id) setActiveId(id);
  };

  const loadSample = () => {
    setTitle(SAMPLE_TITLE);
    setChannel(SAMPLE_CHANNEL);
    editor?.commands.setContent(`<p>${escapeHtml(SAMPLE_TEXT)}</p>`);
    setFindings([]);
    applyHighlights([]);
    setRunState("idle");
    notify("Sample draft loaded. Run check to see findings.");
  };

  const visibleFindings = useMemo(() => findings.filter((f) => {
    if (filter === "All") return f.status === "open";
    if (filter === "Resolved") return f.status !== "open";
    return f.status === "open" && f.severity === filter.toLowerCase();
  }), [findings, filter]);

  const openFindings = findings.filter((f) => f.status === "open");
  const criticalCount = openFindings.filter((f) => f.severity === "critical").length;
  const countFor = (severity: string) => openFindings.filter((f) => f.severity === severity).length;
  const activeFinding = openFindings.find((f) => f.id === activeId) ?? null;
  const selectedSource: BrandSource | null = sources.find((s) => s.id === sourceId) ?? null;
  const sourceCategory = (id: string) => sources.find((s) => s.id === id)?.category ?? "Guideline";
  const wordCount = editor ? plainTextOf(editor.state.doc).length : 0;
  const inReview = contentStatus === "In Review" || contentStatus === "Approved" || contentStatus === "Published";
  const locked = !EDITABLE_STATUSES.includes(contentStatus);
  const statusLabel = runState === "loading" ? "Checking…" : contentStatus;
  const altValid = altText.trim().length >= 20 && altText.trim().length <= 150 && !/^(image|photo|picture)( of)?$/i.test(altText.trim());
  const busy = busyId !== null;

  /** Stepper state. The check is one API call, so only Rules is marked current while it runs. */
  const stepClass = (step: "rules" | "evidence" | "ai") => {
    if (runState === "done") return step === "ai" && aiFallback ? "step-warn" : "step-done";
    if (runState === "error") return step === "rules" ? "step-warn" : "step-muted";
    if (runState === "loading") return step === "rules" ? "step-current" : "step-muted";
    return "step-muted";
  };

  return <div className="compose-workspace">
    <header className="compose-page-header flex flex-wrap items-center gap-2.5 p-1 w-full">
      <button type="button" className="compose-back min-h-[40px] min-w-[40px] sm:min-h-[27px] sm:min-w-[27px] shrink-0" aria-label="Back to content" onClick={() => notify("Content list is available from the sidebar")}><ArrowLeft size={16} /></button>
      <span className="channel-icon shrink-0"><Instagram size={17} /></span>
      <div className="compose-heading min-w-0"><h1>Social Media Post</h1><p>Draft - {channel}</p></div>
      <span className={cn("compose-status shrink-0", runState === "loading" && "status-loading")}>{runState === "loading" && <LoaderCircle size={12} className="animate-spin" />}{statusLabel}</span>
      <div className="check-stepper max-w-full overflow-x-auto">
        <span className={stepClass("rules")}>Rules</span><i />
        <span className={stepClass("evidence")}>Evidence</span><i />
        <span className={stepClass("ai")}>AI analysis</span><i />
        <span className={runState === "done" ? "step-done" : "step-muted"}>{runState === "done" ? "Done" : ""}</span>
      </div>
    </header>

    {initialLoading ? (
      <div className="p-4 md:p-6 w-full">
        <LoadingState label="Loading draft and brand sources" rows={6} />
      </div>
    ) : initialError ? (
      <div className="p-4 md:p-6 w-full max-w-xl mx-auto">
        <ErrorState
          title="Could not load draft workspace"
          description={initialError}
          onRetry={handleRetryInitial}
        />
      </div>
    ) : (
      <div className="compose-columns flex flex-col lg:grid lg:grid-cols-[minmax(0,1.62fr)_minmax(0,1fr)] w-full gap-4">
        <section className="compose-panel editor-panel">
          <div className="panel-tabs" role="tablist" aria-label="Draft views">
            {(["Content", "Preview", "History"] as MainTab[]).map((item) => <button key={item} role="tab" aria-selected={tab === item} onClick={() => setTab(item)} className={cn("panel-tab", tab === item && "panel-tab-active")}>{item === "Content" ? <FileImage size={14} /> : item === "Preview" ? <ImageIcon size={14} /> : <History size={14} />}{item}</button>)}
            <span className="autosaved"><span /> Autosaved</span>
          </div>

          {tab === "History" ? <div className="editor-scroll history-view">
            <h3>Revision history</h3>
            <p className="history-hint">Full revision history is shown on the Review screen once the draft is submitted.</p>
          </div> : tab === "Preview" ? <div className="editor-scroll preview-view">
            <div className="preview-social">
              <div className="preview-brand"><span className="greenglow-mark">G</span><div><strong>GreenGlow</strong><small>Sponsored · {channel}</small></div></div>
              {imageUrl && <img src={imageUrl} alt={altText} />}
              {!imageUrl && <div className="preview-image-placeholder"><ImageIcon size={25} /><span>GreenGlow campaign image</span></div>}
              <p>{editor ? plainTextOf(editor.state.doc) : ""}</p>
            </div>
          </div> : <>
            <div className="draft-meta-row flex flex-col sm:flex-row gap-2 w-full">
              <input aria-label="Draft title" value={title} onChange={(e) => setTitle(e.target.value)} className="min-h-[40px] w-full" />
              <label className="channel-select min-h-[40px] w-full sm:w-[130px] shrink-0"><span className="sr-only">Channel</span><select value={channel} onChange={(e) => setChannel(e.target.value)} className="h-full min-h-[40px] w-full"><option>Instagram</option><option>Website</option><option>Email</option><option>Ad</option></select><ChevronDown size={13} /></label><label className="channel-select min-h-[40px] w-full sm:w-[170px] shrink-0"><span className="sr-only">Asset type</span><select aria-label="Asset type" value={format} onChange={(e) => setFormat(e.target.value as AssetFormat)} className="h-full min-h-[40px] w-full">{ASSET_FORMAT_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select><ChevronDown size={13} /></label>
            </div>
            <div className="editor-toolbar flex items-center overflow-x-auto max-w-full py-1 min-h-[40px]">
              <select aria-label="Text style" defaultValue="paragraph" className="min-h-[32px] sm:min-h-[27px]"><option value="paragraph">Paragraph</option><option value="heading">Heading</option></select>
              <span className="toolbar-divider" />
              <Tool label="Bold" onClick={() => editor?.chain().focus().toggleBold().run()}><b>B</b></Tool>
              <Tool label="Italic" onClick={() => editor?.chain().focus().toggleItalic().run()}><i>I</i></Tool>
              <Tool label="Underline" onClick={() => editor?.chain().focus().toggleUnderline().run()}><u>U</u></Tool>
              <Tool label="Add link" onClick={() => { const url = window.prompt("Enter URL"); if (url) editor?.chain().focus().setLink({ href: url }).run(); }}><Link2 size={15} /></Tool>
              <span className="toolbar-divider" />
              <Tool label="Bullet list" onClick={() => editor?.chain().focus().toggleBulletList().run()}><List size={16} /></Tool>
              <Tool label="Numbered list" onClick={() => editor?.chain().focus().toggleOrderedList().run()}><ListOrdered size={16} /></Tool>
              <button type="button" className="toolbar-help min-h-[32px] min-w-[32px] flex items-center justify-center" title="Run check to see brand findings" onClick={() => notify("Run check to see brand findings")}><CircleHelp size={14} /></button>
            </div>
            <div className="editor-scroll editor-body">
              <div className="editor-inline-status"><span className="green-dot" /> Approved brand workspace <span className="inline-status-right">English · {channel}</span></div>
              <div className="editor-copy-wrap" onClick={handleEditorClick} onMouseOver={handleEditorHover}>
                <EditorContent editor={editor} />
                {activeFinding && <div className="issue-popover"><span className="popover-dot" /><div><strong>{activeFinding.title}</strong><small>{activeFinding.reason}</small></div></div>}
              </div>
              {imageUrl ? <div className="attached-image"><img src={imageUrl} alt={altText || "Uploaded campaign image"} /><button type="button" aria-label="Remove image" onClick={removeImage}><X size={13} /></button></div>
                : <div className="attached-image mock-attached"><div className="mock-product"><span>GreenGlow</span><b>Sun<br />Screen</b><small>SPF 50</small></div><div className="mock-leaves">✦</div><div className="mock-copy">Naturally fresh,<br />every day</div></div>}
              <div className="image-alt-row flex flex-col sm:flex-row gap-2">
                <label className="flex-1">Image alt text <input value={altText} onChange={(e) => setAltText(e.target.value)} placeholder="Describe the meaningful content of the image" className="min-h-[40px] w-full" /></label>
                <span className={cn("alt-validity shrink-0", altValid ? "valid" : "invalid")}>{altValid ? <Check size={12} /> : <CircleHelp size={12} />}{altValid ? "Valid" : "Needs review"}</span>
                <label className="flex items-center gap-2 text-xs text-slate-600" title="Set this before adding the image. The logo check compares it with the approved logo.">
                  <input type="checkbox" checked={imageIsLogo} onChange={(e) => setImageIsLogo(e.target.checked)} />
                  This image is our logo
                </label>
              </div>
            </div>
            <div className="editor-attachment-bar flex flex-wrap items-center gap-2">
              <label className="attach-action min-h-[40px] inline-flex items-center"><Paperclip size={14} /> Add image<input type="file" accept="image/png,image/jpeg,image/webp" aria-label="Choose an image" onChange={(e) => { const file = e.target.files?.[0]; if (file) attachImage(file); e.target.value = ""; }} /></label>
              {attachment && <span className="attachment-name">{attachment}</span>}
              <span className="char-count ml-auto">{wordCount}/5000 characters</span>
            </div>
          </>}

          <div className="editor-action-bar flex flex-wrap gap-2 p-3">
            <button type="button" onClick={() => void saveDraft()} disabled={saving || busy || submitting || runState === "loading"} className="btn-secondary min-h-[40px] flex-1 sm:flex-none justify-center">{saving ? <LoaderCircle size={14} className="animate-spin" /> : <Save size={14} />}{saving ? "Saving…" : "Save draft"}</button>
            <button type="button" onClick={loadSample} disabled={busy || saving || submitting || runState === "loading"} className="btn-secondary min-h-[40px] flex-1 sm:flex-none justify-center">Load sample draft</button>
            <button type="button" onClick={() => void handleRunCheck()} disabled={runState === "loading" || busy || saving || submitting} className="btn-secondary min-h-[40px] flex-1 sm:flex-none justify-center">{runState === "loading" ? <LoaderCircle size={14} className="animate-spin" /> : <ShieldCheck size={14} />} Run check</button>
            <button type="button" onClick={() => void handleSubmitForReview()} disabled={criticalCount > 0 || inReview || submitting || busy || saving || runState === "loading"} title={criticalCount ? `Resolve ${criticalCount} critical finding${criticalCount === 1 ? "" : "s"} before submitting` : undefined} className="btn-primary min-h-[40px] flex-1 sm:flex-none justify-center">{submitting ? <LoaderCircle size={14} className="animate-spin" /> : inReview ? <CheckCheck size={14} /> : <Check size={14} />}{inReview ? "Submitted for review" : "Submit for review"}</button>
            {criticalCount > 0 && <span className="submit-explanation w-full">Resolve {criticalCount} critical issue{criticalCount === 1 ? "" : "s"} first</span>}
            {contentStatus === "Changes requested" && <span className="submit-explanation w-full">Changes requested by the reviewer. Fix the draft and submit again.</span>}
            {inReview && contentStatus === "In Review" && <span className="submit-explanation w-full">Editing is locked until the reviewer responds.</span>}
          </div>
        </section>

        <aside className="compose-panel findings-panel">
          <div className="findings-header">
            <div className="findings-title"><span className="shield-icon"><ShieldCheck size={17} /></span><div><h2>Findings ({openFindings.length})</h2><p><span className="count-critical">{countFor("critical")} critical</span><span className="count-warning">{countFor("warning")} warning</span><span className="count-info">{countFor("info")} info</span></p></div></div>
            <button type="button" className="view-all" onClick={() => setFilter("All")}>View all <span>→</span></button>
          </div>
          <div className="finding-filters overflow-x-auto max-w-full" role="tablist" aria-label="Filter findings">
            {(["All", "Critical", "Warning", "Info", "Resolved"] as Filter[]).map((f) => <button key={f} role="tab" aria-selected={filter === f} onClick={() => setFilter(f)} className={cn("finding-filter min-h-[36px] sm:min-h-[28px]", filter === f && "filter-active")}>{f}{f === "Critical" && countFor("critical") > 0 ? ` ${countFor("critical")}` : ""}</button>)}
          </div>

          {aiFallback && <div role="status" style={{ margin: "8px 10px 0", padding: "8px 10px", border: "1px solid #f2d5a1", borderRadius: 8, background: "#fff8e6", color: "#92400e", fontSize: 11, lineHeight: 1.45 }}><strong>AI check unavailable.</strong> These results come from brand rules only. Run the check again later for AI findings.</div>}
          <div className="findings-scroll">
            {runState === "loading" ? <div className="state-message"><LoaderCircle size={23} className="animate-spin" /><strong>Checking your content…</strong><span>Brand rules are running.</span></div>
            : runState === "error" ? <div className="state-message warning-state"><CircleHelp size={23} /><strong>Check could not run</strong><span>{checkError}</span><button type="button" onClick={() => void handleRunCheck()}>Retry check</button></div>
            : runState === "idle" && findings.length === 0 ? <div className="state-message"><ShieldCheck size={24} /><strong>Not checked yet</strong><span>Press Run check to see brand findings for this draft.</span></div>
            : visibleFindings.length === 0 ? <div className="state-message"><CheckCheck size={24} /><strong>{filter === "Resolved" ? "No resolved findings yet" : "No issues found"}</strong><span>{filter === "Resolved" ? "Accepted or rejected findings appear here." : "No findings match this filter."}</span></div>
            : visibleFindings.map((finding) => <article
                key={finding.id}
                id={`finding-card-${finding.id}`}
                onClick={() => jumpTo(finding)}
                onMouseEnter={() => setActiveId(finding.id)}
                className={cn("compact-finding", `finding-${finding.severity}`, activeId === finding.id && "compact-finding-active", finding.status !== "open" && "resolved-finding")}
              >
                <div className="finding-topline"><SeverityBadge severity={finding.severity} /><h3>{finding.title}</h3><span className="confidence-pill">{Math.round(finding.confidence * 100)}%</span></div>
                <p className="finding-reason">{finding.reason}</p>
                {finding.originalText && <p className="finding-original">“{finding.originalText}”</p>}
                <div className="source-line">
                  <SourceChip sourceId={finding.sourceId} version={finding.sourceVersion} category={sourceCategory(finding.sourceId) as BrandSource["category"]} onClick={() => setSourceId(finding.sourceId)} />
                  {finding.aiGenerated && <span className="ai-label"><Sparkles size={11} /> AI suggestion</span>}
                  {finding.needsHumanReview && <span style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 11, color: "#92400e" }}><CircleHelp size={11} /> Needs human review</span>}
                </div>
                {finding.suggestedFix && <div className="rewrite-box"><div className="rewrite-label"><Sparkles size={12} /> Suggested rewrite</div><p>{finding.suggestedFix}</p></div>}

                {finding.status === "open" ? <div className="finding-actions grid grid-cols-3 gap-2 mt-2">
                  <button type="button" className="accept-button min-h-[40px] sm:min-h-[28px]" disabled={busy || locked || saving || submitting} onClick={(e) => { e.stopPropagation(); void decideOn(finding, { action: "accept" }); }}>{busyId === finding.id ? <LoaderCircle size={12} className="animate-spin" /> : <Check size={12} />} Accept</button>
                  <button type="button" className="edit-button min-h-[40px] sm:min-h-[28px]" disabled={busy || locked || saving || submitting} onClick={(e) => { e.stopPropagation(); setRejectId(null); setEditId(finding.id); setEditText(finding.suggestedFix); }}>Edit</button>
                  <button type="button" className="reject-button min-h-[40px] sm:min-h-[28px]" disabled={busy || locked || saving || submitting} onClick={(e) => { e.stopPropagation(); setEditId(null); setRejectId(rejectId === finding.id ? null : finding.id); setRejectReason(""); }}>Reject</button>
                </div> : <div className="resolved-note"><CheckCheck size={13} /> {finding.status === "rejected" ? "Rejected" : finding.status === "edited" ? "Edited and applied" : finding.status === "accepted" ? "Accepted and applied" : "Resolved by a later edit"}</div>}

                {editId === finding.id && <div className="inline-edit" onClick={(e) => e.stopPropagation()}>
                  <textarea value={editText} onChange={(e) => setEditText(e.target.value)} rows={2} aria-label="Edited suggestion" className="w-full" />
                  <div className="edit-diff" aria-label="Changes preview">
                    <span className="edit-diff-label">Original vs. proposed</span>
                    <p className="text-sm leading-relaxed">
                      {wordDiff(finding.originalText ?? "", editText).map((part, idx) => (
                        <span key={idx} className={cn(part.kind === "removed" && "bg-red-100 text-red-700 line-through", part.kind === "added" && "bg-emerald-100 text-emerald-800")}>{part.text}</span>
                      ))}
                    </p>
                  </div>
                  <div className="flex gap-2 justify-end mt-2">
                    <button type="button" disabled={busy || saving || submitting} className="min-h-[40px] sm:min-h-[28px] px-3" onClick={() => setEditId(null)}>Cancel</button>
                    <button type="button" disabled={busy || saving || submitting || !editText.trim()} className="min-h-[40px] sm:min-h-[28px] px-3" onClick={() => void decideOn(finding, { action: "edit", editedText: editText.trim() })}>Apply edit</button>
                  </div>
                </div>}

                {rejectId === finding.id && <div className="inline-edit" onClick={(e) => e.stopPropagation()}>
                  <label>Reason (optional)<textarea value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} rows={2} placeholder="Why is this suggestion unsuitable?" className="w-full" /></label>
                  <div className="flex gap-2 justify-end mt-2">
                    <button type="button" disabled={busy || saving || submitting} className="min-h-[40px] sm:min-h-[28px] px-3" onClick={() => setRejectId(null)}>Cancel</button>
                    <button type="button" disabled={busy || saving || submitting} className="min-h-[40px] sm:min-h-[28px] px-3" onClick={() => void decideOn(finding, { action: "reject", rejectReason: rejectReason.trim() || undefined })}>Confirm reject</button>
                  </div>
                </div>}
              </article>)}
          </div>
        </aside>
      </div>
    )}

    <SourceDrawer source={selectedSource} onClose={() => setSourceId(null)} onCopy={(id) => notify(`Copied ${id}`)} />
    {toast && <div className="compose-toast" role="status">{toast}<button type="button" onClick={() => setToast("")} aria-label="Dismiss"><X size={13} /></button></div>}
  </div>;
}
