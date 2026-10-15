import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { Button, PageFrame, Pill } from "../../design";
import { readBase64 } from "../i6/api";
import { useProjectTitle } from "../s1/useProjectTitle";
import * as api from "./api";

// V6 H1-H6: Span the architect. What I already know, the few questions (each with a default to accept), the samples, the design pack, and the
// head of data's approval. Copy follows docs/plan/v5-designs/H1..H6; every proposal is labelled as Span's proposal.
const plain = (e: unknown) => (e instanceof ApiError && e.message ? e.message : "That did not go through. Please try again.");
const STATUS: Record<api.System["status"], string> = { connected: "Connected", landed: "Landed", sample: "Sample kept", never_seen: "Never seen" };
type Tab = "know" | "ask" | "samples" | "pack";
type Part = "target" | "catalogue" | "mapping" | "rules" | "sources";
const PARTS: [Part, string][] = [["target", "Target model"], ["catalogue", "Catalogue"], ["mapping", "ETL mapping sheet"], ["rules", "Rules"], ["sources", "Sources"]];

const word = (v: unknown): string => (typeof v === "string" ? v : Array.isArray(v) ? v.map(word).join(", ") : v && typeof v === "object"
  ? ("label" in v && typeof v.label === "string" ? v.label : "text" in v && typeof v.text === "string" ? v.text : Object.values(v).map(word).join(" · ")) : String(v ?? ""));

function Know({ s, pid, reload, can }: { s: api.Summary; pid: string; reload: () => Promise<void>; can: boolean }) {
  const [fix, setFix] = useState<{ id: string; field: string; value: string } | null>(null);
  const [error, setError] = useState("");
  const run = async (f: () => Promise<unknown>) => { setError(""); try { await f(); await reload(); setFix(null); } catch (e) { setError(plain(e)); } };
  return (
    <section aria-label="What Span already knows">
      <p className="ds-card" style={{ padding: 12 }}><strong>Span the architect.</strong> {s.line}</p>
      <h3>Figures to produce</h3>
      <ul>{s.kpis.map((k) => <li key={k.code}><strong>{k.name}</strong>{k.signed ? " (signed definition)" : " (no definition yet)"}</li>)}</ul>
      <h3>Sources named in the intent</h3>
      <table className="ds-table">
        <thead><tr><th>Source</th><th>How it arrives</th><th>Status</th><th>What the scan found</th><th /></tr></thead>
        <tbody>{s.systems.map((x) => (
          <tr key={x.id}>
            <td><strong>{x.name}</strong><br /><span className="ds-muted">{x.holds || "What it holds is not recorded"}{x.owner ? ` · ${x.owner}` : ""}</span></td>
            <td>{x.channel ? api.CHANNEL_WORDS[x.channel as api.Channel] ?? x.channel : "Not known: one question"}{x.frequency ? `, ${x.frequency}` : ""}
              {x.from_intent ? <> <Pill tone="signed">from the intent</Pill></> : null}
              {x.corrected.length ? <><br /><span className="ds-muted">The intent said: {x.corrected.map((f) => `${f} ${(x.intent as Record<string, string>)[f] || "nothing"}`).join(", ")}</span></> : null}</td>
            <td>{STATUS[x.status]}</td>
            <td>{x.found?.columns ? `${x.found.columns} columns, ${x.found.rows ?? 0} rows` : x.found?.documents ? `${x.found.documents} documents` : "Nothing landed yet"}</td>
            <td>{can ? (x.confirmed ? <span className="ds-muted">Confirmed</span> : <Button disabled={!x.channel} onClick={() => void run(() => api.confirmSystems(pid, [x.id]))}>Confirm</Button>) : null}
              {can ? <> <Button onClick={() => setFix({ id: x.id, field: "channel", value: x.channel || "upload" })}>This is different</Button></> : null}</td>
          </tr>))}</tbody>
      </table>
      {fix ? (
        <div role="group" aria-label="Correct a system" className="ds-card" style={{ padding: 12, marginTop: 8 }}>
          <label>How it arrives{" "}
            <select value={fix.field === "channel" ? fix.value : "upload"} onChange={(e) => setFix({ ...fix, field: "channel", value: e.target.value })}>
              {api.CHANNELS.map((c) => <option key={c} value={c}>{api.CHANNEL_WORDS[c]}</option>)}</select></label>{" "}
          <Button variant="primary" onClick={() => void run(() => api.correctSystem(pid, fix.id, { [fix.field]: fix.value }))}>Save: the intent and the pack both change</Button>
        </div>) : null}
      {error ? <p role="alert" className="ds-error">{error}</p> : null}
      <p className="ds-muted">Not asked, already known: {s.not_asked.join("; ") || "nothing yet"}.</p>
    </section>
  );
}

