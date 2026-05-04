import { CodeSnippet } from "../api/client";
import { CodeSnippetViewer } from "./CodeSnippetViewer";

type EvidencePanelProps = {
  snippets: CodeSnippet[];
};

export function EvidencePanel({ snippets }: EvidencePanelProps) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-ink">Retrieved Code Evidence</h3>
      <div className="mt-3 grid gap-3">
        {snippets.length ? (
          snippets.map((snippet) => (
            <CodeSnippetViewer
              key={`${snippet.evidence_id ?? snippet.code_chunk_id}-${snippet.file_path}-${snippet.start_line}`}
              snippet={snippet}
            />
          ))
        ) : (
          <div className="rounded border border-line bg-panel px-3 py-4 text-sm text-slate-500">
            Retrieve code for this cluster after indexing a local repository.
          </div>
        )}
      </div>
    </div>
  );
}
