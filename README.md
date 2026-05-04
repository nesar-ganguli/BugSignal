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
7. Retrieve code evidence with hybrid semantic and keyword search.
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
  |-- Code Indexing Service -> repo scan + ChromaDB
  |-- Retrieval Service -> semantic + keyword search
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
- Code indexing: local filesystem traversal
- GitHub issues: GitHub REST API after approval

## Current Status

Phase 11 is complete. The MVP includes:

- CSV ticket upload and persistence
- sample CSV with 40 tickets across 6 complaint groups
- Ollama structured extraction through one `LLMClient`
- local embeddings and HDBSCAN clustering
- explainable priority scoring
- cluster review dashboard with ticket, priority, confidence, and cohesion views
- local repo indexing into SQLite and ChromaDB
- hybrid code retrieval for ticket clusters
- evidence-grounded issue drafting
- evidence guard warnings for unsupported claims
- human approval before GitHub issue creation
- local approval fallback when GitHub credentials are missing
- polished dashboard workflow strip and README demo path

## Local Setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
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

## Environment Variables

```text
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
DATABASE_URL=sqlite:///./bugsignal.db
GITHUB_TOKEN=
GITHUB_REPO_OWNER=
GITHUB_REPO_NAME=
CHROMA_PERSIST_DIR=./chroma_data
CLONED_REPOS_DIR=./repos
VITE_API_BASE_URL=http://localhost:8000
```

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

## API Overview

- `GET /health`
- `POST /tickets/upload`
- `GET /tickets`
- `POST /tickets/process`
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
