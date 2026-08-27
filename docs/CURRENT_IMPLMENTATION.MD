# BugSignal current implementation

Last verified: 2026-08-26 against the current working tree.

> Maintenance contract: this is a living implementation map, not a roadmap. Every behavior-changing update or feature must update this file in the same change. Describe what the code does now, including partial or legacy paths. Root-level `AGENTS.md` makes this a repository instruction for future coding agents.

## Read this first

BugSignal is a multi-tenant, evidence-grounded support-ticket triage application. It imports ticket CSVs, uses a local Ollama model to extract structured facts, groups related tickets, assigns deterministic priority, retrieves relevant code from an indexed repository, drafts a tentative GitHub issue, runs evidence checks, and requires a human to approve the draft before any GitHub issue can be created.

The most important current behavior is:

- Uploading a CSV starts the `triage_pipeline` Celery workflow automatically.
- The pipeline extracts all pending/stale tickets in batches and rebuilds clusters once.
- If the project has no indexed code, the same workflow pauses at `waiting_for_codebase`.
- Indexing a local or public GitHub repository resumes that paused workflow.
- Eligible clusters receive code retrieval and an issue draft automatically.
- Manual retrieval and drafting endpoints remain available in the UI.
- GitHub creation never happens automatically. A human must approve a draft.

Two processing paths currently coexist and must not be confused:

| Trigger | Workflow type | Current behavior |
| --- | --- | --- |
| CSV upload (`POST /tickets/upload`) | `triage_pipeline` | Preferred resumable path: extraction, clustering, optional pause, retrieval, drafting |
| **Process Tickets** button (`POST /workflows/ticket-processing`) | `ticket_processing` | Older bounded path: extracts up to the requested limit and rebuilds clusters; does not continue to retrieval/drafting |
| `POST /tickets/process` | none (synchronous) | Legacy API path for extraction and clustering; retained for compatibility |

## Product and safety invariants

These are implementation constraints, not marketing language:

1. A root cause is always tentative. Draft prompts require the phrase **suspected root cause** and evidence guard warns when the language is definite.
2. Drafting requires retrieved code evidence. `draft_issue_for_cluster` rejects a cluster with no stored retrieval evidence.
3. Model output does not determine priority. Priority is calculated by deterministic rules and overwrites any priority returned by the model.
4. Model booleans do not determine the four risk flags. Payment/revenue, data-loss, auth, and performance flags are recalculated from ticket/extracted text.
5. The model may cite only supplied ticket IDs, stored evidence IDs, and retrieved file paths. Evidence guard reports unsupported citations and technical claims.
6. GitHub issue creation is human-gated through `POST /issues/{issue_id}/approve`.
7. Every triage artifact and workflow is project-scoped. API repository queries for tickets, clusters, code, evidence, drafts, and workflows must include `project_id`; identity and organization records form the enclosing tenant layer.
8. OIDC is optional only for local development. When disabled, the backend provisions a local developer, organization, and default project.
9. SQLAlchemy models do not create or migrate runtime tables. Alembic migrations must be applied explicitly.

## Runtime architecture

```text
React/Vite browser
  | Authorization bearer token (when OIDC is enabled)
  | X-Project-ID tenant selector
  v
FastAPI API
  |-- PostgreSQL/SQLite: tickets, clusters, chunks, evidence, drafts, workflows, tenancy
  |-- Redis: Celery broker/results and expensive-endpoint rate limiting
  |-- Celery worker: resumable ticket and triage workflows
  |-- Ollama: JSON extraction and issue drafting
  |-- sentence-transformers: ticket and code embeddings
  |-- HDBSCAN/scikit-learn: clustering and low-cohesion splitting
  |-- ChromaDB: semantic code index
  |-- database full-text index: lexical code search
  |-- GitHub API: issue creation after approval only
```

Primary entry points:

- Backend app: `backend/app/main.py`
- Celery setup and task registration: `backend/app/celery_app.py`
- End-to-end worker: `backend/app/tasks/workflow_tasks.py`
- Frontend shell: `frontend/src/App.tsx`
- Main UI and polling: `frontend/src/pages/Dashboard.tsx`
- Browser API boundary: `frontend/src/api/client.ts`

