import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { Button, Chip, PageFrame, Pill } from "../../design";
import { getPeople, listTickets, raiseTicket, STATE_NAMES, type Filters, type TicketRow } from "./api";

// T2: /centre/tickets. The list defaults to the tickets assigned to the signed-in person; every filter is a visible control.
const plain = (err: unknown) => (err instanceof ApiError && err.message ? err.message : "That did not go through. Please try again.");
const STAGES: [string, string][] = [["", "Any stage"], ["intent", "Intent centre"], ["design", "Build centre (design)"], ["build", "Build centre"], ["ops", "Ops"], ["consume", "Consume centre"]];
const STATES: [string, string][] = [["active", "Open, in progress or waiting"], ["", "Any state"], ["resolved", "Resolved"], ["closed", "Closed"]];
const day = (at: string) => new Date(at).toLocaleDateString("en-GB", { day: "numeric", month: "short" });

export default function TicketsPage() {
  const [params, setParams] = useSearchParams();
  const f: Filters = {
    project: params.get("project") ?? "", stage: params.get("stage") ?? "", assignee: params.get("assignee") ?? "me",
    raised_by: params.get("raised_by") ?? "", state: params.get("state") ?? "active", priority: params.get("priority") ?? "",
  };
  const [rows, setRows] = useState<TicketRow[] | null>(null);
  const [error, setError] = useState("");
  const [adding, setAdding] = useState(false);
  const key = JSON.stringify(f);

  const load = useCallback(() => {
    setError("");
    listTickets(JSON.parse(key) as Filters).then((r) => setRows(r.tickets)).catch((e) => { setRows([]); setError(plain(e)); });
  }, [key]);
  useEffect(() => { load(); }, [load]);
  const set = (k: keyof Filters, v: string) => { const p = new URLSearchParams(params); p.set(k, v); setParams(p, { replace: true }); };

  return (
    <PageFrame title="Tickets" subline="Work that agents and people hand each other, with a number and a record of every step."
      actions={<Button variant="primary" onClick={() => setAdding(!adding)}>Raise a ticket</Button>}>
      {adding ? <Raise done={() => { setAdding(false); load(); }} project={f.project ?? ""} /> : null}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", margin: "8px 0 16px" }}>
        <label>Assigned to <select className="ds-input" value={f.assignee === "me" ? "me" : "any"} onChange={(e) => set("assignee", e.target.value === "me" ? "me" : "")}>
          <option value="me">Me</option><option value="any">Anyone</option></select></label>
        <label>Raised by <select className="ds-input" value={f.raised_by === "me" ? "me" : ""} onChange={(e) => set("raised_by", e.target.value)}>
          <option value="">Anyone</option><option value="me">Me</option></select></label>
        <label>Stage <select className="ds-input" value={f.stage} onChange={(e) => set("stage", e.target.value)}>
          {STAGES.map(([v, n]) => <option key={v} value={v}>{n}</option>)}</select></label>
        <label>State <select className="ds-input" value={f.state} onChange={(e) => set("state", e.target.value)}>
          {STATES.map(([v, n]) => <option key={v} value={v}>{n}</option>)}</select></label>
        <label>Priority <select className="ds-input" value={f.priority} onChange={(e) => set("priority", e.target.value)}>
          <option value="">Any</option><option value="high">High</option><option value="normal">Normal</option></select></label>
        {f.project ? <Chip tone="active" onClick={() => set("project", "")}>{`Project ${f.project} (clear)`}</Chip> : null}
      </div>
      {error ? <p role="alert">{error}</p> : null}
      {rows === null ? <p className="ds-muted" role="status">Loading the tickets.</p> : rows.length === 0 && !error ? <p className="ds-muted">No tickets match. Widen a filter, or raise one.</p> : (
        <table className="ds-table" style={{ width: "100%" }}>
          <thead><tr><th>Number</th><th>Title</th><th>Project</th><th>Stage</th><th>Assigned to</th><th>Last change</th><th>Age</th></tr></thead>
          <tbody>{rows.map((r) => (
            <tr key={r.id}>
              <td><Link className="ds-link" to={`/centre/tickets/${r.id}`}>{r.id}</Link></td>
              <td>{r.title} {r.priority === "high" ? <Pill tone="late">High</Pill> : null} {r.state !== "open" ? <Pill tone={r.state === "resolved" || r.state === "closed" ? "signed" : "draft"}>{STATE_NAMES[r.state]}</Pill> : null}</td>
              <td>{r.project_title ?? "None"}</td><td>{r.stage_name}</td><td>{r.assigned_name}</td>
              <td title={r.last_change.text}>{day(r.last_change.at)}</td><td>{r.age_days === 0 ? "Today" : `${r.age_days} d`}</td>
            </tr>))}</tbody>
        </table>
      )}
    </PageFrame>
  );
}

export function Raise({ done, project }: { done: () => void; project: string }) {
  const [title, setTitle] = useState("");
  const [to, setTo] = useState("");
  const [stage, setStage] = useState("build");
  const [names, setNames] = useState<string[]>([]);
  const [error, setError] = useState("");
  useEffect(() => { getPeople().then((p) => setNames(p.people)).catch(() => undefined); }, []);
  async function send() {
    setError("");
    try { await raiseTicket({ title: title.trim(), project: project || undefined, stage, assigned_to: to.trim() || undefined }); done(); } catch (e) { setError(plain(e)); }
  }
  return (
    <form onSubmit={(e) => { e.preventDefault(); if (title.trim()) void send(); }} style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
      <input className="ds-input" aria-label="What is the ticket about" placeholder="What needs doing?" value={title} onChange={(e) => setTitle(e.target.value)} style={{ flex: "1 1 260px" }} />
      <input className="ds-input" aria-label="Who it goes to" placeholder="Who it goes to (default: me)" list="t2-people" value={to} onChange={(e) => setTo(e.target.value)} />
      <datalist id="t2-people">{names.map((n) => <option key={n} value={n} />)}</datalist>
      <select className="ds-input" aria-label="Stage" value={stage} onChange={(e) => setStage(e.target.value)}>{STAGES.slice(1).map(([v, n]) => <option key={v} value={v}>{n}</option>)}</select>
      <Button variant="primary" type="submit" disabled={!title.trim()}>Raise it</Button>
      {error ? <p role="alert">{error}</p> : null}
    </form>
  );
}
