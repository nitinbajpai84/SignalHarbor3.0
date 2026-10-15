import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../../api/client";
import { PageFrame, Pill } from "../../design";
import { FIELDS, KIND_NAMES, listConnectors, removeConnector, runOp, saveConnector, type Connector, type Kind, type Listing, type OpResult } from "./api";

// C5: Settings, Connectors. Where files come from by themselves. Credentials are named, never typed: "the variable MAIL_PASS on the server".
const plain = (err: unknown) => (err instanceof ApiError && err.message ? err.message : "That did not go through. Please try again.");
const when = (at: string | null | undefined) => (at ? new Date(at).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "Never");
const blank = { id: "", kind: "imap" as Kind, host: "", schedule: "daily", source_code: "", file_pattern: "*.xlsx;*.xlsm;*.csv", credentials: {} as Record<string, string>, params: {} as Record<string, string> };

function State({ c }: { c: Connector }) {
  const h = c.health;
  if (!h || h.status === "never") return <Pill tone="open">Not run yet</Pill>;
  if (h.failed) return <Pill tone="failed">Failed</Pill>;
  return h.late ? <Pill tone="late">Late</Pill> : <Pill tone="signed">On time</Pill>;
}

export default function ConnectorsPage() {
  const [data, setData] = useState<Listing | null>(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState(blank);
  const [result, setResult] = useState<{ id: string; op: string; r: OpResult } | null>(null);
  const load = useCallback(() => { listConnectors().then((r) => { setData(r); setError(""); }).catch((e) => { setData({ connectors: [], kinds: [], schedules: [], egress_note: "" }); setError(plain(e)); }); }, []);
  useEffect(() => { load(); }, [load]);
  const f = FIELDS[form.kind];
  const set = (k: "credentials" | "params", name: string, v: string) => setForm({ ...form, [k]: { ...form[k], [name]: v } });
  const save = async () => {
    const { id, ...body } = form;
    try { await saveConnector(id, body); setForm(blank); load(); } catch (e) { setError(plain(e)); }
  };
  const run = async (id: string, op: "test" | "dry-run" | "fetch") => {
    try { setResult({ id, op, r: await runOp(id, op) }); load(); } catch (e) { setError(plain(e)); }
  };
  const say = (r: OpResult) => r.would_arrive ? (r.ok ? `${r.would_arrive.length} file(s) would arrive: ${r.would_arrive.map((w) => w.name).join(", ") || "none"}.` : r.message)
    : r.landed !== undefined ? (r.status === "ok" ? `${r.landed} new file(s) landed, ${r.duplicates ?? 0} already here.` : r.error?.message) : r.message;

  return (
    <PageFrame title="Connectors" subline="Statements arrive by themselves: mailbox, SFTP or a cloud folder. They land in data intake like any file.">
      {error ? <p role="alert">{error}</p> : null}
      <p><Link className="ds-link" to="/centre/build/connect-api">Connect an API</Link>: outside rates, yields, index proxies and news on a schedule.</p>
      {data?.egress_note ? <p className="ds-muted">{data.egress_note}</p> : null}
      {data === null ? <p className="ds-muted" role="status">Loading the connectors.</p> : data.connectors.length === 0 && !error ? <p className="ds-muted">No connectors yet. Add one below.</p> : null}
      {result ? <p role="status">{result.id}: {say(result.r)}</p> : null}
      {data && data.connectors.length > 0 ? (
        <table className="ds-table" style={{ width: "100%" }}>
          <thead><tr><th>Connector</th><th>Source</th><th>State</th><th>Last run</th><th>Files landed</th><th /></tr></thead>
          <tbody>{data.connectors.map((c) => (
            <tr key={c.id}>
              <td>{c.id}<br /><span className="ds-muted">{KIND_NAMES[c.kind]}, {c.schedule}</span></td>
              <td>{c.source_code}</td>
              <td><State c={c} />{c.health?.error ? <div className="ds-muted">{c.health.error.message}</div> : null}</td>
              <td>{when(c.health?.last_run)}</td><td>{c.health?.files_landed ?? 0}</td>
              <td>
                <button className="ds-btn" onClick={() => void run(c.id, "test")}>Test connection</button>{" "}
                <button className="ds-btn" onClick={() => void run(c.id, "dry-run")}>Dry run</button>{" "}
                <button className="ds-btn" onClick={() => void run(c.id, "fetch")}>Fetch now</button>{" "}
                <button className="ds-btn" onClick={() => void removeConnector(c.id).then(load).catch((e) => setError(plain(e)))}>Remove</button>
              </td>
            </tr>))}</tbody>
        </table>) : null}

      <h2>Add a connector</h2>
      <form onSubmit={(e) => { e.preventDefault(); void save(); }} style={{ display: "grid", gap: 8, maxWidth: 520 }}>
        <label>Name <input value={form.id} onChange={(e) => setForm({ ...form, id: e.target.value })} /></label>
        <label>Kind <select value={form.kind} onChange={(e) => setForm({ ...blank, id: form.id, kind: e.target.value as Kind })}>
          {(data?.kinds ?? ["imap", "sftp", "graph"]).map((k) => <option key={k} value={k}>{KIND_NAMES[k as Kind]}</option>)}</select></label>
        {f.host ? <label>Host <input value={form.host} onChange={(e) => setForm({ ...form, host: e.target.value })} placeholder="mail.example.com" /></label> : null}
        {f.params.map((p) => <label key={p}>{p.replace("_", " ")} <input value={form.params[p] ?? ""} onChange={(e) => set("params", p, e.target.value)} /></label>)}
        {f.creds.map((c) => <label key={c}>Variable holding the {c.replace("_", " ")} <input value={form.credentials[c] ?? ""} onChange={(e) => set("credentials", c, e.target.value.toUpperCase())} placeholder="CONN_MAIL_PASSWORD" /></label>)}
        <label>Source code <input value={form.source_code} onChange={(e) => setForm({ ...form, source_code: e.target.value })} placeholder="custodian" /></label>
        <label>Schedule <select value={form.schedule} onChange={(e) => setForm({ ...form, schedule: e.target.value })}>
          {(data?.schedules ?? ["manual", "hourly", "daily", "weekly"]).map((s) => <option key={s}>{s}</option>)}</select></label>
        <label>File names <input value={form.file_pattern} onChange={(e) => setForm({ ...form, file_pattern: e.target.value })} /></label>
        <p className="ds-muted">Passwords are never typed here. Name the variable the server holds them in; it must start CONN_.</p>
        <button className="ds-btn" type="submit">Save connector</button>
      </form>
    </PageFrame>
  );
}