## End-to-end flow

### 0. Authentication, organization, and project selection

All routers except health and authentication are protected by tenant resolution in `backend/app/main.py`.

`require_principal` validates an OIDC bearer token when `OIDC_ENABLED=true`. It validates signature, issuer, audience, expiry, and required claims. With OIDC disabled, it returns the built-in local developer identity.

`require_tenant_context` provisions or resolves a `User`, `Organization`, membership, and project. The browser stores the selected project in `localStorage` as `bugsignal_project_id` and sends it as `X-Project-ID`. The backend verifies that the project belongs to the authenticated organization; cross-organization IDs return 404. Viewers are read-only, while owner/admin/member roles can use write endpoints.

### 1. Ticket import and automatic queueing

`POST /tickets/upload` accepts one CSV up to `MAX_TICKET_UPLOAD_SIZE_BYTES`.

Required CSV columns are `external_ticket_id`, `title`, and `body`. Optional fields are `created_at`, `source`, `customer_plan`, and `severity`. Rows are upserted by `(project_id, external_ticket_id)`. Updating a source ticket makes its previous extraction stale through repository logic.

After the database commit, `queue_triage_workflow`:

- returns an already queued/running triage workflow instead of creating a duplicate;
- requeues an existing `waiting_for_codebase` workflow when new tickets arrive; or
- creates and dispatches a new `triage_pipeline` workflow.

The upload remains successful if queue dispatch fails, and the response explains that tickets were saved but automation could not be queued.

### 2. Structured extraction

The worker pulls pending/stale tickets in batches of `TRIAGE_BATCH_SIZE` (default `20`). Each ticket is sent to the single `LLMClient` abstraction using Ollama `/api/generate`, JSON mode, temperature `0`, and a 90-second extraction timeout.

The extraction schema contains:

- intent, user action, expected behavior, actual behavior, and feature area;
- error terms and normalized sentiment;
- payment/revenue, data-loss, auth, and performance flags.

The response is normalized and Pydantic-validated. Sentiment falls back to deterministic term matching if invalid. The four risk flags are always recalculated deterministically. Each ticket is committed independently. Schema/model failures mark that ticket `failed`; an unavailable Ollama instance fails/retries the workflow. The automated triage path excludes already-failed tickets so it cannot retry them forever.

### 3. Embedding, clustering, and priority

Once automated extraction has exhausted pending/stale tickets, all successfully extracted tickets are embedded with `sentence-transformers/all-MiniLM-L6-v2` (configurable) and clustered together.

Clustering rules in `backend/app/services/clustering_service.py`:

- HDBSCAN uses minimum cluster size `3`, minimum samples `1`, and Euclidean distance.
- Fewer than three tickets become one **Needs manual triage** group.
- Groups below `0.50` cohesion and large enough to split are passed through agglomerative clustering.
- Split groups smaller than three or below `0.35` cohesion are moved to manual triage.
- All outlier groups are merged into one **Needs manual triage** cluster.
- Confidence is derived from cohesion plus a bounded ticket-count bonus.

Rebuilding clusters clears the project's existing cluster assignments and creates a fresh set. Every cluster starts in `needs_review`.

Priority is explainable and deterministic (`backend/app/services/priority_service.py`). Signals include data loss, payment/revenue, auth, performance, ticket count, angry/urgent sentiment, recent ticket velocity, and customer severity. Scores map to P0 at 75+, P1 at 50+, P2 at 25+, and P3 below 25.

### 4. Pause/resume boundary

After clustering, the triage worker checks for project code chunks.

If none exist, it persists intermediate counts in `WorkflowRun.result_json`, changes state to `waiting_for_codebase`, sets progress to 55%, and exits cleanly. This is a pause, not a failure.

Both code-index endpoints call `resume_triage_after_codebase` after a successful index. That function reuses the same workflow ID, sets `current_step=codebase_indexed`, dispatches it again, and causes the worker to skip extraction and clustering on resume.

