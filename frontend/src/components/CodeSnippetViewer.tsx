import { CodeSnippet } from "../api/client";

type CodeSnippetViewerProps = {
  snippet: CodeSnippet;
};

export function CodeSnippetViewer({ snippet }: CodeSnippetViewerProps) {
  return (
    <article className="overflow-hidden rounded border border-line bg-white">
      <div className="flex flex-col gap-2 border-b border-line bg-panel px-3 py-2 text-sm sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <div className="truncate font-semibold text-ink">{snippet.file_path}</div>
          <div className="text-xs text-slate-500">
            Lines {snippet.start_line}-{snippet.end_line}
            {snippet.code_chunk_id ? ` · chunk ${snippet.code_chunk_id}` : ""}
            {snippet.evidence_id ? ` · evidence ${snippet.evidence_id}` : ""}
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="rounded border border-teal-200 bg-teal-50 px-2 py-1 font-semibold text-teal-700">
            {Math.round(snippet.relevance_score * 100)}%
          </span>
          <span className="rounded border border-slate-200 bg-white px-2 py-1 font-semibold text-slate-600">
            {snippet.evidence_type ?? "evidence"}
          </span>
        </div>
      </div>

      <pre className="max-h-80 overflow-auto bg-slate-950 p-3 text-xs leading-relaxed text-slate-100">
        <code>{snippet.snippet}</code>
      </pre>

      <div className="border-t border-line px-3 py-2 text-xs text-slate-600">
        {snippet.reason}
      </div>
    </article>
  );
}
