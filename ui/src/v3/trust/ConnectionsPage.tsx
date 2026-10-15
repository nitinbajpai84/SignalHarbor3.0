import { useState } from "react";

import { getConnections, type Connection } from "../api";
import { FORMS, SCHEDULES, saveConnector, testConnector, connectorId, type AddKind } from "./b/connectorForm";
import { TrustPage, useLoad } from "./b/Shell";

const KIND_LABEL: Record<Connection["kind"], string> = { folder: "Drop folder", mailbox: "Mailbox", sftp: "SFTP", http: "Shared drive", database: "Database", api: "REST API" };
const ADD: [AddKind | "folder" | "database" | "api", string, boolean][] = [
  ["folder", "Folder", false], ["mailbox", "Mailbox", true], ["sftp", "SFTP", true], ["http", "Shared drive", true], ["database", "Database", false], ["api", "REST API", false],
];
/** Reading fine is done, a failed pull is a problem, a source not built yet is just information. */
const PILL: Record<Connection["state"], string> = { ok: "v3-pill done", failing: "v3-pill problem", coming: "v3-pill info" };

function AddForm({ kind, onSaved }: { kind: AddKind; onSaved: () => void }) {
  const f = FORMS[kind];
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [v, setV] = useState<Record<string, string>>({});
  const [pattern, setPattern] = useState("*.xlsx;*.xlsm;*.csv");
  const [schedule, setSchedule] = useState("daily");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const ready = connectorId(name) !== "" && code.trim() !== "";

  const run = async (andTest: boolean) => {
    setBusy(true); setMsg("");
    try {
      const id = await saveConnector(kind, name, v, pattern, schedule, code);
      if (andTest) { const r = await testConnector(id); setMsg(r.ok ? (r.message ?? "Reached the source") : (r.message ?? "Could not reach the source")); }
      else { setMsg("Saved"); }
      setV({});  // secrets are write-only: cleared once sent, never shown again
      onSaved();
    } catch (e) { setMsg((e as Error).message || "Could not save"); }
    finally { setBusy(false); }
  };
  const field = (key: string, label: string, value: string, set: (s: string) => void, secret?: boolean, hint?: string) => (
    <label key={key} style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13, color: "var(--mute)" }}>
      {label}
      <input value={value} onChange={(e) => set(e.target.value)} type={secret ? "password" : "text"} autoComplete="off" placeholder={hint} />
      {secret && <small>Held by the server, never shown again</small>}
    </label>
  );
  return (
    <form className="v3-card" onSubmit={(e) => { e.preventDefault(); void run(false); }} aria-label={`New ${f.label} connection`}>
      <h2 style={{ fontSize: 18 }}>New {f.label} connection</h2>
      <p className="v3-mute">Read-only. Harbor pulls the files on the schedule you set.</p>
      {field("name", "Name", name, setName)}
      {field("code", "Source code (what these files are)", code, setCode)}
      {f.fields.map((x) => field(x.key, x.label, v[x.key] ?? "", (s) => setV({ ...v, [x.key]: s }), x.secret, x.hint))}
      {field("pattern", "File pattern", pattern, setPattern)}
      <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13, color: "var(--mute)" }}>Schedule
        <select value={schedule} onChange={(e) => setSchedule(e.target.value)}>{SCHEDULES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
      </label>
      <div className="v3-row">
        <button type="button" disabled={!ready || busy} onClick={() => void run(true)}>Test the connection</button>
        <button type="submit" className="go" disabled={!ready || busy}>Save connection</button>
      </div>
      {msg && <p className="v3-mute" role="status">{msg}</p>}
    </form>
  );
}

export default function ConnectionsPage() {
  const s = useLoad(getConnections, "connections");
  const [adding, setAdding] = useState<AddKind | null>(null);
  const list: Connection[] = s.data?.connections ?? [];
  return (
    <TrustPage kicker="Trust › Connections · for Anita and Leo" title="Where the office's data comes from, every month" state={s}
      empty={false}>
      <section><h2>Connected sources</h2>
        <p className="v3-mute">Each one pulls on its own schedule. Nobody uploads anything.</p>
        {!list.length && <p className="v3-mute">No sources are connected yet. Add one below.</p>}
        <div style={{ display: "grid", gap: 12, marginTop: 10 }}>
          {list.map((c) => (
            <article key={c.id} className="v3-card" style={c.state === "failing" ? { borderLeft: "4px solid var(--problem)" } : undefined}>
              <div className="v3-row"><b style={{ flex: 1 }}>{c.name || KIND_LABEL[c.kind]}</b>
                <span className={PILL[c.state]}>{c.state === "coming" ? "Coming" : c.state === "ok" ? "Reading" : "Failing"}</span></div>
              <span className="v3-mute">{KIND_LABEL[c.kind]} · {c.target}</span>
              <span className="v3-mute">Schedule {c.schedule} · Last pull {c.last_pull || "Not available yet"}</span>
              {c.state === "failing" && <p className="v3-err">This source could not be read on its last pull. Check its sign-in and test it again.</p>}
            </article>))}
        </div>
      </section>
      <section><h2>Add a connection</h2>
        <p className="v3-mute">Pick where the files already land. Harbor does the rest.</p>
        <div className="v3-row" role="group" aria-label="Kind of connection" style={{ margin: "10px 0" }}>
          {ADD.map(([k, label, on]) => (
            <button key={k} disabled={!on} aria-pressed={adding === k} className={adding === k ? "go" : ""}
              title={on ? undefined : k === "folder" ? "The drop folder is already set up" : "Coming"} onClick={() => on && setAdding(k as AddKind)}>
              {label}{on ? "" : k === "folder" ? "" : " (coming)"}
            </button>))}
        </div>
        {adding && <AddForm key={adding} kind={adding} onSaved={s.retry} />}
      </section>
    </TrustPage>
  );
}
