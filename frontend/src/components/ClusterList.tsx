import { ArrowRight } from "lucide-react";

import { PriorityBadge } from "./PriorityBadge";

const emptyClusters = [
  {
    title: "Checkout hangs after session expiry",
    ticketCount: 0,
    priority: "P1 High",
    confidence: "Pending",
    status: "Phase 5",
  },
  {
    title: "Duplicate charge after retrying payment",
    ticketCount: 0,
    priority: "P0 Critical",
    confidence: "Pending",
    status: "Phase 5",
  },
];

export function ClusterList() {
  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-ink">Cluster Review</h2>
          <p className="text-sm text-slate-600">Detected complaint groups will appear here.</p>
        </div>
      </div>

      <div className="mt-4 overflow-hidden rounded border border-line">
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
            {emptyClusters.map((cluster) => (
              <tr key={cluster.title}>
                <td className="px-4 py-3 font-medium text-ink">{cluster.title}</td>
                <td className="px-4 py-3 text-slate-600">{cluster.ticketCount}</td>
                <td className="px-4 py-3">
                  <PriorityBadge label={cluster.priority} />
                </td>
                <td className="px-4 py-3 text-slate-600">{cluster.confidence}</td>
                <td className="px-4 py-3 text-slate-600">{cluster.status}</td>
                <td className="px-4 py-3">
                  <button
                    className="inline-flex h-8 w-8 items-center justify-center rounded border border-line text-slate-500"
                    type="button"
                    aria-label={`Review ${cluster.title}`}
                    disabled
                  >
                    <ArrowRight size={15} aria-hidden="true" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
