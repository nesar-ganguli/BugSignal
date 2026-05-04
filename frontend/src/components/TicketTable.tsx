import { Ticket } from "../api/client";

type TicketTableProps = {
  tickets: Ticket[];
};

function formatDate(value: string | null) {
  if (!value) return "Unknown";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export function TicketTable({ tickets }: TicketTableProps) {
  const statusStyles: Record<string, string> = {
    completed: "border-emerald-200 bg-emerald-50 text-emerald-700",
    failed: "border-rose-200 bg-rose-50 text-rose-700",
    stale: "border-amber-200 bg-amber-50 text-amber-800",
    pending: "border-slate-200 bg-slate-50 text-slate-600",
  };

  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-ink">Ticket Review</h2>
          <p className="text-sm text-slate-600">All imported tickets available for extraction and clustering review.</p>
        </div>
        <span className="text-sm font-medium text-slate-600">
          {tickets.length.toLocaleString()} ticket{tickets.length === 1 ? "" : "s"}
        </span>
      </div>

      <div className="mt-4 max-h-[560px] overflow-auto rounded border border-line">
        <table className="min-w-full divide-y divide-line text-left text-sm">
          <thead className="sticky top-0 z-10 bg-panel text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3 font-semibold">Ticket</th>
              <th className="min-w-[320px] px-4 py-3 font-semibold">Issue</th>
              <th className="px-4 py-3 font-semibold">Plan</th>
              <th className="px-4 py-3 font-semibold">Severity</th>
              <th className="px-4 py-3 font-semibold">Extraction</th>
              <th className="px-4 py-3 font-semibold">Cluster</th>
              <th className="px-4 py-3 font-semibold">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line bg-white">
            {tickets.length ? (
              tickets.map((ticket) => (
                <tr key={ticket.id}>
                  <td className="whitespace-nowrap px-4 py-3 font-medium text-ink">{ticket.external_ticket_id}</td>
                  <td className="px-4 py-3">
                    <div className="font-medium text-ink">{ticket.title}</div>
                    <div className="mt-1 line-clamp-2 max-w-2xl text-xs leading-5 text-slate-500">{ticket.body}</div>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-600">{ticket.customer_plan ?? "Unknown"}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-600">{ticket.severity ?? "Unknown"}</td>
                  <td className="whitespace-nowrap px-4 py-3">
                    <span
                      className={`rounded border px-2 py-1 text-xs font-semibold ${
                        statusStyles[ticket.extraction_status] ?? statusStyles.pending
                      }`}
                      title={ticket.extraction_error ?? undefined}
                    >
                      {formatExtractionStatus(ticket.extraction_status)}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                    {ticket.cluster_id ? `#${ticket.cluster_id}` : "Unassigned"}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-600">{formatDate(ticket.created_at)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td className="px-4 py-6 text-center text-slate-500" colSpan={7}>
                  Upload the sample CSV to populate tickets.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function formatExtractionStatus(status: string) {
  if (status === "completed") return "Extracted";
  if (status === "failed") return "Failed";
  if (status === "stale") return "Stale";
  return "Pending";
}
