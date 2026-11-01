import type { Finding } from "@/types";
import { SeverityBadge } from "@/components/shared/SeverityBadge";

const VISUAL_TYPES: Finding["type"][] = ["image", "accessibility"];

type VisualFindingsViewProps = {
  imageUrl: string;
  alt: string;
  findings: Finding[];
  className?: string;
};

/**
 * The image with each visual finding's region drawn over it. Findings without a region
 * (bbox is null) are listed below the image. Every visual finding is a suggestion for a person to check.
 */
export function VisualFindingsView({ imageUrl, alt, findings, className }: VisualFindingsViewProps) {
  const visual = findings.filter((f) => VISUAL_TYPES.includes(f.type));
  const boxed = visual.filter((f) => f.bbox !== null);
  const whole = visual.filter((f) => f.bbox === null);

  return (
    <div className={className}>
      <div className="relative inline-block max-w-full overflow-hidden rounded-lg border border-slate-200">
        <img src={imageUrl} alt={alt} className="block max-w-full" />
        {boxed.map((finding) => {
          const [x, y, w, h]: [number, number, number, number] = finding.bbox ?? [0, 0, 0, 0];
          return (
            <div
              key={finding.id}
              title={`${finding.title}: ${finding.reason}`}
              className="absolute border-2 border-red-600 bg-red-500/10"
              style={{ left: `${x * 100}%`, top: `${y * 100}%`, width: `${w * 100}%`, height: `${h * 100}%` }}
            />
          );
        })}
      </div>

      {visual.length > 0 && (
        <ul className="mt-3 space-y-2">
          {visual.map((finding) => (
            <li key={finding.id} className="rounded-lg border border-slate-200 bg-white px-3 py-2">
              <div className="flex items-center gap-2">
                <SeverityBadge severity={finding.severity} />
                <p className="text-sm font-medium text-slate-900">{finding.title}</p>
                {finding.bbox === null && <span className="text-xs text-slate-500">· whole image</span>}
              </div>
              <p className="mt-1 text-xs text-slate-700">{finding.reason}</p>
              {finding.suggestedFix && (
                <p className="mt-1 text-xs text-slate-600">Suggested fix: {finding.suggestedFix}</p>
              )}
              {finding.needsHumanReview && (
                <p className="mt-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  Suggestion: a person should check this
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
      {boxed.length === 0 && whole.length === 0 && (
        <p className="mt-3 text-sm text-slate-500">No visual findings.</p>
      )}
    </div>
  );
}