### 5. Codebase indexing

The user can index either:

- a local directory visible to the backend via `POST /codebase/index`; or
- a public GitHub URL via `POST /codebase/github/index`, cloned under `CLONED_REPOS_DIR`.

`backend/app/services/code_indexing_service.py` scans supported text/code files, ignores generated/vendor directories and unsupported or oversized/binary files, creates symbol-aware or fixed-line chunks, and adds deterministic context such as path, language, module, imports, signature, enclosing symbol, and nearby symbols.

For each project/repository pair, reindexing replaces old database/FTS rows and Chroma records for that repository. Original source is stored for evidence display; contextualized text is embedded for retrieval. Chroma metadata and embedding IDs include `project_id`.

### 6. Hybrid code retrieval

For each eligible cluster, BugSignal builds a query from cluster metadata and member-ticket facts. Retrieval combines:

- the top 30 semantic Chroma candidates;
- the top 30 database full-text candidates (SQLite FTS5/BM25 or PostgreSQL `ts_rank_cd`);
- reciprocal-rank fusion with semantic weight `0.55`, BM25 weight `0.45`, and `RRF_K=60`;
- bounded boosts for exact error/technical-term matches.

The top eight final candidates are stored as `RetrievedEvidence` and returned with file, line range, original snippet, score, retrieval type, and a human-readable reason.

The automatic pipeline skips clusters titled **Needs manual triage** and clusters with cohesion below `TRIAGE_MIN_CLUSTER_COHESION` (default `0.5`). One cluster failure is captured in the workflow result and does not stop other eligible clusters.

### 7. LLM issue drafting and evidence guard

Automatic triage drafts only when retrieval returned snippets and no prior draft exists for the cluster. Manual drafting is available at `POST /clusters/{cluster_id}/draft-issue`.

The prompt includes at most eight tickets and the top five stored evidence rows. It requires a JSON object with title, summary, impact, reproduction steps, expected/actual behavior, suspected root cause, citations, relevant files, confidence, open questions, and priority.

Post-processing:

- missing confidence defaults conservatively to `Low`;
- priority is overwritten with the deterministic cluster priority;
- Pydantic validates the structured response;
- evidence guard checks citation IDs, retrieved file paths, unsupported platforms/versions/quoted technical details, and tentative root-cause language;
- warnings are embedded in the rendered Markdown issue but do not silently disappear;
- the cluster moves to `ready_for_issue` and the draft remains `draft`.

Evidence guard is a warning layer, not formal proof that every natural-language claim is supported. Human review remains mandatory.

### 8. Human approval and GitHub creation

`POST /issues/{issue_id}/approve` is the only GitHub creation path.

- With complete GitHub configuration, `GitHubService` creates the issue, marks the draft and cluster `issue_created`, and stores the URL.
- Without GitHub credentials/repository configuration, no remote call is made; the draft is marked `approved` locally.
- An already-created issue returns idempotently without creating a duplicate.

## Workflow state machine

```text
queued -> running -> waiting_for_codebase -> queued -> running -> completed
             |                                  |
             +------------> retrying/running <--+
             |                                  |
             +------------> failed              +----> failed
             |
             +------------> cancelled
```

Persisted public statuses are `queued`, `running`, `waiting_for_codebase`, `completed`, `failed`, and `cancelled`. During a retry the repository sets the status back to `queued` and increments `attempt_count`. Celery tasks retry at most twice with exponential delays. Workflow state is stored in the application database, so browser disconnects do not lose progress.

The frontend polls the active workflow every two seconds only while it is queued/running. It treats `waiting_for_codebase` as a stable paused state and directs the user to the Codebase tab.

## Data model and ownership

Core tables in `backend/app/models.py`:

