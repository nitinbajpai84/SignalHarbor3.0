import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Button, Pill, when } from "../../design";
import PlanDiagram from "../b6diagram/PlanDiagram";
import { airflowHref, STATE_NAMES, type Plan, type Run, type Schedule, type Table } from "./api";

// B1: the six documents of the stepper. Each takes the plan and says its state in words.
const fileName = (f: string | { name: string; state: string }) => (typeof f === "string" ? { name: f, state: "Landed" } : f);
const Empty = ({ children }: { children: string }) => <p className="ds-muted">{children}</p>;

export function Sources({ plan, pid }: { plan: Plan; pid: string }) {
  return (
    <>
      {plan.sources.length === 0 ? <Empty>The intent of work names no sources yet.</Empty> : null}
      {plan.sources.map((s) => (
        <section key={s.code} aria-label={s.code} style={{ marginBottom: 12 }}>
          <h3 style={{ margin: "0 0 4px", fontSize: 15 }}>{s.code} <Pill tone="open">{s.kind === "structured" ? "Structured" : "Unstructured"}</Pill></h3>
          <p className="ds-muted" style={{ margin: 0 }}>Owner: {s.owner || "Not set"}</p>
          {s.files.length === 0 ? <p style={{ margin: 0 }}>No files landed yet.</p> : (
            <ul style={{ margin: 0 }}>{s.files.map(fileName).map((f) => <li key={f.name}>{f.name}: {f.state}</li>)}</ul>)}
        </section>))}
      <Link className="ds-btn" to={`/centre/data/intake?project=${encodeURIComponent(pid)}`}>Add files</Link>
    </>
  );
}

export function ModelChanges({ plan }: { plan: Plan }) {
  const d = plan.model_diff;
  if (!plan.model_changes || !d || (!d.tables_added.length && !d.columns_added.length)) return <Empty>No change to the data model. Nothing is removed.</Empty>;
  return (
    <>
      <p style={{ marginTop: 0 }}>Proposal {plan.model_changes}. Only additions; nothing is removed.</p>
      {d.tables_added.length ? <><h3 style={{ fontSize: 15 }}>Tables added</h3><ul>{d.tables_added.map((t) => <li key={t.table}>{t.table}: {t.columns.join(", ")}</li>)}</ul></> : null}
      {d.columns_added.length ? <><h3 style={{ fontSize: 15 }}>Columns added</h3><ul>{d.columns_added.map((c) => <li key={`${c.table}.${c.column}`}>{c.table}.{c.column}{c.type ? ` (${c.type})` : ""}</li>)}</ul></> : null}
    </>
  );
}

const LAYERS = ["bronze", "silver", "gold"] as const;
function TableView({ t }: { t: Table }) {
  return (
    <details>
      <summary>{t.name}{t.is_new ? " (new)" : ""}</summary>
      <p style={{ margin: "4px 0" }}>{t.purpose}</p>
      <table className="ds-table"><thead><tr><th>Column</th><th>Type</th><th>From</th></tr></thead>
        <tbody>{t.columns.map((c) => <tr key={c.name}><td>{c.name}</td><td>{c.type}</td><td>{c.from ?? ""}</td></tr>)}</tbody></table>
      <details><summary>How it is calculated</summary>
        <pre aria-label={`SQL of ${t.name}`} style={{ overflow: "auto", whiteSpace: "pre-wrap" }}><code>{t.sql}</code></pre>
      </details>
    </details>
  );
}
export function Tables({ plan }: { plan: Plan }) {
  if (!plan.tables.length) return <Empty>Span has not proposed any tables yet. Tell Span what you need in the conversation.</Empty>;
  return <>{LAYERS.map((l) => {
    const ts = plan.tables.filter((t) => t.layer === l);
    return ts.length ? <section key={l} aria-label={l}><h3 style={{ fontSize: 15, textTransform: "capitalize" }}>{l}</h3>{ts.map((t) => <TableView key={t.name} t={t} />)}</section> : null;
  })}</>;
}

export const Diagram = ({ pid }: { pid: string }) => <PlanDiagram projectId={pid} />;

