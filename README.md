# BugSignal AI

BugSignal AI is a local, agentic engineering workflow system for turning messy support tickets into evidence-grounded GitHub issue drafts. It uploads ticket CSVs, extracts structured fields with a local Ollama model, embeds and clusters complaints, retrieves relevant codebase context, drafts a suspected root cause, and waits for human approval before creating a GitHub issue.

The project principle is intentionally conservative: the system says **suspected root cause**, not confirmed root cause, unless direct evidence exists in logs, stack traces, or retrieved code. Drafts are designed to make weak evidence visible.

## Why It Is Agentic

BugSignal AI performs a multi-step engineering workflow instead of answering a single chat prompt:

1. Ingest support tickets.
2. Extract structured ticket facts.
3. Embed and cluster related complaints.
4. Score cluster priority with an explainable rubric.
5. Index a target codebase.
6. Retrieve likely relevant code snippets.
7. Draft an evidence-cited GitHub issue.
8. Run guardrail validation over the draft.
9. Require human approval before GitHub issue creation.

## Architecture

```text
React Dashboard
  | upload CSV / review clusters / approve issue
  v
FastAPI Backend
  |-- Ticket API -> SQLite tickets
  |-- Extraction Service -> Ollama JSON mode
  |-- Embedding Service -> all-MiniLM-L6-v2
  |-- Clustering Service -> HDBSCAN
  |-- Priority Service -> explainable scoring
  |-- Code Indexing Service -> repo scan + ChromaDB
  |-- Retrieval Service -> semantic + keyword search
  |-- Issue Drafting Service -> Ollama
  |-- Evidence Guard -> citation and hallucination checks
  |-- GitHub Service -> approved issue creation
```

## Tech Stack

- Backend: Python, FastAPI, SQLAlchemy, SQLite
- Local AI: Ollama with `qwen2.5:7b` by default
- Embeddings: `sentence-transformers/all-MiniLM-L6-v2`
- Clustering: HDBSCAN
- Vector storage: ChromaDB
- Code scanning: GitPython or local filesystem traversal
- GitHub issues: PyGithub or REST API after approval
- Frontend: React, Vite, TypeScript, Tailwind CSS

## Revised Implementation Plan

Phase 1 now includes a small ticket upload UI so the intake path is visible immediately. Durable parsing and persistence still happen in Phase 2.

1. Create full project structure, FastAPI app, Vite React app, health endpoint, and CSV upload UI shell.
2. Implement ticket upload persistence, SQLite repositories, ticket listing, and sample ticket seeding.
3. Implement Ollama `LLMClient` and structured ticket extraction.
4. Implement local embeddings and HDBSCAN clustering.
5. Implement cluster listing, cluster detail, cohesion score, confidence score, and priority scoring.
6. Implement codebase indexing and ChromaDB storage.
7. Implement hybrid code retrieval for a cluster.
8. Implement issue drafting with suspected root cause and evidence citations.
9. Implement evidence guard validation.
10. Implement GitHub issue creation after human approval.
11. Polish frontend workflows and README demo path.

## Current Status

Phase 1 scaffold is in progress:

- Backend app structure exists.
- `GET /health` returns backend status and Ollama reachability.
- `POST /tickets/upload` accepts a CSV and returns a preview response.
- Frontend dashboard includes health status, overview cards, cluster placeholders, and CSV upload.
- Sample CSV includes 40 tickets across 6 issue groups.

## Local Setup

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
uvicorn app.main:app --reload
```

The backend runs at `http://localhost:8000`.

### 2. Ollama

Install Ollama from `https://ollama.com`, then pull the default local model:

```bash
ollama pull qwen2.5:7b
ollama serve
```

You can also use `llama3.1:8b` by setting:

```bash
OLLAMA_MODEL=llama3.1:8b
```

### 3. Frontend

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
```

## Demo Flow

1. Start Ollama and pull `qwen2.5:7b`.
2. Start the backend.
3. Start the frontend.
4. Upload `backend/app/data/sample_tickets.csv`.
5. Process tickets.
6. Review generated clusters.
7. Index a local repository.
8. Retrieve code evidence for a cluster.
9. Generate a GitHub issue draft.
10. Review warnings and approve the issue when ready.

Steps 5-10 are implemented in later phases.

## Safety And Design Choices

- Local-only LLM calls through `LLMClient`.
- No OpenAI, Anthropic, Groq, or paid external LLM APIs.
- Evidence-grounded output with cited ticket or code sources.
- Suspected root cause language by default.
- Human approval required before GitHub issue creation.
- Missing GitHub token keeps approved issues local.
- Guardrails flag invented files, unsupported evidence IDs, and unsupported technical claims.
