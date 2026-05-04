import { AlertTriangle, CheckCircle2, ExternalLink, FileText, ShieldCheck } from "lucide-react";

import { IssueDraft } from "../api/client";

type IssueDraftPanelProps = {
  draft: IssueDraft | null;
  isApprovingIssue: boolean;
  onApproveIssue: (issueId: number) => void;
};

export function IssueDraftPanel({ draft, isApprovingIssue, onApproveIssue }: IssueDraftPanelProps) {
  if (!draft) {
    return (
      <section className="rounded-lg border border-line bg-white p-5 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded border border-line bg-panel text-slate-600">
            <FileText size={18} aria-hidden="true" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-ink">Issue Draft</h3>
            <p className="text-sm text-slate-600">Retrieve code evidence before drafting an issue.</p>
          </div>
        </div>
      </section>
    );
  }

  const hasWarnings = draft.warnings.length > 0;
  const isCreated = draft.status === "issue_created";
  const isApprovedLocal = draft.status === "approved";

  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3">
          <div
            className={`grid h-9 w-9 place-items-center rounded border ${
              hasWarnings
                ? "border-amber-200 bg-amber-50 text-amber-700"
                : "border-emerald-200 bg-emerald-50 text-emerald-700"
            }`}
          >
            {hasWarnings ? <AlertTriangle size={18} aria-hidden="true" /> : <ShieldCheck size={18} aria-hidden="true" />}
          </div>
          <div>
            <h3 className="text-sm font-semibold text-ink">{draft.title}</h3>
            <p className="text-sm text-slate-600">Draft #{draft.id} · {draft.status}</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <span className="rounded border border-line bg-panel px-2 py-1 text-xs font-semibold text-slate-700">
            {draft.priority_label}
          </span>
          <span className="rounded border border-line bg-panel px-2 py-1 text-xs font-semibold text-slate-700">
            {draft.confidence_level} confidence
          </span>
          <span
            className={`rounded border px-2 py-1 text-xs font-semibold ${
              hasWarnings
                ? "border-amber-200 bg-amber-50 text-amber-800"
                : "border-emerald-200 bg-emerald-50 text-emerald-700"
            }`}
          >
            {hasWarnings ? `${draft.warnings.length} warning${draft.warnings.length === 1 ? "" : "s"}` : "Guard clear"}
          </span>
        </div>
      </div>

      <div className="mt-4 flex flex-col gap-3 rounded border border-line bg-panel p-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="text-sm text-slate-700">
          {isCreated ? (
            <span className="inline-flex items-center gap-2 font-medium text-emerald-700">
              <CheckCircle2 size={16} aria-hidden="true" />
              Created on GitHub
            </span>
          ) : isApprovedLocal ? (
            <span className="inline-flex items-center gap-2 font-medium text-signal">
              <CheckCircle2 size={16} aria-hidden="true" />
              Approved locally
            </span>
          ) : (
            "Human approval is required before creating a GitHub issue."
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          {draft.github_issue_url ? (
            <a
              className="inline-flex items-center justify-center gap-2 rounded border border-line bg-white px-3 py-2 text-sm font-semibold text-ink transition hover:border-signal hover:text-signal"
              href={draft.github_issue_url}
              target="_blank"
              rel="noreferrer"
            >
              <ExternalLink size={16} aria-hidden="true" />
              Open Issue
            </a>
          ) : null}
          <button
            className="rounded bg-signal px-3 py-2 text-sm font-semibold text-white transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:bg-slate-400"
            type="button"
            onClick={() => onApproveIssue(draft.id)}
            disabled={isApprovingIssue || isCreated}
          >
            {isApprovingIssue ? "Approving..." : isApprovedLocal ? "Create on GitHub" : isCreated ? "Created" : "Approve Issue"}
          </button>
        </div>
      </div>

      {hasWarnings ? (
        <div className="mt-4 rounded border border-amber-200 bg-amber-50 p-3">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-amber-900">Evidence Guard Warnings</h4>
          <ul className="mt-2 grid gap-1 text-sm text-amber-900">
            {draft.warnings.map((warning) => (
              <li key={warning}>- {warning}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <pre className="mt-4 max-h-[520px] overflow-auto whitespace-pre-wrap rounded border border-line bg-slate-950 p-4 text-xs leading-6 text-slate-100">
        {draft.body_markdown}
      </pre>
    </section>
  );
}
