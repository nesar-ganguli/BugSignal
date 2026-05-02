import { ChangeEvent, FormEvent, useState } from "react";
import { FileUp, Loader2, Upload } from "lucide-react";

import { uploadTickets, UploadTicketsResponse } from "../api/client";

export function TicketUpload() {
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [result, setResult] = useState<UploadTicketsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const onFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    setResult(null);
    setError(null);
    setFile(event.target.files?.[0] ?? null);
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!file) return;

    setIsUploading(true);
    setError(null);
    setResult(null);

    try {
      setResult(await uploadTickets(file));
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Upload failed.");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-sm">
      <div className="flex items-center gap-3">
        <div className="grid h-10 w-10 place-items-center rounded border border-teal-100 bg-teal-50 text-signal">
          <FileUp size={20} aria-hidden="true" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-ink">Ticket Intake</h2>
          <p className="text-sm text-slate-600">CSV upload for support tickets.</p>
        </div>
      </div>

      <form className="mt-5 grid gap-4" onSubmit={onSubmit}>
        <label className="grid gap-2">
          <span className="text-sm font-medium text-slate-700">Ticket CSV</span>
          <input
            className="block w-full rounded border border-line bg-panel px-3 py-2 text-sm text-slate-700 file:mr-4 file:rounded file:border-0 file:bg-ink file:px-3 file:py-2 file:text-sm file:font-semibold file:text-white"
            type="file"
            accept=".csv,text/csv"
            onChange={onFileChange}
          />
        </label>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="text-sm text-slate-600">
            {file ? (
              <span>
                Selected <span className="font-medium text-ink">{file.name}</span>
              </span>
            ) : (
              <span>Expected columns: ticket_id, title, body, created_at.</span>
            )}
          </div>

          <button
            className="inline-flex items-center justify-center gap-2 rounded bg-ink px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-400"
            type="submit"
            disabled={!file || isUploading}
          >
            {isUploading ? <Loader2 className="animate-spin" size={16} aria-hidden="true" /> : <Upload size={16} aria-hidden="true" />}
            Upload
          </button>
        </div>
      </form>

      {result ? (
        <div className="mt-4 rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
          {result.message} Received {result.bytes_received.toLocaleString()} bytes.
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
