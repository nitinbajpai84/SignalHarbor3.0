import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { Button, day, PageFrame, Pill } from "../../design";
import { approveAlias, confirmField, correctField, getDocument, type DocDetail, type DocVersion, type Field } from "./api";

// E2d: the original and the amended statement side by side, what was read from them, and the person's say (Confirm reads / Not right).
const plain = (err: unknown) => (err instanceof ApiError && err.message ? err.message : "That did not go through. Please try again.");
// A read value that is a bare date reads like every other date on screen ("30 Sep 2026").
const shown = (v: string | null) => (v === null ? "Not in this statement" : /^\d{4}-\d{2}-\d{2}$/.test(v) ? day(v, v) : v);
const STATE: Record<Field["state"], string> = { waiting: "Waiting for review", confirmed: "Confirmed", corrected: "Corrected", rejected: "Rejected" };

function Statement({ v }: { v: DocVersion }) {
  const ref = v.page ? `Page ${v.page}${v.line ? `, line ${v.line}` : ""}` : "Page not found";
  return (
    <section aria-label={`${v.label} statement`} style={{ flex: "1 1 320px" }}>
      <h2><Pill tone={v.label === "Current" ? "signed" : "open"}>{v.label}</Pill> received {day(v.received_at, v.received_at)}</h2>
      <p className="ds-muted">Labelled {v.status_label} by the manager.</p>
      <p><mark>{v.value_text}</mark></p>
      {v.excerpt ? <blockquote>{v.excerpt}</blockquote> : null}
      <p><a className="ds-link" href={v.page ? `${v.file_url}#page=${v.page}` : v.file_url} target="_blank" rel="noreferrer">{ref}: open the original file</a></p>
    </section>
  );
}

function FieldRow({ f, canReview, onDone, onError }: { f: Field; canReview: boolean; onDone: (f: Field) => void; onError: (m: string) => void }) {
  const [fixing, setFixing] = useState(false);
  const [value, setValue] = useState("");
  const run = async (fn: () => Promise<Field>) => { onError(""); try { onDone(await fn()); setFixing(false); } catch (e) { onError(plain(e)); } };
  return (
    <tr>
      <td>{f.field}</td><td>{shown(f.original)}</td><td>{shown(f.amended)}</td>
      <td>{Math.round(f.confidence * 100)}% sure</td>
      <td>{STATE[f.state]}</td>
      <td>{canReview && f.state === "waiting" ? (fixing ? (
        <span style={{ display: "inline-flex", gap: 8 }}>
          <input className="ds-input" aria-label={`Correct value for ${f.field}`} placeholder="The right value" value={value} onChange={(e) => setValue(e.target.value)} />
          <Button variant="primary" disabled={!value.trim()} onClick={() => run(() => correctField(f.id, value.trim()))}>Save the right value</Button>
        </span>) : (
        <span style={{ display: "inline-flex", gap: 8 }}>
          <Button variant="primary" onClick={() => run(() => confirmField(f.id))}>Confirm reads</Button>
          <Button onClick={() => setFixing(true)}>Not right</Button>
        </span>)) : null}</td>
    </tr>
  );
}

export default function EvidencePage() {
  const { documentId = "" } = useParams();
  const [d, setD] = useState<DocDetail | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(() => getDocument(documentId).then(setD).catch((e) => setError(plain(e))), [documentId]);
  useEffect(() => { void load(); }, [load]);

  if (!d) return <PageFrame title="Evidence">{error ? <p role="alert">{error}</p> : <p className="ds-muted" role="status">Loading the statement.</p>}</PageFrame>;
  const done = (n: Field) => setD({ ...d, fields: d.fields.map((x) => (x.id === n.id ? n : x)) });
  const m = d.match;
  return (
    <PageFrame title={`${d.instrument_name} · valued ${day(d.valuation_date, d.valuation_date)}`} crumbs={<Link className="ds-link" to="/centre/evidence">All statements</Link>}>
      {error ? <p role="alert">{error}</p> : null}
      {m ? (
        <p>{m.status === "approved" ? `Matched "${m.source_name}" to ${m.instrument_name}.`
          : m.status === "proposed" ? `Proposed match, not yet approved: "${m.source_name}" to ${m.instrument_name}.`
          : `"${m.source_name}" is not matched to any fund yet.`}{" "}
          {m.status === "proposed" && m.can_approve ? <Button onClick={() => { setError(""); approveAlias(m.identifier_id).then((n) => setD({ ...d, match: n })).catch((e) => setError(plain(e))); }}>Approve this match</Button> : null}</p>
      ) : null}
      <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>{d.versions.map((v) => <Statement key={v.id} v={v} />)}</div>
      <section aria-label="Read fields"><h2>What was read</h2>
        <table><thead><tr><th>Field</th><th>Original</th><th>Amended</th><th>Read confidence</th><th>State</th><th>Your say</th></tr></thead>
          <tbody>{d.fields.map((f) => <FieldRow key={f.id} f={f} canReview={d.can_review} onDone={done} onError={setError} />)}</tbody></table>
      </section>
    </PageFrame>
  );
}
