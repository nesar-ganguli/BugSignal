# BugSignal AI

BugSignal AI is a local, evidence-grounded engineering workflow system for turning messy support tickets into human-reviewed GitHub issue drafts.

It is not a generic chatbot. The app ingests support tickets, extracts structured facts with a local Ollama model, embeds and clusters related complaints, retrieves relevant code from a local repository, drafts a suspected root cause, runs evidence guard checks, and requires human approval before creating a GitHub issue.

The product principle is conservative by design: BugSignal AI says **suspected root cause**, not confirmed root cause, unless direct evidence exists in logs, stack traces, or retrieved code.

## Why It Is Agentic

BugSignal AI performs a multi-step engineering workflow:

1. Ingest support ticket CSVs.
2. Extract structured issue fields with a local LLM.
3. Embed tickets with `sentence-transformers/all-MiniLM-L6-v2`.
4. Cluster similar complaints with HDBSCAN.
5. Score cluster priority with an explainable rubric.
6. Index a local target codebase into SQLite and ChromaDB.
7. Retrieve code evidence with contextual embeddings, BM25, and reciprocal-rank fusion.
8. Draft a GitHub issue using only tickets and retrieved snippets.
9. Run evidence guard validation.
10. Wait for human approval before GitHub issue creation.

## Architecture

```text
React + Vite Dashboard
  | upload CSV / process tickets / review clusters / approve issue
  v
FastAPI Backend
  |-- Ticket API -> SQLite
  |-- Extraction Service -> Ollama JSON mode
  |-- Embedding Service -> all-MiniLM-L6-v2
  |-- Clustering Service -> HDBSCAN
  |-- Priority Service -> explainable scoring
  |-- Code Indexing Service -> symbol-aware chunks + contextual embeddings
  |-- Retrieval Service -> Chroma + SQLite FTS5/BM25 + rank fusion
  |-- Issue Drafting Service -> Ollama
  |-- Evidence Guard -> citation and hallucination checks
  |-- GitHub Service -> human-approved issue creation
```

## Tech Stack

- Backend: Python, FastAPI, SQLAlchemy, SQLite
- Frontend: React, Vite, TypeScript, Tailwind CSS
- Local LLM: Ollama, default `qwen2.5:7b`
- Embeddings: `sentence-transformers/all-MiniLM-L6-v2`
- Clustering: HDBSCAN
- Vector store: ChromaDB
- Code indexing: local filesystem traversal with deterministic file and symbol context
- GitHub issues: GitHub REST API after approval
- Workflow queue: Celery with Redis and database-backed progress tracking

## Current Status

Phase 11 is complete. The MVP includes:

- CSV ticket upload and persistence
- sample CSV with 40 tickets across 6 complaint groups
- Ollama structured extraction through one `LLMClient`
- local embeddings and HDBSCAN clustering
- explainable priority scoring
- cluster review dashboard with ticket, priority, confidence, and cohesion views
- symbol-aware local repo indexing into SQLite and ChromaDB
- contextualized hybrid code retrieval with BM25 and reciprocal-rank fusion
- evidence-grounded issue drafting
- evidence guard warnings for unsupported claims
- human approval before GitHub issue creation
- local approval fallback when GitHub credentials are missing
- polished dashboard workflow strip and README demo path

## Local Setup

### Backend

Use Python 3.11 or newer.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
alembic upgrade head
uvicorn app.main:app --reload
```

The backend runs at `http://localhost:8000`.

### Ollama

Install Ollama from `https://ollama.com`, then pull a local model:

```bash
ollama pull qwen2.5:7b
ollama serve
```

If your machine already has another model, set it in `.env`, for example:

```text
OLLAMA_MODEL=qwen2:7b
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:5173`.

### Workflow worker

Ticket extraction and clustering run outside the API process. Start PostgreSQL and Redis, apply
database migrations, then run the Celery worker from `backend`:

```bash
docker compose up -d postgres redis
cd backend
source .venv/bin/activate
alembic upgrade head
celery -A app.celery_app.celery_app worker --loglevel=info
```

On macOS, Redis can also run directly without Docker:

```bash
brew install python@3.11 redis
redis-server --daemonize yes
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
celery -A app.celery_app.celery_app worker --loglevel=info --pool=solo --concurrency=1
```

Workflow state remains in the application database and is available through `GET /workflows` and
`GET /workflows/{workflow_id}` even if the browser disconnects.

### Operational health and logging

The API emits structured JSON request logs and returns an `X-Request-ID` header. Clients may send
their own `X-Request-ID` (up to 128 characters) to correlate frontend, API, and worker incidents.

- `GET /health/live` confirms the API process is alive without checking dependencies.
- `GET /health/ready` returns `200` only when PostgreSQL, Redis, and the configured Ollama model are ready.
- `GET /health` remains the detailed Ollama status endpoint used by the dashboard.

Queued or running workflows older than `STALE_WORKFLOW_TIMEOUT_SECONDS` are marked failed before a
new workflow is accepted for that project, preventing abandoned jobs from blocking future runs.

### Production security controls

Set `ENVIRONMENT=production`, configure `ALLOWED_HOSTS` and `CORS_ORIGINS` explicitly, and terminate
TLS at the load balancer or reverse proxy. Production mode disables OpenAPI documentation and adds
HSTS alongside frame, MIME-sniffing, referrer, and browser-permission protections. Request bodies
and ticket CSVs have configurable size limits. Workflow, indexing, retrieval, and drafting endpoints
use a Redis-backed fixed-window rate limit keyed by a hashed client identity; `429` responses include a
`Retry-After` header.

