import { ClusterDetailResponse } from "../api/client";
import { EvidencePanel } from "./EvidencePanel";
import { IssueDraftPanel } from "./IssueDraftPanel";
import { PriorityBadge } from "./PriorityBadge";

type ClusterDetailProps = {
  detail: ClusterDetailResponse | null;
  isLoading: boolean;
  isRetrievingCode: boolean;
  isDraftingIssue: boolean;
  isApprovingIssue: boolean;
  onRetrieveCode: (clusterId: number) => void;
  onDraftIssue: (clusterId: number) => void;
  onApproveIssue: (issueId: number) => void;
};

export function ClusterDetail({
  detail,
  isLoading,
  isRetrievingCode,
  isDraftingIssue,
  isApprovingIssue,
  onRetrieveCode,
  onDraftIssue,
  onApproveIssue,
}: ClusterDetailProps) {
  if (isLoading) {
    return (
      <section className="rounded-lg border border-line bg-white p-5 shadow-sm">
        <p className="text-sm text-slate-600">Loading cluster detail...</p>
      </section>
    );
  }

  if (!detail) {
    return (
      <section className="rounded-lg border border-line bg-white p-5 shadow-sm">
        <h2 className="text-base font-semibold text-ink">Cluster Detail</h2>
        <p className="mt-1 text-sm text-slate-600">Select a cluster to review priority, cohesion, and tickets.</p>
      </section>
    );
  }

  const { cluster, tickets, priority_breakdown, retrieved_code_snippets, issue_draft } = detail;
  const hasRetrievedEvidence = retrieved_code_snippets.length > 0;

  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-ink">{cluster.title}</h2>
          <p className="mt-1 text-sm text-slate-600">{cluster.summary ?? "No summary available."}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <PriorityBadge label={cluster.priority_label} />
          <button
            className="rounded border border-line px-3 py-2 text-sm font-semibold text-ink transition hover:border-signal hover:text-signal disabled:cursor-not-allowed disabled:text-slate-400"
            type="button"
            onClick={() => onRetrieveCode(cluster.id)}
            disabled={isRetrievingCode}
          >
            {isRetrievingCode ? "Retrieving..." : "Retrieve Code"}
          </button>
          <button
            className="rounded bg-signal px-3 py-2 text-sm font-semibold text-white transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:bg-slate-400"
            type="button"
            onClick={() => onDraftIssue(cluster.id)}
            disabled={isDraftingIssue || !hasRetrievedEvidence}
          >
            {isDraftingIssue ? "Drafting..." : "Draft Issue"}
          </button>
        </div>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-4">
        <Metric label="Tickets" value={String(cluster.ticket_count)} />
        <Metric label="Priority" value={String(cluster.priority_score)} />
        <Metric label="Cohesion" value={`${Math.round(cluster.cohesion_score * 100)}%`} />
        <Metric label="Confidence" value={`${Math.round(cluster.confidence_score * 100)}%`} />
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(220px,320px)_1fr]">
        <div>
          <h3 className="text-sm font-semibold text-ink">Priority Breakdown</h3>
          <div className="mt-3 grid gap-2">
            {priority_breakdown.length ? (
              priority_breakdown.map((item) => (
                <div key={item.label} className="flex items-center justify-between rounded border border-line bg-panel px-3 py-2 text-sm">
                  <span className="text-slate-700">{item.label}</span>
                  <span className="font-semibold text-ink">+{item.points}</span>
                </div>
              ))
            ) : (
              <p className="text-sm text-slate-500">No priority signals were found.</p>
            )}
          </div>
        </div>

        <div>
          <h3 className="text-sm font-semibold text-ink">Tickets In Cluster</h3>
          <div className="mt-3 overflow-x-auto rounded border border-line">
            <table className="min-w-full divide-y divide-line text-left text-sm">
              <thead className="bg-panel text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-3 py-2 font-semibold">Ticket</th>
                  <th className="px-3 py-2 font-semibold">Title</th>
                  <th className="px-3 py-2 font-semibold">Sentiment</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {tickets.map((ticket) => (
                  <tr key={ticket.id}>
                    <td className="whitespace-nowrap px-3 py-2 font-medium text-ink">{ticket.external_ticket_id}</td>
                    <td className="px-3 py-2 text-slate-700">{ticket.title}</td>
                    <td className="whitespace-nowrap px-3 py-2 text-slate-600">{ticket.sentiment ?? "Unknown"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="mt-5">
        <EvidencePanel snippets={retrieved_code_snippets} />
      </div>

      <div className="mt-5">
        <IssueDraftPanel
          draft={issue_draft}
          isApprovingIssue={isApprovingIssue}
          onApproveIssue={onApproveIssue}
        />
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-line bg-panel p-3">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-lg font-bold text-ink">{value}</div>
    </div>
  );
}