| Model | Purpose | Important ownership/relationship |
| --- | --- | --- |
| `User` | OIDC/local identity | Unique by issuer + subject |
| `Organization` | Tenant boundary | External organization ID |
| `OrganizationMembership` | User role in organization | owner/admin/member/viewer |
| `Project` | Working isolation boundary | Belongs to organization |
| `Ticket` | Raw and extracted support data | Project-scoped; optional cluster |
| `Cluster` | Group, priority, confidence, review state | Project-scoped; has tickets |
| `CodeChunk` | Original and contextualized repository chunk | Project + repository scoped |
| `RetrievedEvidence` | Ranked cluster-to-code link | Project + cluster + code chunk |
| `IssueDraft` | Markdown and review/publication state | Project + cluster |
| `WorkflowRun` | Durable async progress/result/error state | Project + workflow type |

PostgreSQL is the expected concurrent runtime. SQLite remains supported for tests and lightweight local evaluation. Chroma persists separately at `CHROMA_PERSIST_DIR`; Redis is not the source of truth for workflow progress.

## HTTP surface

All listed endpoints are current FastAPI routes. Write endpoints require editor access unless noted.

| Area | Endpoints |
| --- | --- |
| Health | `GET /health/live`, `GET /health/ready`, `GET /health` |
| Identity/projects | `GET /auth/me`, `GET /projects`, `POST /projects` (admin) |
| Tickets | `POST /tickets/upload`, `GET /tickets`, `POST /tickets/process` (legacy) |
| Workflows | `POST /workflows/ticket-processing`, `GET /workflows`, `GET /workflows/{id}`, `POST /workflows/{id}/cancel` |
| Clusters | `GET /clusters`, `POST /clusters/rebuild`, `GET /clusters/{id}`, `POST /clusters/{id}/retrieve-code`, `POST /clusters/{id}/draft-issue` |
| Codebase | `GET /codebase/status`, `POST /codebase/index`, `POST /codebase/github/index` |
| Issues | `GET /issues`, `POST /issues/{id}/approve` |

Expensive processing, clustering, indexing, retrieval, and drafting endpoints use the Redis-backed fixed-window rate limiter. The request middleware also enforces body-size limits, emits structured JSON logs, attaches `X-Request-ID`, and adds browser security headers. Production disables API docs, rejects wildcard CORS, and enables HSTS.

## Frontend behavior

The React dashboard is a single-page, hash-tabbed interface:

1. **Overview** shows totals, pipeline progress, health, and the active workflow.
2. **Tickets** imports CSV data, exposes the explicit bounded Process Tickets action, and lists tickets.
3. **Clusters** reviews grouping, priority, confidence, cohesion, and member tickets.
4. **Codebase** indexes a local path or public GitHub repository.
5. **Evidence & Issues** manually retrieves evidence, drafts, reviews warnings, and approves.

The UI can display and operate the automatic workflow, but manual controls remain important for skipped clusters, reruns, diagnosis, and the older processing path.

## Configuration that changes behavior

See `.env.example` and `backend/app/config.py` for the complete list. The values most likely to change behavior are:

- `OLLAMA_BASE_URL`, `OLLAMA_MODEL`: local generation service and model.
- `EMBEDDING_MODEL`, `EMBEDDING_DEVICE`: embedding identity/runtime.
- `TRIAGE_BATCH_SIZE`: automatic extraction batch size.
- `TRIAGE_MIN_CLUSTER_COHESION`: eligibility threshold for automatic retrieval/drafting.
- `DATABASE_URL` and pool settings: durable relational store.
- `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`: task transport/result backend.
- `CHROMA_PERSIST_DIR`: semantic code index location.
- `CLONED_REPOS_DIR`: managed destination for public repository clones.
- `OIDC_*`: identity and organization-claim mapping.
- `GITHUB_TOKEN`, `GITHUB_REPO_OWNER`, `GITHUB_REPO_NAME`: approval-time publication.
- `RATE_LIMIT_*`, upload/body limits, hosts, CORS, and `ENVIRONMENT`: security/operations.

Changing an embedding model or contextualization/indexing logic requires reindexing repositories. Existing vectors are not automatically migrated.

## Local development and verification

Expected services are PostgreSQL, Redis, Ollama, the FastAPI process, the Celery worker, and Vite.

