import { useEffect, useState } from "react";
import { Activity, AlertCircle, Boxes, ListChecks, Loader2, RefreshCw, WandSparkles } from "lucide-react";

import {
  approveIssue,
  Cluster,
  CodebaseStatusResponse,
  ClusterDetailResponse,
  draftIssueForCluster,
  getCodebaseStatus,
  getClusterDetail,
  getClusters,
  getHealth,
  getTickets,
  HealthResponse,
  processTickets,
  retrieveCodeForCluster,
  Ticket,
} from "../api/client";
import { ClusterList } from "../components/ClusterList";
import { ClusterDetail } from "../components/ClusterDetail";
import { TicketUpload } from "../components/TicketUpload";
import { TicketTable } from "../components/TicketTable";
import { CodebaseIndexPage } from "./CodebaseIndexPage";

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

export function Dashboard() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [ticketTotal, setTicketTotal] = useState(0);
  const [ticketError, setTicketError] = useState<string | null>(null);
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [clusterTotal, setClusterTotal] = useState(0);
  const [clusterError, setClusterError] = useState<string | null>(null);
  const [codebaseStatus, setCodebaseStatus] = useState<CodebaseStatusResponse | null>(null);
  const [selectedClusterId, setSelectedClusterId] = useState<number | null>(null);
  const [clusterDetail, setClusterDetail] = useState<ClusterDetailResponse | null>(null);
  const [isClusterDetailLoading, setIsClusterDetailLoading] = useState(false);
  const [isRetrievingCode, setIsRetrievingCode] = useState(false);
  const [isDraftingIssue, setIsDraftingIssue] = useState(false);
  const [isApprovingIssue, setIsApprovingIssue] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processMessage, setProcessMessage] = useState<string | null>(null);
  const [processError, setProcessError] = useState<string | null>(null);

  const refreshTickets = () => {
    getTickets()
      .then((response) => {
        setTickets(response.items);
        setTicketTotal(response.total);
        setTicketError(null);
      })
      .catch((error) => {
        setTicketError(error instanceof Error ? error.message : "Unable to load tickets.");
      });
  };

  const refreshClusters = () => {
    getClusters()
      .then((response) => {
        setClusters(response.items);
        setClusterTotal(response.total);
        setClusterError(null);
        if (!selectedClusterId && response.items.length) {
          setSelectedClusterId(response.items[0].id);
        }
      })
      .catch((error) => {
        setClusterError(error instanceof Error ? error.message : "Unable to load clusters.");
      });
  };

  const refreshCodebaseStatus = () => {
    getCodebaseStatus()
      .then((response) => {
        setCodebaseStatus(response);
        setClusterError(null);
      })
      .catch((error) => {
        setClusterError(error instanceof Error ? error.message : "Unable to load codebase status.");
      });
  };

  const refreshAll = () => {
    getHealth()
      .then(setHealth)
      .catch((error) => {
        setHealthError(error instanceof Error ? error.message : "Backend unavailable.");
      });
    refreshTickets();
    refreshClusters();
    refreshCodebaseStatus();
    if (selectedClusterId) loadClusterDetail(selectedClusterId);
  };

  const loadClusterDetail = (clusterId: number) => {
    setSelectedClusterId(clusterId);
    setIsClusterDetailLoading(true);
    getClusterDetail(clusterId)
      .then((response) => {
        setClusterDetail(response);
        setClusterError(null);
      })
      .catch((error) => {
        setClusterError(error instanceof Error ? error.message : "Unable to load cluster detail.");
      })
      .finally(() => setIsClusterDetailLoading(false));
  };

  useEffect(() => {
    refreshAll();
  }, []);

  useEffect(() => {
    if (selectedClusterId) {
      loadClusterDetail(selectedClusterId);
    } else {
      setClusterDetail(null);
    }
  }, [selectedClusterId]);

  const runExtraction = async () => {
    setIsProcessing(true);
    setProcessError(null);
    setProcessMessage(null);

    try {
      const result = await processTickets(20, false);
      setProcessMessage(
        `${result.message} Processed ${result.processed}, failed ${result.failed}.`,
      );
      refreshTickets();
      refreshClusters();
      refreshCodebaseStatus();
      if (selectedClusterId) loadClusterDetail(selectedClusterId);
    } catch (error) {
      setProcessError(error instanceof Error ? error.message : "Ticket extraction failed.");
    } finally {
      setIsProcessing(false);
    }
  };

  const runCodeRetrieval = async (clusterId: number) => {
    setIsRetrievingCode(true);
    setClusterError(null);
    try {
      await retrieveCodeForCluster(clusterId);
      loadClusterDetail(clusterId);
    } catch (error) {
      setClusterError(error instanceof Error ? error.message : "Unable to retrieve code evidence.");
    } finally {
      setIsRetrievingCode(false);
    }
  };

  const runIssueDraft = async (clusterId: number) => {
    setIsDraftingIssue(true);
    setClusterError(null);
    try {
      await draftIssueForCluster(clusterId);
      loadClusterDetail(clusterId);
      refreshClusters();
    } catch (error) {
      setClusterError(error instanceof Error ? error.message : "Unable to draft issue.");
    } finally {
      setIsDraftingIssue(false);
    }
  };

  const runIssueApproval = async (issueId: number) => {
    setIsApprovingIssue(true);
    setClusterError(null);
    setProcessMessage(null);
    try {
      const result = await approveIssue(issueId);
      setProcessMessage(result.message);
      if (selectedClusterId) loadClusterDetail(selectedClusterId);
      refreshClusters();
    } catch (error) {
      setClusterError(error instanceof Error ? error.message : "Unable to approve issue.");
    } finally {
      setIsApprovingIssue(false);
    }
  };

  const overviewCards = [
    { label: "Total Tickets", value: ticketTotal.toLocaleString(), icon: ListChecks },
    { label: "Clusters", value: clusterTotal.toLocaleString(), icon: Boxes },
    { label: "Needs Review", value: clusters.filter((cluster) => cluster.status === "needs_review").length.toString(), icon: AlertCircle },
    { label: "P0/P1", value: clusters.filter((cluster) => ["P0 Critical", "P1 High"].includes(cluster.priority_label)).length.toString(), icon: Activity },
  ];
  const extractedTickets = tickets.filter((ticket) => ticket.extraction_status === "completed").length;

  return (
    <main className="min-h-screen bg-panel">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-5 py-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-ink">BugSignal AI</h1>
            <p className="mt-1 text-sm text-slate-600">Evidence-grounded support ticket triage for engineering teams.</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <HealthPill health={health} />
            <button
              className="inline-flex items-center justify-center gap-2 rounded border border-line bg-white px-3 py-1 text-sm font-semibold text-slate-700 transition hover:border-signal hover:text-signal"
              type="button"
              onClick={refreshAll}
            >
              <RefreshCw size={15} aria-hidden="true" />
              Refresh
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl gap-6 px-5 py-6">
        {healthError ? (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {healthError}
          </div>
        ) : null}

        {ticketError ? (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {ticketError}
          </div>
        ) : null}

        {clusterError ? (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {clusterError}
          </div>
        ) : null}

        {processMessage ? (
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            {processMessage}
          </div>
        ) : null}

        {processError ? (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            {processError}
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

        <WorkflowStrip
          ticketTotal={ticketTotal}
          extractedTickets={extractedTickets}
          clusterTotal={clusterTotal}
          indexedChunks={codebaseStatus?.indexed_chunks ?? 0}
          evidenceCount={clusterDetail?.retrieved_code_snippets.length ?? 0}
          issueStatus={clusterDetail?.issue_draft?.status ?? null}
        />

        <div className="grid gap-6 lg:grid-cols-[minmax(320px,420px)_1fr]">
          <TicketUpload onUploaded={refreshTickets} />
          <section className="grid gap-6">
            <div className="rounded-lg border border-line bg-white p-5 shadow-sm">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="text-base font-semibold text-ink">Structured Extraction</h2>
                  <p className="text-sm text-slate-600">Run Ollama JSON extraction for pending tickets.</p>
                </div>
                <button
                  className="inline-flex items-center justify-center gap-2 rounded bg-signal px-4 py-2 text-sm font-semibold text-white transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:bg-slate-400"
                  type="button"
                  onClick={runExtraction}
                  disabled={isProcessing || ticketTotal === 0}
                >
                  {isProcessing ? (
                    <Loader2 className="animate-spin" size={16} aria-hidden="true" />
                  ) : (
                    <WandSparkles size={16} aria-hidden="true" />
                  )}
                  Process Tickets
                </button>
              </div>
            </div>
            <ClusterList
              clusters={clusters}
              selectedClusterId={selectedClusterId}
              onSelectCluster={setSelectedClusterId}
            />
          </section>
        </div>

        <ClusterDetail
          detail={clusterDetail}
          isLoading={isClusterDetailLoading}
          isRetrievingCode={isRetrievingCode}
          isDraftingIssue={isDraftingIssue}
          isApprovingIssue={isApprovingIssue}
          onRetrieveCode={runCodeRetrieval}
          onDraftIssue={runIssueDraft}
          onApproveIssue={runIssueApproval}
        />

        <CodebaseIndexPage onStatusChange={setCodebaseStatus} />

        <TicketTable tickets={tickets} />
      </div>
    </main>
  );
}

function WorkflowStrip({
  ticketTotal,
  extractedTickets,
  clusterTotal,
  indexedChunks,
  evidenceCount,
  issueStatus,
}: {
  ticketTotal: number;
  extractedTickets: number;
  clusterTotal: number;
  indexedChunks: number;
  evidenceCount: number;
  issueStatus: string | null;
}) {
  const steps = [
    { label: "Tickets", value: ticketTotal ? ticketTotal.toLocaleString() : "0", active: ticketTotal > 0 },
    { label: "Extracted", value: extractedTickets ? extractedTickets.toLocaleString() : "0", active: extractedTickets > 0 },
    { label: "Clusters", value: clusterTotal ? clusterTotal.toLocaleString() : "0", active: clusterTotal > 0 },
    { label: "Code Index", value: indexedChunks ? `${indexedChunks.toLocaleString()} chunks` : "0 chunks", active: indexedChunks > 0 },
    { label: "Evidence", value: evidenceCount ? `${evidenceCount} snippets` : "0 snippets", active: evidenceCount > 0 },
    { label: "Draft", value: issueStatus ? formatStatus(issueStatus) : "None", active: Boolean(issueStatus) },
  ];

  return (
    <section className="rounded-lg border border-line bg-white p-4 shadow-sm">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
        {steps.map((step) => (
          <div key={step.label} className="flex items-center gap-3">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                step.active ? "bg-signal" : "bg-slate-300"
              }`}
              aria-hidden="true"
            />
            <div className="min-w-0">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{step.label}</div>
              <div className="truncate text-sm font-semibold text-ink">{step.value}</div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function formatStatus(value: string) {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
