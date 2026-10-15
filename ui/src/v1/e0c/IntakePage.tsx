import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../../api/client";
import { PageFrame, Pill } from "../../design";
import { listFiles, loadMonth, STATE_NAMES, STATE_TONES, uploadFile, type IntakeFile, type MonthResult } from "./api";

// E0c3: /centre/data/intake. Files grouped by source; every state is a word, not only a colour.
export const plain = (err: unknown) => (err instanceof ApiError && err.message ? err.message : "That did not go through. Please try again.");
export const when = (at: string | null) => (at ? new Date(at).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "Never");

export default function IntakePage() {
  const [files, setFiles] = useState<IntakeFile[] | null>(null);
  const [canUpload, setCanUpload] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    listFiles().then((r) => { setFiles(r.files); setCanUpload(r.can_upload !== false); setError(""); }).catch((e) => { setFiles([]); setError(plain(e)); });
  }, []);
  useEffect(() => { load(); }, [load]);
  const [receivedOn, setReceivedOn] = useState("");  // blank: received now
  const send = async (picked: FileList | null) => {  // one file or a month of them; each goes through the same file page
    setError("");
    for (const file of Array.from(picked ?? [])) {
      try { await uploadFile(file, receivedOn); } catch (e) { setError(`${file.name}: ${plain(e)}`); }
    }
    load();
  };
  const [month, setMonth] = useState<MonthResult | null>(null);
  const sendMonth = async (picked: FileList | null) => {
    setError(""); setMonth(null);
    try { setMonth(await loadMonth(Array.from(picked ?? []))); load(); } catch (e) { setError(plain(e)); }
  };
  const groups = new Map<string, IntakeFile[]>();
  (files ?? []).forEach((x) => { const k = x.source_label || x.source_code; groups.set(k, [...(groups.get(k) ?? []), x]); });

  return (
    <PageFrame title="Data intake" subline="Drop files in the inbox folder or upload here.">
      {canUpload ? <p><label>Received on (leave blank for today) <input className="ds-input" type="date" value={receivedOn} onChange={(e) => setReceivedOn(e.target.value)} /></label></p> : null}
      {canUpload ? <p><label>Upload files (one, or a month at once) <input type="file" multiple accept=".xlsx,.xlsm,.csv" onChange={(e) => void send(e.target.files)} /></label></p> : null}
      {canUpload ? <p><label>Load a month of files (daily CSVs, the administrator workbook, bank files) <input type="file" multiple accept=".xlsx,.xlsm,.csv" onChange={(e) => void sendMonth(e.target.files)} /></label></p> : null}
      {month ? (
        <ul aria-label="Month result">{Object.entries(month.files).map(([n, r]) => (
          <li key={n}>{r.file_id ? <Link className="ds-link" to={`/centre/data/intake/${r.file_id}`}>{n}</Link> : n}: {r.message || r.state}</li>))}</ul>
      ) : null}
      {error ? <p role="alert">{error}</p> : null}
      {files === null ? <p className="ds-muted" role="status">Loading the files.</p> : files.length === 0 && !error ? <p className="ds-muted">No files yet. Drop one in the inbox folder or upload it here.</p> : null}
      {[...groups].map(([source, rows]) => (
        <section key={source} aria-label={source}>
          <h2>{source}</h2>
          <table className="ds-table" style={{ width: "100%" }}>
            <thead><tr><th>File</th><th>State</th><th>Owner</th><th>Received</th><th>Last load</th></tr></thead>
            <tbody>{rows.map((r) => (
              <tr key={r.id}>
                <td><Link className="ds-link" to={`/centre/data/intake/${r.id}`}>{r.name}</Link></td>
                <td><Pill tone={STATE_TONES[r.state]}>{STATE_NAMES[r.state]}</Pill></td>
                <td>{r.owner ?? "No owner yet"}</td><td>{when(r.received_at)}</td><td>{when(r.last_load_at)}</td>
              </tr>))}</tbody>
          </table>
        </section>
      ))}
    </PageFrame>
  );
}
