import { Fragment, useState } from "react";

import { useLoad } from "../../components/useLoad";
import { Pill } from "../../design";
import { getRun, getRuns, type RunRow } from "./api";

// RUN1: every run has an id, test or production, so operations and data governance can see what each run did. Click a row for its steps.
const when = (iso?: string) => (iso ? new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "");
const KIND: Record<string, string> = { pipeline: "Pipeline", intake_load: "File load", connector_pull: "Connector pull", recon: "Reconciliation" };

function Steps({ id }: { id: string }) {
  const r = useLoad(() => getRun(id), `run-${id}`);
  if (!r.data) return <p className="ds-muted">Reading the steps.</p>;
  if (!r.data.steps.length) return <p className="ds-muted">This run recorded no steps.</p>;
  return (
    <table className="ds-table" aria-label={`Steps of ${id}`}>
      <thead><tr><th>Step</th><th>Layer</th><th>Target</th><th>Rows in</th><th>Inserted</th><th>Rejected</th><th>Checks</th><th>Error</th></tr></thead>
      <tbody>{r.data.steps.map((s, i) => (
        <tr key={i}><td>{s.name}</td><td>{s.layer}</td><td>{s.target}</td><td>{s.rows_in ?? ""}</td><td>{s.inserted ?? ""}</td><td>{s.rejected ?? ""}</td>
          <td>{s.checks_passed} passed, {s.checks_failed} failed</td><td>{s.error ?? ""}</td></tr>))}</tbody>
    </table>
  );
}

export default function RunsSection() {
  const runs = useLoad(getRuns, "k3-runs");
  const [open, setOpen] = useState<string | null>(null);
  const rows: RunRow[] = runs.data?.runs ?? [];
  return (
    <section aria-label="Runs"><h2 style={{ fontSize: 17 }}>Runs</h2>
      {rows.length ? (
        <table className="ds-table">
          <thead><tr><th>Run</th><th>Kind</th><th>Mode</th><th>Trigger</th><th>Who</th><th>Started</th><th>Duration</th><th>Status</th></tr></thead>
          <tbody>{rows.map((r) => (
            <Fragment key={r.run_id}>
              <tr onClick={() => setOpen(open === r.run_id ? null : r.run_id)} style={{ cursor: "pointer" }}>
                <td><button type="button" className="n-btn" aria-expanded={open === r.run_id} onClick={(e) => { e.stopPropagation(); setOpen(open === r.run_id ? null : r.run_id); }}>{r.run_id}</button></td>
                <td>{KIND[r.kind] ?? r.kind}</td>
                <td><Pill tone={r.mode === "production" ? "signed" : "draft"}>{r.mode === "production" ? "PRODUCTION" : "TEST"}</Pill></td>
                <td>{r.trigger.replace("_", " ")}</td><td>{r.who}</td><td>{when(r.started)}</td><td>{r.seconds == null ? "" : `${r.seconds} s`}</td>
                <td>{r.status === "ok" ? <Pill tone="ok">ok</Pill> : r.status === "running" ? <Pill tone="open">running</Pill> : <Pill tone="failed">{r.status}</Pill>}</td>
              </tr>
              {open === r.run_id ? <tr><td colSpan={8}><Steps id={r.run_id} /></td></tr> : null}
            </Fragment>))}</tbody>
        </table>
      ) : <p className="ds-muted">{runs.state === "loading" ? "Reading the runs." : "No run has been recorded yet."}</p>}
    </section>
  );
}
