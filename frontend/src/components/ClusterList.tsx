import { ArrowRight } from "lucide-react";

import { Cluster } from "../api/client";
import { PriorityBadge } from "./PriorityBadge";

type ClusterListProps = {
  clusters: Cluster[];
  selectedClusterId: number | null;
  onSelectCluster: (clusterId: number) => void;
};

export function ClusterList({ clusters, selectedClusterId, onSelectCluster }: ClusterListProps) {
  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-ink">Cluster Review</h2>
          <p className="text-sm text-slate-600">Detected complaint groups will appear here.</p>
        </div>
      </div>

      <div className="mt-4 overflow-x-auto rounded border border-line">
        <table className="min-w-full divide-y divide-line text-left text-sm">
          <thead className="bg-panel text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3 font-semibold">Cluster</th>
              <th className="px-4 py-3 font-semibold">Tickets</th>
              <th className="px-4 py-3 font-semibold">Priority</th>
              <th className="px-4 py-3 font-semibold">Confidence</th>
              <th className="px-4 py-3 font-semibold">Status</th>
              <th className="px-4 py-3 font-semibold">Review</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line bg-white">
            {clusters.length ? (
              clusters.map((cluster) => (
              <tr key={cluster.id} className={selectedClusterId === cluster.id ? "bg-teal-50/50" : undefined}>
                <td className="min-w-[220px] px-4 py-3">
                  <div className="font-medium text-ink">{cluster.title}</div>
                  {cluster.suspected_feature_area ? (
                    <div className="mt-1 text-xs text-slate-500">{cluster.suspected_feature_area}</div>
                  ) : null}
                </td>
                <td className="px-4 py-3 text-slate-600">{cluster.ticket_count}</td>
                <td className="px-4 py-3">
                  <PriorityBadge label={cluster.priority_label} />
                </td>
                <td className="px-4 py-3 text-slate-600">{Math.round(cluster.confidence_score * 100)}%</td>
                <td className="px-4 py-3">
                  <StatusBadge status={cluster.status} />
                </td>
                <td className="px-4 py-3">
                  <button
                    className="inline-flex h-8 w-8 items-center justify-center rounded border border-line text-slate-500 transition hover:border-signal hover:text-signal"
                    type="button"
                    aria-label={`Review ${cluster.title}`}
                    onClick={() => onSelectCluster(cluster.id)}
                  >
                    <ArrowRight size={15} aria-hidden="true" />
                  </button>
                </td>
              </tr>
              ))
            ) : (
              <tr>
                <td className="px-4 py-6 text-center text-slate-500" colSpan={6}>
                  Process tickets to generate HDBSCAN clusters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function StatusBadge({ status }: { status: string }) {
  const normalized = status.split("_").join(" ");
  const className =
    status === "issue_created"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : status === "ready_for_issue" || status === "approved"
        ? "border-teal-200 bg-teal-50 text-teal-700"
        : "border-slate-200 bg-slate-50 text-slate-600";

  return (
    <span className={`whitespace-nowrap rounded border px-2 py-1 text-xs font-semibold capitalize ${className}`}>
      {normalized}
    </span>
  );
}