### Database migrations

The API and utility scripts never create or alter tables automatically. Apply committed migrations
before starting a new API or worker release:

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

Check that the database matches the SQLAlchemy models with `alembic check`. Create future schema
changes with `alembic revision --autogenerate -m "description"`, inspect the generated migration,
and test both upgrade and downgrade paths before committing it.

SQLite remains supported for tests and lightweight local evaluation. PostgreSQL is the expected
runtime database for concurrent API and worker processes. A database created before Alembic was
introduced should be backed up and reviewed before using `alembic stamp 20260801_0001`; stamping
records a version but does not repair a mismatched schema.

## Environment Variables

```text
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DEVICE=cpu
OIDC_ENABLED=false
OIDC_ISSUER=https://your-provider.example.com/
OIDC_AUDIENCE=https://api.bugsignal.local
OIDC_JWKS_URL=https://your-provider.example.com/.well-known/jwks.json
OIDC_ALGORITHMS=RS256
OIDC_ORGANIZATION_CLAIM=org_id
OIDC_ROLES_CLAIM=roles
DATABASE_URL=postgresql+psycopg://bugsignal:bugsignal_local@localhost:5432/bugsignal
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
DATABASE_POOL_TIMEOUT_SECONDS=30
GITHUB_TOKEN=
GITHUB_REPO_OWNER=
GITHUB_REPO_NAME=
CHROMA_PERSIST_DIR=./chroma_data
CLONED_REPOS_DIR=./repos
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
VITE_API_BASE_URL=http://localhost:8000
VITE_OIDC_ENABLED=false
VITE_OIDC_AUTHORITY=https://your-provider.example.com/
VITE_OIDC_CLIENT_ID=bugsignal-spa
VITE_OIDC_REDIRECT_URI=http://localhost:5173
VITE_OIDC_POST_LOGOUT_REDIRECT_URI=http://localhost:5173
VITE_OIDC_SCOPE=openid profile email
```

### Authentication and tenant isolation

BugSignal accepts standards-compliant OIDC access tokens and uses Authorization Code + PKCE in
the browser. Deployed environments must enable OIDC in both backend and frontend configuration.
The backend validates token signature, issuer, audience, expiry, and required claims.

The configured organization claim selects an organization. Every organization receives a default
project, and every ticket, cluster, code chunk, evidence record, issue draft, and workflow belongs
to exactly one project. API requests select a project with `X-Project-ID`; omitted headers use the
organization's first project. The backend verifies project ownership and returns 404 for projects
outside the authenticated organization. Development mode provisions an isolated
`local-development` organization and should never be enabled in production.

`CLONED_REPOS_DIR` is where public GitHub repos are cloned when you index by URL. GitHub issue settings are optional. Without them, approved issue drafts remain approved locally.

## Demo Flow

1. Start Ollama.
2. Start the backend.
3. Start the frontend.
4. Upload `backend/app/data/sample_tickets.csv`.
5. Click **Process Tickets**.
6. Index code in the **Codebase Index** panel. You can use either a local path or a public GitHub URL such as `https://github.com/owner/repo`.
7. Select a cluster.
8. Click **Retrieve Code**.
9. Click **Draft Issue**.
10. Review evidence, warnings, confidence, and suspected root cause.
11. Click **Approve Issue**.

If GitHub env vars are configured, approval creates the GitHub issue. Otherwise, the draft is marked approved locally and can be retried after credentials are added.

Re-index a repository after changing indexing or embedding settings. The index stores the original
source for evidence display and a separate contextualized representation containing file path,
module, language, enclosing symbol, signature, imports, and nearby symbols for retrieval.
The same contextualized representation is indexed in ChromaDB and database full-text search
(PostgreSQL GIN/`tsvector` in production, SQLite FTS5 in tests). Retrieval combines
semantic and BM25 result ranks using reciprocal-rank fusion, then applies bounded boosts for exact
routes, identifiers, error strings, and function names.

## API Overview

- `GET /health`
- `POST /tickets/upload`
- `GET /tickets`
- `POST /tickets/process`
- `POST /workflows/ticket-processing`
- `GET /workflows`
- `GET /workflows/{workflow_id}`
- `POST /workflows/{workflow_id}/cancel`
- `GET /clusters`
- `POST /clusters/rebuild`
- `GET /clusters/{cluster_id}`
- `POST /clusters/{cluster_id}/retrieve-code`
- `POST /clusters/{cluster_id}/draft-issue`
- `POST /codebase/index`
- `POST /codebase/github/index`
- `GET /codebase/status`
- `GET /issues`
- `POST /issues/{issue_id}/approve`

## Safety Choices

- All LLM calls go through local Ollama via `LLMClient`.
- No OpenAI, Anthropic, Groq, or paid external LLM APIs.
- Issue drafts cite ticket IDs or retrieved code evidence IDs.
- Drafts use “suspected root cause” language.
- Weak evidence produces “Insufficient evidence to identify a suspected root cause.”
- Evidence guard warnings are visible before approval.
- GitHub issue creation only happens after a human clicks approve.
- Missing GitHub credentials never block the local demo.

## Sample Data

The included sample CSV covers:

- checkout hangs after session expiry
- password reset email not arriving
- uploaded file disappears after refresh
- dashboard loads slowly for large accounts
- duplicate charge after retrying payment
- mobile layout broken on settings page

## Notes For Portfolio Review

For the strongest demo, index a real local application repo that matches the ticket domain. If you index BugSignal itself, retrieval may correctly report weak evidence because the checkout/payment code does not exist in this project.