function Ask({ pid, qs, reload, can }: { pid: string; qs: api.Questions | null; reload: () => Promise<void>; can: boolean }) {
  const [error, setError] = useState("");
  const run = async (f: () => Promise<unknown>) => { setError(""); try { await f(); await reload(); } catch (e) { setError(plain(e)); } };
  if (!qs) return <p className="ds-muted" role="status">Reading what is missing.</p>;
  const asks = qs.all.filter((q) => q.topic !== "Sample");
  return (
    <section aria-label="The few questions">
      <p>{qs.open.filter((q) => q.topic !== "Sample").length ? "Span has a proposed answer for each question. Accept it or edit it." : "Everything is answered."}</p>
      {asks.map((q) => (
        <div key={q.id} className="ds-card" style={{ padding: 12, marginBottom: 8 }}>
          <p style={{ margin: 0 }}><span className="ds-muted">{q.topic.toUpperCase()}</span> {q.state === "answered" ? <Pill tone="signed">Answered</Pill> : null}</p>
          <h3 style={{ margin: "4px 0" }}>{q.title}</h3>
          <p className="ds-muted" style={{ margin: 0 }}>{q.why} {q.evidence}</p>
          <p style={{ margin: "8px 0" }}><span className="ds-muted">Span proposes (suggestion):</span> {word(q.proposal) || "nothing beyond values by date"}</p>
          {q.state === "answered" ? <p style={{ margin: 0 }}>Your answer: <strong>{word(q.answer) || "none"}</strong></p> : null}
          {can && q.state === "open" ? (
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {q.id.startsWith("source:") ? api.CHANNELS.map((c) => <Button key={c} variant={c === q.proposal ? "primary" : undefined} onClick={() => void run(() => api.answer(pid, q.id, c))}>{api.CHANNEL_WORDS[c]}</Button>)
                : q.id === "history" ? <>
                    {q.options.map((o) => <Button key={o} onClick={() => void run(() => api.answer(pid, q.id, [o]))}>Keep history of {o.replace(/_/g, " ")}</Button>)}
                    <Button variant="primary" onClick={() => void run(() => api.answer(pid, q.id, []))}>None beyond values by date</Button></>
                : <Button variant="primary" onClick={() => void run(() => api.answer(pid, q.id, q.proposal))}>Accept</Button>}
            </div>) : null}
        </div>))}
      {can && qs.open.some((q) => q.topic !== "Sample") ? <Button variant="primary" onClick={() => void run(() => api.acceptAll(pid))}>Accept all and continue</Button> : null}
      {error ? <p role="alert" className="ds-error">{error}</p> : null}
    </section>
  );
}

