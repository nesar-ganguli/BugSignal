import { FormEvent, useEffect, useState } from "react";
import { Code2, Github, Loader2, RefreshCw } from "lucide-react";

import {
  CodebaseStatusResponse,
  getCodebaseStatus,
  indexCodebase,
  indexGitHubCodebase,
} from "../api/client";

function formatDate(value: string | null) {
  if (!value) return "Never";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

type CodebaseIndexPageProps = {
  onStatusChange?: (status: CodebaseStatusResponse) => void;
};

export function CodebaseIndexPage({ onStatusChange }: CodebaseIndexPageProps) {
  const [repoPath, setRepoPath] = useState("");
  const [sourceMode, setSourceMode] = useState<"local" | "github">("local");
  const [status, setStatus] = useState<CodebaseStatusResponse | null>(null);
  const [isIndexing, setIsIndexing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refreshStatus = () => {
    getCodebaseStatus()
      .then((response) => {
        setStatus(response);
        onStatusChange?.(response);
        setError(null);
      })
      .catch((statusError) => {
        setError(statusError instanceof Error ? statusError.message : "Unable to load codebase status.");
      });
  };

  useEffect(() => {
    refreshStatus();
  }, []);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!repoPath.trim()) return;

    setIsIndexing(true);
    setError(null);
    setMessage(null);

    try {
      const input = repoPath.trim();
      const result = sourceMode === "github" ? await indexGitHubCodebase(input) : await indexCodebase(input);
      setMessage(`${result.message} Skipped ${result.skipped_files} files.`);
      refreshStatus();
    } catch (indexError) {
      setError(indexError instanceof Error ? indexError.message : "Codebase indexing failed.");
    } finally {
      setIsIndexing(false);
    }
  };

  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex items-start gap-3">
          <div className="grid h-10 w-10 place-items-center rounded border border-teal-100 bg-teal-50 text-signal">
            <Code2 size={20} aria-hidden="true" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-ink">Codebase Index</h2>
            <p className="text-sm text-slate-600">Current index: {status?.indexed_chunks ?? 0} chunks across {status?.indexed_files ?? 0} files.</p>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3 text-sm">
          <Metric label="Files" value={String(status?.indexed_files ?? 0)} />
          <Metric label="Chunks" value={String(status?.indexed_chunks ?? 0)} />
          <Metric label="Last Index" value={formatDate(status?.last_indexed_at ?? null)} />
        </div>
      </div>

      <form className="mt-5 grid gap-3" onSubmit={onSubmit}>
        <div className="inline-flex w-fit rounded border border-line bg-panel p-1">
          <button
            className={`rounded px-3 py-1.5 text-sm font-semibold transition ${
              sourceMode === "local" ? "bg-white text-ink shadow-sm" : "text-slate-600 hover:text-ink"
            }`}
            type="button"
            onClick={() => setSourceMode("local")}
          >
            Local path
          </button>
          <button
            className={`inline-flex items-center gap-2 rounded px-3 py-1.5 text-sm font-semibold transition ${
              sourceMode === "github" ? "bg-white text-ink shadow-sm" : "text-slate-600 hover:text-ink"
            }`}
            type="button"
            onClick={() => setSourceMode("github")}
          >
            <Github size={15} aria-hidden="true" />
            GitHub URL
          </button>
        </div>

        <div className="grid gap-3 lg:grid-cols-[1fr_auto]">
          <input
            className="min-w-0 rounded border border-line bg-panel px-3 py-2 text-sm text-slate-700"
            placeholder={sourceMode === "github" ? "https://github.com/owner/repo" : "/Users/you/projects/target-app"}
            value={repoPath}
            onChange={(event) => setRepoPath(event.target.value)}
          />
        <button
          className="inline-flex items-center justify-center gap-2 rounded bg-ink px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-400"
          type="submit"
          disabled={isIndexing || !repoPath.trim()}
        >
          {isIndexing ? <Loader2 className="animate-spin" size={16} aria-hidden="true" /> : <RefreshCw size={16} aria-hidden="true" />}
          {sourceMode === "github" ? "Clone & Index" : "Index Repo"}
        </button>
        </div>
      </form>

      {message ? (
        <div className="mt-4 rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
          {message}
        </div>
      ) : null}

      {error ? (
        <div className="mt-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      ) : null}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-line bg-panel px-3 py-2">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 whitespace-nowrap text-sm font-bold text-ink">{value}</div>
    </div>
  );
}