export function Approval({ plan, busy, onApprove, onSendBack, onPropose }: { plan: Plan; busy: boolean; onApprove: (note: string) => void; onSendBack: (reason: string) => void; onPropose: () => void }) {
  const [choice, setChoice] = useState<"" | "approve" | "back">("");   // V6 (design C2): choose one, say why when sending back, then act
  const [reason, setReason] = useState("");
  const can = plan.can ?? {};
  return (
    <>
      <p style={{ marginTop: 0 }}>State: <Pill tone={plan.state === "rejected" ? "failed" : plan.state === "draft" || plan.state === "proposed" ? "draft" : "signed"}>{STATE_NAMES[plan.state]}</Pill> Version {plan.version}</p>
      <p>Proposed by: {plan.proposed_by ?? "Nobody yet"}</p>
      {plan.approved_by ? <p>Approved by {plan.approved_by}{plan.approved_at ? `, ${when(plan.approved_at)}` : ""}. This also approved the model change.</p> : null}
      {plan.state === "rejected" && plan.reason ? <p>Sent back: {plan.reason}</p> : null}
      {plan.state === "draft" || plan.state === "rejected" ? <Button disabled={busy || !plan.tables.length} onClick={onPropose}>Send to the head of data</Button> : null}
      {can.approve || can.reject ? (
        <div style={{ display: "grid", gap: 8, maxWidth: 460 }}>
          <fieldset style={{ border: 0, padding: 0, margin: 0, display: "grid", gap: 6 }}>
            <legend className="ds-footnote" style={{ padding: 0, marginBottom: 4 }}>Your decision: choose one</legend>
            <label style={{ display: "flex", gap: 8, alignItems: "center" }}><input type="radio" name="b6-decision" disabled={!can.approve} checked={choice === "approve"} onChange={() => setChoice("approve")} />Approve the plan, the builder may try it on a copy</label>
            <label style={{ display: "flex", gap: 8, alignItems: "center" }}><input type="radio" name="b6-decision" disabled={!can.reject} checked={choice === "back"} onChange={() => setChoice("back")} />Send back to the builder and Span with a note</label>
          </fieldset>
          <label>{choice === "back" ? "Reason for sending back (needed)" : "Note for the builder (optional)"}
            <textarea placeholder={choice === "back" ? "What should Span change?" : "For example: keep the raw copies shared with the investment report"} value={reason} onChange={(e) => setReason(e.target.value)} /></label>
          <p className="ds-muted" style={{ margin: 0 }}>Approving also approves the new tables and columns in document 2, and lets the builder run the plan on a copy. Nothing touches live reports yet.</p>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <Button disabled={busy || choice !== "back" || !can.reject || !reason.trim()} onClick={() => onSendBack(reason.trim())}>Send back</Button>
            <Button variant="primary" disabled={busy || choice !== "approve" || !can.approve} onClick={() => onApprove(reason.trim())}>Approve the plan</Button>
          </div>
        </div>
      ) : plan.state === "proposed" ? <p className="ds-muted">Only the head of data can approve this plan.</p> : null}
    </>
  );
}

const FREQ: [Schedule["freq"], string][] = [["daily", "Every day"], ["weekly", "Every week"], ["monthly", "Every month"], ["on_arrival", "When a new file arrives"]];
const ROOMS: [string, string][] = [["", "Design with Span"], ["/scan", "Scan"], ["/mapping", "Mapping sheet"], ["/engineer", "Pipeline room"], ["/runs", "Run log"], ["/deviations", "Approval requests"]];
/** The Build rooms for one intent of work. Keeps the old rooms one click from the list and the project. */
export function Rooms({ iid }: { iid?: string | null }) {
  if (!iid) return null;
  return <>{ROOMS.map(([p, n], i) => <span key={p}>{i ? " · " : ""}<Link className="ds-link" to={`/centre/build/${encodeURIComponent(iid)}${p}`}>{n}</Link></span>)}</>;
}

