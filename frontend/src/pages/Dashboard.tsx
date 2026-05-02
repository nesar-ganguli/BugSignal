import { useEffect, useState } from "react";
import { Activity, AlertCircle, Boxes, ListChecks } from "lucide-react";

import { getHealth, HealthResponse } from "../api/client";
import { ClusterList } from "../components/ClusterList";
import { TicketUpload } from "../components/TicketUpload";

function HealthPill({ health }: { health: HealthResponse | null }) {
  if (!health) {
    return <span className="rounded border border-line bg-white px-3 py-1 text-sm text-slate-600">Backend checking</span>;
  }

  const reachable = health.ollama.reachable;
  return (
    <span
      className={`rounded border px-3 py-1 text-sm font-medium ${
        reachable
          ? "border-emerald-200 bg-emerald-50 text-emerald-700"
          : "border-amber-200 bg-amber-50 text-amber-800"
      }`}
    >
      Ollama {reachable ? "reachable" : "unavailable"}
    </span>
  );
}

const overviewCards = [
  { label: "Total Tickets", value: "0", icon: ListChecks },
  { label: "Clusters", value: "0", icon: Boxes },
  { label: "Needs Review", value: "0", icon: AlertCircle },
  { label: "P0/P1", value: "0", icon: Activity },
];

export function Dashboard() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch((error) => {
        setHealthError(error instanceof Error ? error.message : "Backend unavailable.");
      });
  }, []);

  return (
    <main className="min-h-screen bg-panel">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-5 py-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-ink">BugSignal AI</h1>
            <p className="mt-1 text-sm text-slate-600">Evidence-grounded support ticket triage for engineering teams.</p>
          </div>
          <HealthPill health={health} />
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl gap-6 px-5 py-6">
        {healthError ? (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {healthError}
          </div>
        ) : null}

        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {overviewCards.map((card) => {
            const Icon = card.icon;
            return (
              <div key={card.label} className="rounded-lg border border-line bg-white p-4 shadow-sm">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-medium text-slate-600">{card.label}</span>
                  <Icon size={18} className="text-signal" aria-hidden="true" />
                </div>
                <div className="mt-3 text-2xl font-bold text-ink">{card.value}</div>
              </div>
            );
          })}
        </section>

        <div className="grid gap-6 lg:grid-cols-[minmax(320px,420px)_1fr]">
          <TicketUpload />
          <ClusterList />
        </div>
      </div>
    </main>
  );
}
