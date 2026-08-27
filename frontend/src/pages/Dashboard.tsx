import { useEffect, useState } from "react";
import { Activity, AlertCircle, Boxes, Building2, ListChecks, Loader2, LogOut, Plus, RefreshCw, WandSparkles } from "lucide-react";

import {
  approveIssue,
  cancelWorkflow,
  createProject,
  Cluster,
  CodebaseStatusResponse,
  ClusterDetailResponse,
  draftIssueForCluster,
  getCodebaseStatus,
  getClusterDetail,
  getClusters,
  getHealth,
  getCurrentUser,
  getProjects,
  getWorkflow,
  getWorkflows,
  getTickets,
  HealthResponse,
  processTickets,
  retrieveCodeForCluster,
  Ticket,
  CurrentUserResponse,
  Project,
  WorkflowRun,
} from "../api/client";
import { oidcEnabled, signOut } from "../auth";
import { ClusterList } from "../components/ClusterList";
import { ClusterDetail } from "../components/ClusterDetail";
import { TicketUpload } from "../components/TicketUpload";
import { TicketTable } from "../components/TicketTable";
import { CodebaseIndexPage } from "./CodebaseIndexPage";

type DashboardTab = "overview" | "tickets" | "clusters" | "codebase" | "evidence";

const dashboardTabs: { id: DashboardTab; label: string; step?: number }[] = [
  { id: "overview", label: "Overview" },
  { id: "tickets", label: "Tickets", step: 1 },
  { id: "clusters", label: "Clusters", step: 2 },
  { id: "codebase", label: "Codebase", step: 3 },
  { id: "evidence", label: "Evidence & Issues", step: 4 },
];

