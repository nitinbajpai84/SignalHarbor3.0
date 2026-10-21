import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getConnectors, runConnector, type ConnectorRow } from "../api";
import V3Frame from "../Frame";
import "./build.css";

const KIND: Record<string, string> = { "file format": "File format", api: "API", inbox: "Inbox", sftp: "SFTP" };
const when = (at: string | null) => (at ? new Date(at).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "Never run");

/** The words on a card: connected, not connected yet (naming the settings, never their values), or the error. */
export function statusLine(c: ConnectorRow): { pill: string; text: string } {
  if (c.state === "needs_settings") return { pill: "needs", text: `Not connected yet: needs ${c.missing.join(", ")}` };
  if (c.state === "error") return { pill: "problem", text: c.errors[0] ?? "The last run failed" };
  return { pill: "done", text: "Connected" };
}

export default function Connections() {
  const [rows, setRows] = useState<ConnectorRow[] | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState("");
  const load = useCallback(() => { getConnectors().then((r) => { setRows(r.connectors); setErr(""); }).catch((e: Error) => setErr(e.message)); }, []);
  useEffect(() => { load(); }, [load]);
  const run = (id: string) => {
    setBusy(id); setErr("");
    runConnector(id).then((r) => setRows((rs) => (rs ?? []).map((x) => (x.id === id ? r : x)))).catch((e: Error) => setErr(e.message)).finally(() => setBusy(""));
  };
  return (
    <V3Frame back={<Link to="/v3/build" className="b3-back">&larr; Use cases</Link>}>
      <main className="b3-board b3">
        <div>
          <h1>Connections</h1>
          <p className="v3-mute">Where Harbor fetches files from. Whatever arrives lands in the drop folder and is read like any file you drop. Settings are held by the server and never shown here.</p>
        </div>
        {err && <p className="v3-err" role="alert">{err} <button onClick={load}>Try again</button></p>}
        {rows === null && !err && <p className="v3-mute" role="status">Loading connections...</p>}
        {rows !== null && rows.length === 0 && <p className="v3-mute">No connector is installed yet.</p>}
        <div className="g-grid">
          {(rows ?? []).map((c) => {
            const s = statusLine(c);
            return (
              <section key={c.id} className="b3-card g-conn" aria-label={c.label}>
                <div className="v3-row g-head"><b>{c.label}</b><span className="v3-pill info">{KIND[c.kind] ?? c.kind}</span></div>
                <p><span className={`v3-pill ${s.pill}`}>{s.text}</span></p>
                <p className="v3-mute">Last run: {when(c.last_run)}{c.last_run ? ` · ${c.files} file${c.files === 1 ? "" : "s"}` : ""}</p>
                {c.message && c.state === "connected" && <p className="v3-mute">{c.message}</p>}
                <div className="v3-row"><button className="go" disabled={busy === c.id} onClick={() => run(c.id)}>{busy === c.id ? "Running..." : "Run now"}</button></div>
              </section>
            );
          })}
        </div>
      </main>
    </V3Frame>
  );
}