function Samples({ pid, s, reload, can }: { pid: string; s: api.Summary; reload: () => Promise<void>; can: boolean }) {
  const [error, setError] = useState("");
  const [lines, setLines] = useState<{ sid: string; rows: { n: number; text: string }[] } | null>(null);
  const [mark, setMark] = useState({ name: "", format: "text" });
  const need = s.systems.filter((x) => x.format === "pdf" || x.status === "never_seen" || x.sample);
  const run = async (f: () => Promise<unknown>) => { setError(""); try { await f(); await reload(); } catch (e) { setError(plain(e)); } };
  const up = (x: api.System, file: File | undefined) => file && void run(async () => {
    const data = await readBase64(file);
    if (file.name.toLowerCase().endsWith(".pdf")) { await api.samplePdf(pid, x.id, file.name, data); setLines({ sid: x.id, rows: (await api.sampleLines(pid, x.id)).lines }); } else await api.sampleTable(pid, x.id, file.name, data);
  });
  return (
    <section aria-label="Samples">
      <p>Span asks for a sample only for a source it has never seen, or a PDF whose fields must be read once.</p>
      {need.map((x) => (
        <div key={x.id} className="ds-card" style={{ padding: 12, marginBottom: 8 }}>
          <h3 style={{ marginTop: 0 }}>{x.name} <span className="ds-muted">{x.format === "pdf" ? "mark the fields to read" : "show one file"}</span></h3>
          {can ? <label>Choose a file <input type="file" aria-label={`Sample for ${x.name}`} accept={x.format === "pdf" ? ".pdf" : ".xlsx,.xlsm,.csv"} onChange={(e) => up(x, e.target.files?.[0])} /></label> : null}
          {x.sample?.kind === "table" ? (
            <table className="ds-table"><thead><tr><th>Column</th><th>Type</th><th>Where it goes</th></tr></thead>
              <tbody>{(x.sample.columns ?? []).map((c) => <tr key={c.name}><td>{c.name}</td><td>{c.type}</td><td>{c.goes_to && c.goes_to !== "ignore" ? c.goes_to : <span className="ds-muted">to confirm</span>}</td></tr>)}</tbody></table>) : null}
          {x.sample?.kind === "pdf" ? (
            <div>
              <p className="ds-muted">Fields marked: {(x.sample.fields ?? []).map((f) => `${f.name} (${f.where_usually || "line " + f.line})`).join("; ") || "none yet"}. Span will read these from every statement.</p>
              {can ? <Button onClick={() => void run(async () => setLines({ sid: x.id, rows: (await api.sampleLines(pid, x.id)).lines }))}>Show the statement lines</Button> : null}
            </div>) : null}
          {lines?.sid === x.id ? (
            <div role="group" aria-label="Statement lines">
              <label>Name this field <input value={mark.name} onChange={(e) => setMark({ ...mark, name: e.target.value })} /></label>{" "}
              <select aria-label="Field format" value={mark.format} onChange={(e) => setMark({ ...mark, format: e.target.value })}>{["text", "number", "date", "percent"].map((f) => <option key={f}>{f}</option>)}</select>
              <ol style={{ maxHeight: 220, overflow: "auto" }}>{lines.rows.map((l) => (
                <li key={l.n}>{l.text}{" "}<Button disabled={!mark.name.trim()} onClick={() => void run(() => api.markField(pid, x.id, l.n, mark.name.trim(), mark.format))}>Mark here</Button></li>))}</ol>
            </div>) : null}
        </div>))}
      {need.length === 0 ? <p className="ds-muted">No sample is needed.</p> : null}
      {error ? <p role="alert" className="ds-error">{error}</p> : null}
    </section>
  );
}