function initialDashboardTab(): DashboardTab {
  const value = window.location.hash.replace("#", "") as DashboardTab;
  return dashboardTabs.some((tab) => tab.id === value) ? value : "overview";
}

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
  const [activeTab, setActiveTab] = useState<DashboardTab>(initialDashboardTab);
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
  const [activeWorkflow, setActiveWorkflow] = useState<WorkflowRun | null>(null);
  const [isCancellingWorkflow, setIsCancellingWorkflow] = useState(false);
  const [processMessage, setProcessMessage] = useState<string | null>(null);
  const [processError, setProcessError] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<CurrentUserResponse | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [showProjectForm, setShowProjectForm] = useState(false);
  const [projectName, setProjectName] = useState("");
  const [projectSlug, setProjectSlug] = useState("");
  const [isCreatingProject, setIsCreatingProject] = useState(false);

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

  const handleTicketsUploaded = (result: { workflow_id: string | null }) => {
    refreshTickets();
    if (result.workflow_id) {
      getWorkflow(result.workflow_id).then((workflow) => {
        setActiveWorkflow(workflow);
        setIsProcessing(["queued", "running"].includes(workflow.status));
      }).catch(() => undefined);
    }
  };

  const handleCodebaseStatusChange = (status: CodebaseStatusResponse) => {
    setCodebaseStatus(status);
    getWorkflows(1).then((response) => {
      if (response.items[0]) setActiveWorkflow(response.items[0]);
    }).catch(() => undefined);
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
    Promise.all([getCurrentUser(), getProjects()])
      .then(([user, projectResponse]) => {
        setCurrentUser(user);
        setProjects(projectResponse.items);
      })
      .catch((error) => {
        setHealthError(error instanceof Error ? error.message : "Unable to load tenant context.");
      });
    getWorkflows(1)
      .then((response) => {
        const latest = response.items[0];
        if (latest) {
          setActiveWorkflow(latest);
          setIsProcessing(["queued", "running"].includes(latest.status));
        }
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!activeWorkflow || !["queued", "running"].includes(activeWorkflow.status)) return;

    const timer = window.setInterval(() => {
      getWorkflow(activeWorkflow.id)
        .then((workflow) => {
          setActiveWorkflow(workflow);
          if (workflow.status === "completed") {
            setIsProcessing(false);
            setProcessMessage(workflow.result?.message ?? "Ticket workflow completed.");
            refreshTickets();
            refreshClusters();
            refreshCodebaseStatus();
          } else if (workflow.status === "waiting_for_codebase") {
            setIsProcessing(false);
            setProcessMessage(workflow.result?.message ?? "Ticket processing is complete. Add a repository to continue.");
            refreshTickets();
            refreshClusters();
            refreshCodebaseStatus();
          } else if (workflow.status === "failed" || workflow.status === "cancelled") {
            setIsProcessing(false);
            setProcessError(workflow.error_message ?? `Workflow ${workflow.status}.`);
          }
        })
        .catch((error) => {
          setProcessError(error instanceof Error ? error.message : "Unable to refresh workflow.");
        });
    }, 2000);

    return () => window.clearInterval(timer);
  }, [activeWorkflow?.id, activeWorkflow?.status]);

  useEffect(() => {
    if (selectedClusterId) {
      loadClusterDetail(selectedClusterId);
    } else {
      setClusterDetail(null);
    }
  }, [selectedClusterId]);

  const switchProject = (projectId: number) => {
    window.localStorage.setItem("bugsignal_project_id", String(projectId));
    window.location.reload();
  };

  const selectTab = (tab: DashboardTab) => {
    setActiveTab(tab);
    window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}#${tab}`);
  };

  const runProjectCreation = async () => {
    setIsCreatingProject(true);
    setProcessError(null);
    try {
      const project = await createProject(projectName.trim(), projectSlug.trim());
      window.localStorage.setItem("bugsignal_project_id", String(project.id));
      window.location.reload();
    } catch (error) {
      setProcessError(error instanceof Error ? error.message : "Unable to create project.");
      setIsCreatingProject(false);
    }
  };

  const runExtraction = async () => {
    setIsProcessing(true);
    setProcessError(null);
    setProcessMessage(null);

    try {
      const result = await processTickets(20, false);
      setActiveWorkflow(result);
      setProcessMessage("Ticket processing workflow queued.");
    } catch (error) {
      setProcessError(error instanceof Error ? error.message : "Unable to queue ticket processing.");
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

  const runWorkflowCancellation = async () => {
    if (!activeWorkflow) return;
    setIsCancellingWorkflow(true);
    setProcessError(null);
    try {
      const workflow = await cancelWorkflow(activeWorkflow.id);
      setActiveWorkflow(workflow);
      setIsProcessing(false);
      setProcessMessage("Ticket workflow cancelled.");
    } catch (error) {
      setProcessError(error instanceof Error ? error.message : "Unable to cancel workflow.");
    } finally {
      setIsCancellingWorkflow(false);
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
  const canEdit = currentUser ? ["owner", "admin", "member"].includes(currentUser.project_role) : false;

  return (
    <main className="min-h-screen bg-panel">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-5 py-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-ink">BugSignal AI</h1>
            <p className="mt-1 text-sm text-slate-600">Evidence-grounded support ticket triage for engineering teams.</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {currentUser ? (
              <div className="flex flex-wrap items-center gap-2 rounded border border-line bg-slate-50 p-1.5">
                <span className="inline-flex items-center gap-1.5 px-2 text-xs font-semibold text-slate-600">
                  <Building2 size={14} aria-hidden="true" />
                  {currentUser.organization_external_id}
                </span>
                <select
                  className="rounded border border-line bg-white px-2 py-1 text-sm font-semibold text-ink"
                  aria-label="Active project"
                  value={currentUser.project_id}
                  onChange={(event) => switchProject(Number(event.target.value))}
                >
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>{project.name}</option>
                  ))}
                </select>
                {['owner', 'admin'].includes(currentUser.project_role) ? (
                  <button type="button" className="rounded p-1 text-slate-600 hover:bg-white hover:text-signal" title="Create project" onClick={() => setShowProjectForm((value) => !value)}>
                    <Plus size={16} aria-hidden="true" />
                  </button>
                ) : null}
                <span className="rounded bg-white px-2 py-1 text-xs font-medium text-slate-600">
                  {currentUser.display_name ?? currentUser.email ?? currentUser.subject} · {currentUser.project_role}
                </span>
                {oidcEnabled ? (
                  <button type="button" className="rounded p-1 text-slate-600 hover:text-red-700" title="Sign out" onClick={() => void signOut()}>
                    <LogOut size={16} aria-hidden="true" />
                  </button>
                ) : null}
              </div>
            ) : null}
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
        {showProjectForm ? (
          <section className="rounded-lg border border-line bg-white p-4 shadow-sm">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
              <label className="grid flex-1 gap-1 text-xs font-semibold text-slate-600">Project name
                <input className="rounded border border-line px-3 py-2 text-sm font-normal text-ink" value={projectName} onChange={(event) => { setProjectName(event.target.value); if (!projectSlug) setProjectSlug(event.target.value.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')); }} />
              </label>
              <label className="grid flex-1 gap-1 text-xs font-semibold text-slate-600">Slug
                <input className="rounded border border-line px-3 py-2 text-sm font-normal text-ink" value={projectSlug} onChange={(event) => setProjectSlug(event.target.value.toLowerCase())} />
              </label>
              <button type="button" className="rounded bg-signal px-4 py-2 text-sm font-semibold text-white disabled:bg-slate-400" disabled={isCreatingProject || !projectName.trim() || !projectSlug.trim()} onClick={runProjectCreation}>
                {isCreatingProject ? "Creating…" : "Create project"}
              </button>
            </div>
          </section>
        ) : null}
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

        {currentUser && !canEdit ? (
          <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
            You have viewer access to this project. Changes and workflow actions are disabled.
          </div>
        ) : null}

        <nav className="overflow-x-auto rounded-lg border border-line bg-white p-2 shadow-sm" aria-label="BugSignal workflow">
          <div className="flex min-w-max gap-1" role="tablist">
            {dashboardTabs.map((tab) => (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={activeTab === tab.id}
                onClick={() => selectTab(tab.id)}
                className={`inline-flex items-center gap-2 rounded px-4 py-2 text-sm font-semibold transition ${
                  activeTab === tab.id ? "bg-ink text-white" : "text-slate-600 hover:bg-panel hover:text-ink"
                }`}
              >
                {tab.step ? <span className={`grid h-5 w-5 place-items-center rounded-full text-xs ${activeTab === tab.id ? "bg-white/20" : "bg-slate-200"}`}>{tab.step}</span> : null}
                {tab.label}
              </button>
            ))}
          </div>
        </nav>

        {activeWorkflow?.status === "waiting_for_codebase" ? (
          <div className="flex flex-col gap-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900 sm:flex-row sm:items-center sm:justify-between">
            <span>Ticket extraction and clustering are complete. Add this project's repository to continue evidence retrieval and issue drafting automatically.</span>
            <button type="button" className="shrink-0 rounded bg-ink px-3 py-2 font-semibold text-white" onClick={() => selectTab("codebase")}>Add repository</button>
          </div>
        ) : null}

        {activeTab === "overview" ? (
          <div className="grid gap-6" role="tabpanel">
            <TabHeading title="Project Overview" description="Monitor the current project and follow progress through the triage workflow." />
            {activeWorkflow ? (
              <WorkflowRunPanel workflow={activeWorkflow} isCancelling={isCancellingWorkflow} readOnly={!canEdit} onCancel={runWorkflowCancellation} />
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
            <WorkflowStrip ticketTotal={ticketTotal} extractedTickets={extractedTickets} clusterTotal={clusterTotal} indexedChunks={codebaseStatus?.indexed_chunks ?? 0} evidenceCount={clusterDetail?.retrieved_code_snippets.length ?? 0} issueStatus={clusterDetail?.issue_draft?.status ?? null} />
          </div>
        ) : null}

        {activeTab === "tickets" ? (
          <div className="grid gap-6" role="tabpanel">
            <TabHeading title="1. Import and Process Tickets" description="Upload support data, then run structured extraction and clustering." />
            {activeWorkflow ? <WorkflowRunPanel workflow={activeWorkflow} isCancelling={isCancellingWorkflow} readOnly={!canEdit} onCancel={runWorkflowCancellation} /> : null}
            <div className="grid gap-6 lg:grid-cols-[minmax(320px,420px)_1fr]">
              <TicketUpload disabled={!canEdit} onUploaded={handleTicketsUploaded} />
              <div className="rounded-lg border border-line bg-white p-5 shadow-sm">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h2 className="text-base font-semibold text-ink">Structured Extraction</h2>
                    <p className="text-sm text-slate-600">Run Ollama extraction and create clusters from pending tickets.</p>
                  </div>
                  <button className="inline-flex items-center justify-center gap-2 rounded bg-signal px-4 py-2 text-sm font-semibold text-white transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:bg-slate-400" type="button" onClick={runExtraction} disabled={!canEdit || isProcessing || ticketTotal === 0}>
                    {isProcessing ? <Loader2 className="animate-spin" size={16} aria-hidden="true" /> : <WandSparkles size={16} aria-hidden="true" />}
                    Process Tickets
                  </button>
                </div>
              </div>
            </div>
            <TicketTable tickets={tickets} />
          </div>
        ) : null}

        {activeTab === "clusters" ? (
          <div className="grid gap-6" role="tabpanel">
            <TabHeading title="2. Review Clusters" description="Inspect grouped complaints, priority signals, confidence, and member tickets." />
            <div className="grid min-w-0 gap-6 xl:grid-cols-[minmax(300px,380px)_minmax(0,1fr)]">
              <ClusterList clusters={clusters} selectedClusterId={selectedClusterId} onSelectCluster={setSelectedClusterId} />
              <ClusterDetail mode="cluster" detail={clusterDetail} isLoading={isClusterDetailLoading} isRetrievingCode={isRetrievingCode} isDraftingIssue={isDraftingIssue} isApprovingIssue={isApprovingIssue} readOnly={!canEdit} onRetrieveCode={runCodeRetrieval} onDraftIssue={runIssueDraft} onApproveIssue={runIssueApproval} />
            </div>
          </div>
        ) : null}

        {activeTab === "codebase" ? (
          <div className="grid gap-6" role="tabpanel">
            <TabHeading title="3. Index the Codebase" description="Build the project-specific code index used to retrieve evidence for clusters." />
            <CodebaseIndexPage readOnly={!canEdit} onStatusChange={handleCodebaseStatusChange} />
          </div>
        ) : null}

        {activeTab === "evidence" ? (
          <div className="grid gap-6" role="tabpanel">
            <TabHeading title="4. Retrieve Evidence and Draft Issues" description="Select a cluster, retrieve relevant code, draft an evidence-grounded issue, and approve it." />
            <div className="grid min-w-0 gap-6 xl:grid-cols-[minmax(300px,380px)_minmax(0,1fr)]">
              <ClusterList clusters={clusters} selectedClusterId={selectedClusterId} onSelectCluster={setSelectedClusterId} />
              <ClusterDetail mode="evidence" detail={clusterDetail} isLoading={isClusterDetailLoading} isRetrievingCode={isRetrievingCode} isDraftingIssue={isDraftingIssue} isApprovingIssue={isApprovingIssue} readOnly={!canEdit} onRetrieveCode={runCodeRetrieval} onDraftIssue={runIssueDraft} onApproveIssue={runIssueApproval} />
            </div>
          </div>
        ) : null}
      </div>
    </main>
  );
}

function TabHeading({ title, description }: { title: string; description: string }) {
  return (
    <div>
      <h2 className="text-xl font-bold text-ink">{title}</h2>
      <p className="mt-1 text-sm text-slate-600">{description}</p>
    </div>
  );
}

function WorkflowRunPanel({
  workflow,
  isCancelling,
  readOnly,
  onCancel,
}: {
  workflow: WorkflowRun;
  isCancelling: boolean;
  readOnly: boolean;
  onCancel: () => void;
}) {
  const canCancel = !readOnly && ["queued", "running"].includes(workflow.status);
  return (
    <section className="rounded-lg border border-line bg-white p-4 shadow-sm" aria-live="polite">
      <div className="flex items-center justify-between gap-4">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            {workflow.workflow_type === "triage_pipeline" ? "Automated triage workflow" : "Ticket workflow"}
          </div>
          <div className="mt-1 text-sm font-semibold text-ink">
            {formatStatus(workflow.current_step)} · attempt {workflow.attempt_count || 1}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold text-signal">{workflow.progress_percent}%</span>
          {canCancel ? (
            <button
              type="button"
              className="rounded border border-line px-2 py-1 text-xs font-semibold text-slate-600 hover:border-red-300 hover:text-red-700 disabled:opacity-50"
              disabled={isCancelling}
              onClick={onCancel}
            >
              {isCancelling ? "Cancelling…" : "Cancel"}
            </button>
          ) : null}
        </div>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-200">
        <div
          className={`h-full rounded-full transition-all ${workflow.status === "failed" ? "bg-red-500" : "bg-signal"}`}
          style={{ width: `${workflow.progress_percent}%` }}
        />
      </div>
      {workflow.error_message ? <p className="mt-2 text-xs text-red-700">{workflow.error_message}</p> : null}
    </section>
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