```bash
docker compose up -d postgres redis
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

In another backend shell:

```bash
source .venv/bin/activate
celery -A app.celery_app.celery_app worker --loglevel=info
```

On macOS the configured worker uses the solo pool because PyTorch MPS is not fork-safe. Then start the frontend with `npm install && npm run dev` from `frontend`.

Verification commands:

```bash
cd backend
pytest
alembic check

cd ../frontend
npm run build
```

The repository currently has backend tests for extraction, clustering/triage, indexing, retrieval, drafting, tenancy, security controls, workflow persistence, and operational health. There is no configured frontend unit-test script; `npm run build` is the available TypeScript/build check.

## Failure, retry, and recovery semantics

- Ollama unavailability fails the current task attempt and can trigger Celery retry.
- A bad LLM response fails only the individual ticket in batched extraction; automatic triage does not repeatedly select failed tickets.
- A per-cluster retrieval/draft error is recorded in `cluster_results` and processing continues.
- Queue dispatch failures are persisted on the workflow; upload/index responses preserve their primary successful operation when possible.
- Queued/running workflows older than `STALE_WORKFLOW_TIMEOUT_SECONDS` are marked failed before the explicit ticket-processing endpoint accepts another run.
- Cancellation is cooperative: the task ID is revoked without terminating the worker. Extraction loops re-read workflow status at checkpoints, so cancellation is not guaranteed to interrupt an in-progress embedding, clustering, retrieval, or LLM call immediately.
- Reindexing is the recovery path after embedding/index-context changes.

## Current limitations and sharp edges

- The automatic `triage_pipeline` is created indirectly by ticket upload; there is no dedicated public endpoint to start or force that full pipeline.
- The explicit **Process Tickets** button still starts `ticket_processing`, not the full automatic triage pipeline.
- The README demo steps describe the manual workflow, while CSV upload now also starts automation. Both are valid, but the automated path is preferred.
- Automatic triage skips manual-triage and low-cohesion clusters. A human can still inspect them, but should treat conclusions cautiously.
- Evidence guard detects several common unsupported-claim patterns but is not a general factual verifier.
- Local repository indexing reads paths from the backend host. A browser user cannot upload a repository directory through the current API.
- GitHub repository import is designed for public clone URLs; private-repository import credentials are not implemented in that path.
- Workflow result payloads vary by workflow type. Consumers must check `workflow_type` rather than assuming one fixed result shape.
- Cluster rebuilding replaces the current grouping. Code that adds cluster-linked state must account for rebuild behavior and database referential integrity.

## Change map for humans and coding agents

Start in these files for common changes:

| Change | Primary files | Also inspect |
| --- | --- | --- |
| Ticket CSV/input fields | `ticket_csv_service.py`, `ticket_schema.py`, `models.py` | migrations, frontend types, seed/sample CSVs |
| Extraction prompt/schema | `ticket_extraction_service.py`, `llm_client.py` | tests, priority/clustering inputs |
| Automatic orchestration | `workflow_tasks.py`, `triage_workflow_service.py` | workflow repository/schema, tickets/codebase APIs, dashboard polling |
| Clustering/priority | `clustering_service.py`, `cluster_workflow_service.py`, `priority_service.py` | cluster schemas/UI, thresholds/tests |
| Code indexing | `code_indexing_service.py`, `code_repository.py` | Chroma service, migration/FTS behavior, reindex notes |
| Retrieval ranking | `code_retrieval_service.py` | evidence persistence, UI evidence display, tests |
| Draft schema/prompt | `issue_drafting_service.py`, `issue_schema.py` | evidence guard, frontend types/rendering, tests |
| Approval/GitHub | `issues.py`, `github_service.py` | issue/cluster repositories, configuration |
| Auth/tenancy | `auth_service.py`, `tenant_service.py` | every repository query, migrations, frontend auth/client |
| Operations/security | `main.py`, `health.py`, `rate_limit_service.py`, `config.py` | `.env.example`, Docker/README, tests |
| Frontend workflow | `Dashboard.tsx`, `client.ts` | component props, backend response schemas |

When changing any row above, update this document with the resulting behavior and update the Last verified date. If code and this file disagree, code is the immediate runtime truth and this file must be corrected in the same change.