/** NU-23: the newest run of this plan version, when it failed (and the first table that broke). A later clean run clears it. */
export function lastFailed(plan: Plan, runs: Run[]): { table: string | null } | null {
  const r = runs.find((x) => x.plan_version === plan.version && x.status !== "running");
  return r && r.status === "failed" ? { table: r.steps.find((x) => x.status === "failed")?.table ?? null } : null;
}

const RUN_PAGE = 5;

export function Pipeline({ plan, runs, busy, pid, onRun, onSchedule }: { plan: Plan; runs: Run[]; busy: boolean; pid: string; onRun: (m: "sandbox" | "live") => void; onSchedule: (s: Schedule) => void }) {
  const [s, setS] = useState<Schedule>(plan.schedule);
  const [page, setPage] = useState(0);  // the run log shows five runs at a time, newest first
  const { freq, at, day } = plan.schedule;
  useEffect(() => setS({ freq, at, day }), [freq, at, day]);  // by value: the plan is fetched again while a run is polled, and that must not wipe an unsaved choice (UC10A-005)
  const can = plan.can ?? {};
  const approved = plan.state === "approved" || plan.state === "built" || plan.state === "live";
  const broken = lastFailed(plan, runs);
  return (
    <>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <Button disabled={busy || !can.run_sandbox} onClick={() => onRun("sandbox")}>Try it on a copy</Button>
        <Button variant="primary" disabled={busy || !can.go_live || !approved || !!broken} onClick={() => onRun("live")}>Go live</Button>
      </div>
      {approved && broken ? <p className="ds-muted" role="status">Going live waits for a clean run: the last run of this plan failed{broken.table ? ` at ${broken.table}` : ""}. Fix it, then try it on a copy.</p> : null}
      <details style={{ margin: "8px 0" }}><summary>For engineers</summary>
        <a className="ds-btn" href={airflowHref(pid)} download>Download the Airflow file</a>
      </details>
      {!approved ? <p className="ds-muted">Going live waits for the head of data to approve the plan.</p> : null}
      <fieldset style={{ margin: "12px 0" }}><legend>How often</legend>
        <label>Repeat <select value={s.freq} onChange={(e) => setS({ ...s, freq: e.target.value as Schedule["freq"] })}>{FREQ.map(([k, n]) => <option key={k} value={k}>{n}</option>)}</select></label>{" "}
        {s.freq !== "on_arrival" ? <label>At <input type="time" value={s.at} onChange={(e) => setS({ ...s, at: e.target.value })} /></label> : null}{" "}
        <Button disabled={busy || !can.schedule} onClick={() => onSchedule(s)}>Save the schedule</Button>
      </fieldset>
      <h3 style={{ fontSize: 15 }}>Last runs</h3>
      {plan.intent_id ? <p><Link className="ds-link" to={`/centre/build/${encodeURIComponent(plan.intent_id)}/runs`}>Full run log</Link></p> : null}
      {runs.length > RUN_PAGE ? (
        <p className="ds-muted" role="group" aria-label="Run log pages">Runs {page * RUN_PAGE + 1} to {Math.min(runs.length, (page + 1) * RUN_PAGE)} of {runs.length}{" "}
          <Button disabled={page === 0} onClick={() => setPage(page - 1)}>Newer runs</Button>{" "}
          <Button disabled={(page + 1) * RUN_PAGE >= runs.length} onClick={() => setPage(page + 1)}>Older runs</Button></p>) : null}
      {runs.length === 0 ? <Empty>No runs yet.</Empty> : runs.slice(page * RUN_PAGE, (page + 1) * RUN_PAGE).map((r) => (
        <details key={r.run_id}>
          <summary>{r.mode === "live" ? "Live" : "Sandbox"} run, plan version {r.plan_version}: {r.status}</summary>
          <table className="ds-table"><thead><tr><th>Table</th><th>Rows</th><th>Status</th></tr></thead>
            <tbody>{r.steps.map((x) => <tr key={x.table}><td>{x.table}</td><td>{x.rows}</td><td>{x.status}{x.error ? `: ${x.error}` : ""}</td></tr>)}</tbody></table>
        </details>))}
    </>
  );
}