function PackParts({ view, pid, reload }: { view: api.PackView; pid: string; reload: () => Promise<void> }) {
  const pack = view.pack as api.Pack;
  const [part, setPart] = useState<Part>("target");
  const [error, setError] = useState("");
  const [diff, setDiff] = useState<api.Diff | null>(null);
  const [from, setFrom] = useState<number | null>(null);
  const [editing, setEditing] = useState<{ section: string; key: string; field: string; value: string } | null>(null);
  const run = async (f: () => Promise<unknown>) => { setError(""); try { await f(); await reload(); setEditing(null); } catch (e) { setError(plain(e)); } };
  const can = view.can.edit;
  const fix = (section: string, key: string, field: string, value: string) => can ? <> <Button onClick={() => setEditing({ section, key, field, value })}>Correct a line</Button></> : null;
  return (
    <section aria-label="The design pack">
      <p className="ds-muted">One document, versioned. Each line can be corrected by the team. Approved means locked for the builder.</p>
      <div role="tablist" aria-label="Parts of the pack" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {PARTS.map(([id, name]) => <Button key={id} variant={part === id ? "primary" : undefined} onClick={() => setPart(id)}>{name}</Button>)}
        <Button disabled={view.versions.length < 2} title={view.versions.length < 2 ? "There is one version so far" : undefined}
          onClick={() => void api.getDiff(pid, from ?? view.versions[view.versions.length - 2]?.version ?? 1, pack.version).then(setDiff).catch((e) => setError(plain(e)))}>Compare versions</Button>
        {view.versions.length > 1 ? <label className="ds-muted">with version <select aria-label="Compare with version" value={from ?? view.versions[view.versions.length - 2]?.version} onChange={(e) => setFrom(Number(e.target.value))}>
          {view.versions.filter((v) => v.version !== pack.version).map((v) => <option key={v.version} value={v.version}>{v.version}</option>)}</select></label> : null}
      </div>
      {diff ? (
        <div className="ds-card" style={{ padding: 12, margin: "8px 0" }} aria-label="Versions compared">
          <strong>Version {diff.from} to {diff.to}</strong>{diff.changes.length === 0 ? <p>No difference.</p> : null}
          <ul>{diff.changes.map((c) => <li key={c.line}>{c.change === "added" ? "Added" : c.change === "removed" ? "Removed" : "Changed"}: {c.line}{c.before ? <> <s>{c.before}</s></> : null} {c.after}</li>)}</ul>
          <Button onClick={() => setDiff(null)}>Close</Button>
        </div>) : null}
      {part === "target" ? (
        <div>
          <h3>Gold tables <span className="ds-muted">What Lumen reads. Type 2 columns keep their history.</span></h3>
          <table className="ds-table" aria-label="Gold tables">
            <thead><tr><th>Table and columns</th><th>Grain and key</th><th>Type 2</th><th>Owner</th><th /></tr></thead>
            <tbody>{pack.target.gold.map((g) => (
              <tr key={g.name}>
                <td><strong>{g.name}</strong><br /><span className="ds-muted">{g.columns.map((c) => `${c.name} ${c.type.toLowerCase()}`).join(" · ")}</span></td>
                <td>{g.grain}<br /><span className="ds-muted">Key: {g.keys.join(" + ") || "none"}</span></td>
                <td>{g.history.join(", ") || "none"}</td><td>{g.owner || "not set"}</td><td>{fix("gold_table", g.name, "owner", g.owner)}</td>
              </tr>))}</tbody>
          </table>
          {pack.target.gold.map((g) => (
            <details key={g.name} className="ds-card" style={{ padding: 12, marginBottom: 8 }}>
              <summary>Columns, types and definitions of {g.name.replace(/^gold_/, "")}</summary>
              <table className="ds-table"><thead><tr><th>Column</th><th>Type</th><th>Definition</th><th /></tr></thead>
                <tbody>{g.columns.map((c) => <tr key={c.name}><td>{c.name}</td><td>{c.type}</td><td>{c.definition}</td><td>{fix("gold_column", `${g.name}.${c.name}`, "definition", c.definition)}</td></tr>)}</tbody></table>
            </details>))}
          {can && !pack.locked ? <AddGold pid={pid} reload={reload} /> : null}
          <h3>Silver reused <span className="ds-muted">The company model stays as it is; the gold tables read these</span></h3>
          <table className="ds-table" aria-label="Silver reused"><thead><tr><th>Table</th><th>Used</th><th>Other projects that read it</th><th /></tr></thead>
            <tbody>{pack.target.silver.filter((t) => t.status !== "proposed").map((t) => <tr key={t.name}><td>{t.name}</td><td>{t.note}</td>
              <td>{t.other_projects?.length ? t.other_projects.join(", ") : "none yet"}</td><td>{fix("silver", t.name, "note", t.note)}</td></tr>)}</tbody></table>
          {pack.target.silver.some((t) => t.status === "proposed") ? (
            <section aria-label="Silver proposed">
              <h3>Silver proposed <span className="ds-muted">Needs the head of data{view.model_change ? ` (model change ${view.model_change.version}: ${view.model_change.state})` : ""}</span></h3>
              {pack.target.silver.filter((t) => t.status === "proposed").map((t) => (
                <div key={t.name} className="ds-card" style={{ padding: 12, marginBottom: 8 }}>
                  <strong>{t.extends ? `Add columns to ${t.name}` : `New table ${t.name}`}</strong>: {(t.columns ?? []).join(", ")}
                  <p>Looked for: {t.looked_for || "not said"}</p>
                  <p>Considered: {(t.considered ?? []).map((c) => `${c.table} (${c.why_not})`).join("; ") || "none"}</p>
                  <p>Affects: {t.affects?.length ? t.affects.join("; ") : "no other project reads it yet"}</p>
                </div>))}
            </section>) : null}
          {pack.definitions?.length ? (
            <>
              <h3>Definitions <span className="ds-muted">Signed definitions are used as they are</span></h3>
              <table className="ds-table" aria-label="Definitions"><thead><tr><th>Figure</th><th>Definition and source</th><th /></tr></thead>
                <tbody>{pack.definitions.map((d) => (
                  <tr key={d.name}><td>{d.name}</td><td>{d.definition}<br /><span className="ds-muted">{d.source}</span></td><td>{fix("definition", d.name, "definition", d.definition)}</td></tr>))}</tbody></table>
            </>) : null}
          {pack.benchmark ? (
            <section aria-label="Benchmark check">
              <h3>Benchmark check <span className="ds-muted">What the builder compares with the report you give it</span></h3>
              <p>
                {pack.benchmark.portfolio ? <><strong>{pack.benchmark.portfolio}</strong>{pack.benchmark.portfolio_name ? ` (${pack.benchmark.portfolio_name})` : ""}</> : <span className="ds-warn">No portfolio chosen yet</span>}
                {" "}against <strong>{pack.benchmark.code || "no benchmark chosen yet"}</strong>{pack.benchmark.version ? `, signed version ${pack.benchmark.version}` : ""}, for <strong>{pack.benchmark.month || "no month yet"}</strong>.
                {" "}It compares {pack.benchmark.figures.map((f) => f.label.toLowerCase()).join(", ")}, and the weight of each leg.
              </p>
              {can ? <p>{fix("benchmark", "portfolio", "portfolio", pack.benchmark.portfolio)} {fix("benchmark", "code", "code", pack.benchmark.code)} {fix("benchmark", "month", "month", pack.benchmark.month)}</p> : null}
            </section>) : null}
          <div className="ds-card" style={{ padding: 12, marginTop: 12, display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
            <strong>Next</strong><span className="ds-muted">The mapping sheet shows how each source field becomes a gold column.</span>
            <Button variant="primary" onClick={() => setPart("mapping")}>Open the mapping sheet</Button>
          </div>
        </div>) : null}
      {part === "catalogue" ? (
        <table className="ds-table"><thead><tr><th>Table</th><th>Column</th><th>Meaning</th><th>Source</th><th>Sensitivity</th><th /></tr></thead>
          <tbody>{pack.catalogue.map((c) => <tr key={`${c.table}.${c.column}`}><td>{c.table}</td><td>{c.column}</td><td>{c.meaning}</td><td>{c.source}</td><td>{c.sensitivity}</td>
            <td>{c.layer === "gold" ? fix("catalogue", `${c.table}.${c.column}`, "meaning", c.meaning) : null}</td></tr>)}</tbody></table>) : null}
      {part === "mapping" ? (
        <div>
          <p>{pack.open_rows ? <Pill tone="draft">{pack.open_rows} rows need a person</Pill> : "No row is open."} Source field, then bronze, silver and gold, with the transformation.</p>
          <table className="ds-table"><thead><tr><th>Source field</th><th>Bronze</th><th>Silver</th><th>Gold</th><th>Transformation or formula</th><th /></tr></thead>
            <tbody>{pack.mapping.map((m) => (
              <tr key={m.id} data-open={!!m.needs_person && !m.resolved}>
                <td>{m.system ? `${m.system}: ` : ""}{m.source_field || (m.kind === "derived" ? "Derived" : "")}</td><td>{m.bronze}</td><td>{m.silver}</td><td>{m.gold}</td>
                <td>{m.words}{m.needs_person && !m.resolved ? <><br /><strong>{m.needs_person}</strong></> : null}</td>
                <td>{can ? (m.needs_person && !m.resolved ? <Button onClick={() => setEditing({ section: "mapping", key: m.id, field: "resolve", value: "" })}>Settle</Button> : fix("mapping", m.id, "words", m.words)) : null}</td>
              </tr>))}</tbody></table>
        </div>) : null}
      {part === "rules" ? (
        <div>
          <h3>Checks <span className="ds-muted">from the process map</span></h3>
          <ul>{pack.rules.checks.map((c) => <li key={c.id}>{c.text} <span className="ds-muted">({c.tolerance})</span>{fix("rule_check", c.id, "tolerance", c.tolerance)}</li>)}</ul>
          <p>Refresh: <strong>{pack.rules.refresh.label ?? `${pack.rules.refresh.at} ${pack.rules.refresh.freq}`}</strong>. Late data: {pack.rules.late_data} Benchmark: {pack.rules.benchmark}.</p>
          <p>History kept (type 2): {pack.rules.history.join(", ") || "none beyond values by date"}.</p>
        </div>) : null}
      {part === "sources" ? (
        <table className="ds-table"><thead><tr><th>Source</th><th>How it arrives</th><th>Sample</th></tr></thead>
          <tbody>{pack.sources.map((x) => <tr key={x.id}><td>{x.name}</td><td>{api.CHANNEL_WORDS[x.channel as api.Channel] ?? "not known"}{x.frequency ? `, ${x.frequency}` : ""}</td>
            <td>{x.sample ?? "none"}{x.marked_fields.length ? ` · fields marked: ${x.marked_fields.join(", ")}` : ""}</td></tr>)}</tbody></table>) : null}
      {editing ? (
        <div role="group" aria-label="Correct a line" className="ds-card" style={{ padding: 12, marginTop: 8 }}>
          <label>{editing.section === "mapping" && editing.field === "resolve" ? "How was it settled?" : `New value for ${editing.field}`}{" "}
            <input value={editing.value} maxLength={300} onChange={(e) => setEditing({ ...editing, value: e.target.value })} /></label>{" "}
          <Button variant="primary" disabled={!editing.value.trim()} onClick={() => void run(() => editing.field === "resolve"
            ? api.edit(pid, editing.section, editing.key, { resolve: true }, editing.value.trim()) : api.edit(pid, editing.section, editing.key, { [editing.field]: editing.value.trim() }))}>Save as a correction</Button>{" "}
          <Button onClick={() => setEditing(null)}>Cancel</Button>
        </div>) : null}
      {error ? <p role="alert" className="ds-error">{error}</p> : null}
    </section>
  );
}

function AddGold({ pid, reload }: { pid: string; reload: () => Promise<void> }) {
  const [f, setF] = useState({ name: "", purpose: "", sql: "", reads: "" });
  const [error, setError] = useState("");
  return (
    <details className="ds-card" style={{ padding: 12, margin: "8px 0" }}>
      <summary>Add a gold table</summary>
      <label>Name <input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="gold_..." /></label>{" "}
      <label>What it is for <input value={f.purpose} onChange={(e) => setF({ ...f, purpose: e.target.value })} maxLength={300} /></label>{" "}
      <label>Tables it reads <input value={f.reads} onChange={(e) => setF({ ...f, reads: e.target.value })} placeholder="cash_movements, portfolios" /></label>
      <label>Select <textarea value={f.sql} onChange={(e) => setF({ ...f, sql: e.target.value })} rows={4} placeholder="create table gold_... as select ..." /></label>{" "}
      <Button variant="primary" disabled={!f.name.trim() || !f.sql.trim()} onClick={() => void (async () => {
        setError("");
        try { await api.edit(pid, "gold_add", f.name.trim(), { purpose: f.purpose, sql: f.sql, depends_on: f.reads }); setF({ name: "", purpose: "", sql: "", reads: "" }); await reload(); } catch (e) { setError(plain(e)); }
      })()}>Add to the pack</Button>
      {error ? <p role="alert" className="ds-error">{error}</p> : null}
    </details>
  );
}

function Approve({ view, pid, reload }: { view: api.PackView; pid: string; reload: () => Promise<void> }) {
  const pack = view.pack as api.Pack;
  const [note, setNote] = useState("");
  const [why, setWhy] = useState("");
  const [error, setError] = useState("");
  const run = async (f: () => Promise<unknown>) => { setError(""); try { await f(); await reload(); } catch (e) { setError(plain(e)); } };
  return (
    <section aria-label="Approve the design pack" className="ds-card" style={{ padding: 16, marginTop: 16 }}>
      <h3 style={{ marginTop: 0 }}>Design pack version {pack.version} <Pill tone={pack.state === "approved" ? "signed" : "draft"}>{pack.state === "approved" ? "Approved" : pack.state === "proposed" ? "Waiting for the head of data" : pack.state === "superseded" ? "Superseded" : "Draft"}</Pill></h3>
      <p className="ds-muted">{pack.counts.sources} sources · {pack.counts.gold} gold and {pack.counts.silver} silver tables · {pack.counts.mapping} mapping rows ({pack.open_rows} open) · {pack.counts.checks} checks</p>
      {pack.send_back ? <p role="status">Sent back: {pack.send_back}</p> : null}
      {pack.state === "approved" ? <p>Approved by {pack.approved_by}. Locked for the builder; the team can still edit it through a new version.{view.plan_version ? ` The build plan is version ${view.plan_version}.` : ""}{pack.plan_state === "approved" ? " The build plan and the model change it carries were approved with it, so the builder can start." : ""}</p> : null}
      {pack.state === "approved" && pack.plan_state === "not_approved" ? (
        <p role="status">The build plan could not be approved with the pack{pack.plan_error ? `: ${pack.plan_error}` : ""}. {view.can.approve_plan ? <Button variant="primary" onClick={() => void run(() => api.approvePlan(pid))}>Approve the build plan</Button> : "The head of data approves it next."}</p>) : null}
      {view.can.submit ? <Button variant="primary" disabled={pack.open_rows > 0} onClick={() => void run(() => api.submit(pid))}>Send to the head of data for approval</Button> : null}
      {view.can.submit && pack.open_rows > 0 ? <span className="ds-muted"> Settle the open mapping rows first.</span> : null}
      {view.can.approve ? (
        <div>
          <label>Note to the builder <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} /></label>{" "}
          <Button variant="primary" onClick={() => void run(() => api.approve(pid, note))}>Approve version {pack.version}</Button>{" "}
          <label>Why not <input value={why} onChange={(e) => setWhy(e.target.value)} maxLength={300} /></label>{" "}
          <Button disabled={!why.trim()} onClick={() => void run(() => api.reject(pid, why))}>Send back</Button>
        </div>) : null}
      {view.can.plan ? <Button onClick={() => void run(() => api.planFromPack(pid))}>Draw the build plan from this pack</Button> : null}
      <ul className="ds-muted">{(view.log ?? []).slice(-5).map((l, i) => <li key={i}>{l.by}: {l.what}{l.note ? ` (${l.note})` : ""}</li>)}</ul>
      {error ? <p role="alert" className="ds-error">{error}</p> : null}
    </section>
  );
}

const ROLES: [string, string][] = [["raiser", "Business owner"], ["sponsor", "Sponsor"], ["head_of_data", "Head of data"], ["builder", "Data engineer"]]; // H4: the roles line under the title

export default function ArchitectureStep() {
  const { projectId = "" } = useParams();
  const title = useProjectTitle(projectId);
  const [tab, setTab] = useState<Tab>("know");
  const [summary, setSummary] = useState<api.Summary | null>(null);
  const [qs, setQs] = useState<api.Questions | null>(null);
  const [view, setView] = useState<api.PackView | null>(null);
  const [problem, setProblem] = useState("");
  const [busy, setBusy] = useState(false);
  const reload = useCallback(async () => {
    try {
      const [s, q, v] = await Promise.all([api.getSummary(projectId), api.getQuestions(projectId), api.getPack(projectId)]);
      setSummary(s); setQs(q); setView(v); setProblem("");
    } catch (e) { setProblem(plain(e)); }
  }, [projectId]);
  useEffect(() => { void reload(); }, [reload]);
  useEffect(() => { if (view?.pack) setTab("pack"); }, [view?.pack?.version]); // eslint-disable-line react-hooks/exhaustive-deps
  const can = !!view?.can.answer;
  const draft = async () => { setBusy(true); try { setView(await api.generate(projectId)); setTab("pack"); } catch (e) { setProblem(plain(e)); } finally { setBusy(false); } };
  const tabs: [Tab, string][] = [["know", "What I already know"], ["ask", "The few questions"], ["samples", "Samples"], ["pack", "The design pack"]];
  return (
    <PageFrame title={`${title}: Architecture`} subline="Span the architect reads what the intent says, asks only what is missing, then drafts the design pack for the head of data.">
      <div className="ds-dark">{/* V6B: drawn dark, as in designs H1 to H6 */}
      {summary?.people ? <p className="ds-muted" data-testid="roles">{ROLES.filter(([k]) => summary.people?.[k]).map(([k, n]) => `${n} ${summary.people?.[k]}`).join(" · ")}</p> : null}
      <div role="tablist" aria-label="Architecture steps" style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
        {tabs.map(([id, name]) => <Button key={id} variant={tab === id ? "primary" : undefined} onClick={() => setTab(id)}>{name}</Button>)}
      </div>
      <p><Link to={`/centre/build/p/${projectId}/architecture/model`}>Model view: the three layers and every table</Link></p>
      {problem ? <p role="alert" className="ds-error">{problem}</p> : null}
      {!summary && !problem ? <p className="ds-muted" role="status">Span is reading the intent.</p> : null}
      {summary && tab === "know" ? <Know s={summary} pid={projectId} reload={reload} can={can} /> : null}
      {tab === "ask" ? <Ask pid={projectId} qs={qs} reload={reload} can={can} /> : null}
      {summary && tab === "samples" ? <Samples pid={projectId} s={summary} reload={reload} can={can} /> : null}
      {tab === "pack" ? (view?.pack ? <><PackParts view={view} pid={projectId} reload={reload} /><Approve view={view} pid={projectId} reload={reload} /></>
        : <div><p>The pack is not drafted yet. With the answers and samples, Span writes it.</p>{view?.can.generate ? <Button variant="primary" disabled={busy} onClick={() => void draft()}>Draft the design pack</Button> : <p className="ds-muted">The data team drafts it.</p>}</div>) : null}
      {tab === "pack" && view?.pack && view.can.generate ? <p><Button disabled={busy} onClick={() => void draft()}>Draft again from the latest answers</Button></p> : null}
      </div>
    </PageFrame>
  );
}
