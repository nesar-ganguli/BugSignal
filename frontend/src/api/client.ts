const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export type HealthResponse = {
  app: string;
  status: string;
  ollama: {
    reachable: boolean;
    model: string;
    model_available?: boolean;
    available_models?: string[];
    error?: string;
  };
};

export type UploadTicketsResponse = {
  filename: string;
  bytes_received: number;
  inserted: number;
  updated: number;
  skipped: number;
  total_tickets: number;
  status: string;
  message: string;
  errors: string[];
};

export type Ticket = {
  id: number;
  external_ticket_id: string;
  title: string;
  body: string;
  created_at: string | null;
  source: string | null;
  customer_plan: string | null;
  severity: string | null;
  extracted_intent: string | null;
  extracted_user_action: string | null;
  extracted_expected_behavior: string | null;
  extracted_actual_behavior: string | null;
  extracted_feature_area: string | null;
  extracted_error_terms: string | null;
  sentiment: string | null;
  contains_payment_or_revenue_issue: boolean;
  contains_data_loss_issue: boolean;
  contains_auth_issue: boolean;
  contains_performance_issue: boolean;
  extraction_status: string;
  extracted_at: string | null;
  extraction_error: string | null;
  cluster_id: number | null;
};

export type TicketListResponse = {
  items: Ticket[];
  total: number;
};

export type ProcessTicketsResponse = {
  processed: number;
  failed: number;
  total_tickets: number;
  clusters_created: number;
  clustered_tickets: number;
  outlier_tickets: number;
  message: string;
  errors: string[];
};

export type Cluster = {
  id: number;
  title: string;
  summary: string | null;
  ticket_count: number;
  priority_score: number;
  priority_label: string;
  priority_breakdown: string | null;
  confidence_score: number;
  cohesion_score: number;
  llm_coherence_label: string | null;
  suspected_feature_area: string | null;
  status: string;
};

export type ClusterListResponse = {
  items: Cluster[];
  total: number;
};

export type PriorityBreakdownItem = {
  label: string;
  points: number;
};

export type ClusterDetailResponse = {
  cluster: Cluster;
  tickets: Ticket[];
  priority_breakdown: PriorityBreakdownItem[];
  retrieved_code_snippets: CodeSnippet[];
  issue_draft: IssueDraft | null;
};

export type CodeSnippet = {
  evidence_id: number | null;
  code_chunk_id: number | null;
  file_path: string;
  start_line: number;
  end_line: number;
  snippet: string;
  relevance_score: number;
  evidence_type: string | null;
  reason: string;
};

export type CodeRetrievalResponse = {
  cluster_id: number;
  query: string;
  snippets: CodeSnippet[];
  message: string;
};

export type CodebaseStatusResponse = {
  indexed_files: number;
  indexed_chunks: number;
  last_indexed_at: string | null;
};

export type CodebaseIndexResponse = {
  repo_path: string;
  source_url: string | null;
  indexed_files: number;
  indexed_chunks: number;
  skipped_files: number;
  message: string;
  errors: string[];
};

export type IssueEvidenceItem = {
  claim: string;
  source_type: "ticket" | "code";
  source_id: string;
};

export type StructuredIssueDraft = {
  title: string;
  summary: string;
  user_impact: string;
  steps_to_reproduce: string[];
  expected_behavior: string;
  actual_behavior: string;
  suspected_root_cause: string;
  evidence: IssueEvidenceItem[];
  relevant_files: string[];
  confidence: "Low" | "Medium" | "High";
  open_questions: string[];
  priority_label: "P0 Critical" | "P1 High" | "P2 Medium" | "P3 Low";
};

export type IssueDraft = {
  id: number;
  cluster_id: number;
  title: string;
  body_markdown: string;
  priority_label: string;
  confidence_level: string;
  status: string;
  warnings: string[];
  github_issue_url: string | null;
  created_at: string;
};

export type IssueDraftResponse = {
  draft: IssueDraft;
  structured: StructuredIssueDraft;
  message: string;
};

export type IssueApprovalResponse = {
  issue: IssueDraft;
  github_issue_created: boolean;
  message: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    const fallback = `${response.status} ${response.statusText}`;
    let detail = fallback;
    try {
      const payload = (await response.json()) as { detail?: string };
      detail = payload.detail ?? fallback;
    } catch {
      detail = fallback;
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export function getTickets(): Promise<TicketListResponse> {
  return request<TicketListResponse>("/tickets");
}

export function getClusters(): Promise<ClusterListResponse> {
  return request<ClusterListResponse>("/clusters");
}

export function getClusterDetail(clusterId: number): Promise<ClusterDetailResponse> {
  return request<ClusterDetailResponse>(`/clusters/${clusterId}`);
}

export function retrieveCodeForCluster(clusterId: number): Promise<CodeRetrievalResponse> {
  return request<CodeRetrievalResponse>(`/clusters/${clusterId}/retrieve-code`, {
    method: "POST",
  });
}

export function draftIssueForCluster(clusterId: number): Promise<IssueDraftResponse> {
  return request<IssueDraftResponse>(`/clusters/${clusterId}/draft-issue`, {
    method: "POST",
  });
}

export function approveIssue(issueId: number): Promise<IssueApprovalResponse> {
  return request<IssueApprovalResponse>(`/issues/${issueId}/approve`, {
    method: "POST",
  });
}

export function uploadTickets(file: File): Promise<UploadTicketsResponse> {
  const formData = new FormData();
  formData.append("file", file);

  return request<UploadTicketsResponse>("/tickets/upload", {
    method: "POST",
    body: formData,
  });
}

export function processTickets(limit = 20, force = false): Promise<ProcessTicketsResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    force: String(force),
  });
  return request<ProcessTicketsResponse>(`/tickets/process?${params.toString()}`, {
    method: "POST",
  });
}

export function getCodebaseStatus(): Promise<CodebaseStatusResponse> {
  return request<CodebaseStatusResponse>("/codebase/status");
}

export function indexCodebase(localRepoPath: string): Promise<CodebaseIndexResponse> {
  return request<CodebaseIndexResponse>("/codebase/index", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ local_repo_path: localRepoPath }),
  });
}

export function indexGitHubCodebase(githubUrl: string): Promise<CodebaseIndexResponse> {
  return request<CodebaseIndexResponse>("/codebase/github/index", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ github_url: githubUrl }),
  });
}
