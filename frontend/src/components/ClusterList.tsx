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
    <section className="min-w-0 rounded-lg border border-line bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-ink">Cluster Review</h2>
          <p className="text-sm text-slate-600">Detected complaint groups will appear here.</p>
        </div>
      </div>

      <div className="mt-4 grid gap-2">
        {clusters.length ? (
          clusters.map((cluster) => {
            const selected = selectedClusterId === cluster.id;
            return (
              <button
                key={cluster.id}
                type="button"
                aria-pressed={selected}
                onClick={() => onSelectCluster(cluster.id)}
                className={`min-w-0 rounded border p-3 text-left transition ${
                  selected
                    ? "border-signal bg-teal-50 shadow-sm"
                    : "border-line bg-white hover:border-slate-300 hover:bg-panel"
                }`}
              >
                <div className="flex min-w-0 items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="break-words text-sm font-semibold text-ink">{cluster.title}</div>
                    {cluster.suspected_feature_area ? (
                      <div className="mt-1 break-words text-xs text-slate-500">{cluster.suspected_feature_area}</div>
                    ) : null}
                  </div>
                  <ArrowRight className={`mt-0.5 shrink-0 ${selected ? "text-signal" : "text-slate-400"}`} size={16} aria-hidden="true" />
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <PriorityBadge label={cluster.priority_label} />
                  <StatusBadge status={cluster.status} />
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-600">
                  <span><strong className="text-ink">{cluster.ticket_count}</strong> tickets</span>
                  <span><strong className="text-ink">{Math.round(cluster.confidence_score * 100)}%</strong> confidence</span>
                </div>
              </button>
            );
          })
        ) : (
          <div className="rounded border border-dashed border-line px-4 py-8 text-center text-sm text-slate-500">
            Process tickets to generate HDBSCAN clusters.
          </div>
        )}
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
