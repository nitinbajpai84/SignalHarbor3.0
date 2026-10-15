import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { Button, CheckIcon, Pill, WarningIcon, when, type PillTone } from "../../design";
import { ask, num, signed } from "../b9verify/format";
import "../b9verify/verify.css";
import * as api from "./api";
import type { BuilderView, Connection, Message, Variance, VarianceLine } from "./api";
import "./b11.css";

// V6-builder, designs H7 to H9. Span the builder: connect each source as the pack says, run on a copy, check against a benchmark, go live or send back.
const CONN: Record<Connection["status"], [PillTone, string]> = { connected: ["ok", "Connected"], failed: ["failed", "Failed"], needs_sample: ["late", "Needs a sample"], mismatch: ["late", "Check the details"], not_needed: ["open", "Not needed"] };
const LINE: Record<VarianceLine["status"], [PillTone, string]> = { matches: ["ok", "Matches"], explained: ["open", "Explained"], unexplained: ["failed", "Unexplained"] };
const FREQ: Record<string, string> = { daily: "every day", weekly: "every week", monthly: "every month", on_arrival: "when a new file arrives" };
const show = (v: string | string[] | null) => (Array.isArray(v) ? v.join(", ") : v ?? "Not given");
const unit = (l: VarianceLine, v: string | null) => (v === null ? "none" : l.unit === "pct" ? `${num(v, 2)}%` : num(v));
// the pack's refresh rule as written, its day too ("every month at 06:00, by the 5th business day")
const schedule = (s: { freq: string; at: string; day?: string | number | null } | null | undefined) =>
  (s ? `${FREQ[s.freq] ?? s.freq}${s.freq === "on_arrival" ? "" : ` at ${s.at}`}${s.freq === "monthly" && s.day ? `, by the ${s.day}` : ""}` : "on its schedule");

function toBase64(file: File): Promise<string> {
  return new Promise((ok, no) => {
    const r = new FileReader();
    r.onload = () => ok(String(r.result).split(",")[1] ?? "");
    r.onerror = () => no(new Error("That file could not be read. Please try another."));
    r.readAsDataURL(file);
  });
}

export default function BuilderPanel({ pid }: { pid: string }) {
  const [v, setV] = useState<BuilderView | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [signedId, setSignedId] = useState("");
  const started = useRef(false);

  const act = useCallback(async (f: () => Promise<BuilderView>) => { setBusy(true); try { setV(await f()); setErr(""); } catch (e) { setErr(ask(e)); } finally { setBusy(false); } }, []);
  useEffect(() => {
    let live = true;
    api.getBuilder(pid).then((x) => {
      if (!live) return;
      setV(x);
      if (x.can.start && !started.current) { started.current = true; void act(() => api.startBuilder(pid)); } // the builder starts by itself: nobody clicks Run
    }).catch((e) => live && setErr(ask(e)));
    return () => { live = false; };
  }, [pid, act]);

  if (!v) return <p className="ds-muted" role="status">{err ? `The builder is not available right now. ${err}` : "Opening the builder."}</p>;
  const r = v.round, pack = v.pack, var_ = r?.variance ?? null;
  return (
    <section className="b11 ds-dark" aria-label="Span the builder">
      <div className="b11-head">
        <h2>Span the builder: connecting and running</h2>
        {pack ? <Pill tone="signed">{`Pack version ${pack.version} · locked`}</Pill> : null}
        {v.newer ? <Pill tone="draft">{`Version ${v.newer.version} waits for the head of data`}</Pill> : null}
      </div>
      {err ? <p role="alert" className="b9v-err"><WarningIcon size={16} /> {err}</p> : null}
      {!pack ? <p className="ds-muted" role="status">{v.waiting}</p> : null}
      {pack && !r && busy ? <p className="ds-muted" role="status">{pack.sources ? `Connecting the ${pack.sources} source${pack.sources === 1 ? "" : "s"} and running` : "Running"} on a copy.</p> : null}

      <Thread messages={v.thread} />
      {r?.connections.length ? <Connections v={v} act={act} pid={pid} busy={busy} /> : null}
      {r?.run ? <RunCard r={r} pid={pid} /> : null}
      {r?.run?.status === "ok" && !var_ ? <Ask v={v} pid={pid} busy={busy} act={act} signedId={signedId} setSignedId={setSignedId} /> : null}
      {var_ && r ? <Result var_={var_} r={r} /> : null}
      {r && ["checked", "ran", "sent_back", "live"].includes(r.state) ? (
        <div className="b11-next">
          <Next v={v} pid={pid} busy={busy} act={act} note={note} setNote={setNote} />
        </div>) : null}
      {v.can.issue && r?.state === "sent_back" ? <Issue v={v} pid={pid} busy={busy} act={act} /> : null}
    </section>
  );
}

function Thread({ messages }: { messages: Message[] }) {
  if (!messages.length) return null;
  return (
    <div className="b9v-card" aria-label="The two Span roles">
      <p className="ds-muted" style={{ margin: 0 }}>The two Span roles talk it through here, so you see why the pack changed. People only approve the new version.</p>
      {messages.map((m) => (
        <div key={m.at + m.text} className="b11-voice" data-who={m.who}>
          <strong>{m.who} · {when(m.at)}</strong>
          <p>{m.text}</p>
          {m.evidence.map((e) => <span key={e.text} className="b11-ev">Evidence: {e.text}</span>)}
        </div>))}
    </div>
  );
}

function Connections({ v, act, pid, busy }: { v: BuilderView; act: (f: () => Promise<BuilderView>) => Promise<void>; pid: string; busy: boolean }) {
  const cs = v.round!.connections, ok = cs.filter((c) => c.status === "connected").length;
  return (
    <div className="b9v-card" aria-label="Connecting the sources">
      <h2>Connecting the {cs.length} source{cs.length === 1 ? "" : "s"}</h2>
      <p className="ds-muted" style={{ margin: 0 }}>{ok} connected{cs.length - ok ? `, ${cs.length - ok} need${cs.length - ok === 1 ? "s" : ""} a person` : ""}</p>
      {cs.map((c) => (
        <div key={c.code} className="b11-src">
          <div><strong>{c.name}</strong><p className="ds-muted">{c.how_words}{c.from_intent ? " · as in the intent" : " · as in the pack"}</p></div>
          <p>{c.detail}{c.status === "failed" || c.status === "needs_sample" ? ` ${needTo(v, c)}` : ""}</p>
          <Pill tone={CONN[c.status][0]}>{CONN[c.status][1]}</Pill>
          {v.can.not_needed && (c.status === "needs_sample" || c.status === "not_needed") ? (
            <div className="b11-actions">
              {c.status === "needs_sample" ? (
                <Button disabled={busy} onClick={() => { if (window.confirm(`Take ${c.name} out of the build? It has no sample file. You can put it back later.`)) void act(() => api.notNeeded(pid, { source: c.code })); }}>Mark as not needed</Button>
              ) : <Button disabled={busy} onClick={() => void act(() => api.notNeeded(pid, { source: c.code, needed: true }))}>Put it back</Button>}
            </div>) : null}
          {c.mismatches.map((m) => (
            <div key={m.field} className="b11-mismatch" role="group" aria-label={`${c.name}: ${m.field} differs`}>
              <strong>The {m.field === "file" ? "file name" : m.field === "columns" ? "columns" : "host"} differs. Which is right?</strong>
              <dl>
                <dt>The intent says</dt><dd>{show(m.intent)}</dd>
                <dt>The pack says</dt><dd>{show(m.pack)}</dd>
                {m.seen ? <><dt>What I found</dt><dd>{m.seen}</dd></> : null}
              </dl>
              {v.can.settle ? (
                <div className="b11-actions">
                  {[...new Set([m.intent, m.pack, m.seen].map((x) => (x == null ? "" : show(x))).filter(Boolean))].map((val) => (
                    <Button key={val} disabled={busy} onClick={() => void act(() => api.settle(pid, { source: c.code, field: m.field, value: val }))}>Use {val}</Button>))}
                </div>) : null}
              <span className="ds-muted">The answer updates the intent&apos;s system map and the pack together.</span>
            </div>))}
        </div>))}
      {v.can.recheck ? <div><Button disabled={busy} onClick={() => void act(() => api.recheck(pid))}>Check again</Button></div> : null}
    </div>
  );
}

function needTo(v: BuilderView, c: Connection): string {
  const n = v.needs.find((x) => x.source === c.code);
  return n ? `Raised to ${n.to.join(" and ") || "the data team"} in Action.` : "";
}

function RunCard({ r, pid }: { r: NonNullable<BuilderView["round"]>; pid: string }) {
  const run = r.run!;
  return (
    <div className="b9v-card" aria-label="Run on a copy">
      <div className="b11-head"><h2>Run on a copy</h2><Pill tone={run.status === "ok" ? "ok" : "failed"}>{run.status === "ok" ? "Done" : "Failed"}</Pill></div>
      <p className="ds-muted" style={{ margin: 0 }}>Pack version {run.pack_version}, started by itself{run.started ? ` at ${when(run.started)}` : ""}. Nothing touches live data.</p>
      {run.error ? <p role="alert" className="b9v-err"><WarningIcon size={16} /> {run.error} The tables from the last good run are unchanged. <Link className="ds-link" to={`/centre/build/p/${encodeURIComponent(pid)}/architecture`}>Open the design</Link></p> : null}
      {run.steps?.length ? <ul className="b11-steps">{run.steps.map((s) => <li key={s.label}><span>{s.label}</span><span className="ds-muted">{s.rows == null ? s.status : `${num(String(s.rows))} rows`}</span></li>)}</ul> : null}
      {run.tables ? (
        <div className="b9v-tiles">
          <div><span>Tables built</span><strong>{run.tables.bronze + run.tables.silver + run.tables.gold}</strong><small>{run.tables.bronze} bronze, {run.tables.silver} silver, {run.tables.gold} gold</small></div>
          <div><span>Rows in gold</span><strong>{num(String(run.gold_rows ?? 0))}</strong></div>
          <div><span>Checks</span><strong>{run.checks ? `${run.checks.passed} of ${run.checks.total}` : "Not available yet"}</strong><small>control totals against the source files</small></div>
        </div>) : null}
    </div>
  );
}

function Ask({ v, pid, busy, act, signedId, setSignedId }: { v: BuilderView; pid: string; busy: boolean; act: (f: () => Promise<BuilderView>) => Promise<void>; signedId: string; setSignedId: (s: string) => void }) {
  if (!v.can.benchmark) return <p className="ds-muted">Waiting for the data engineer to give the builder a report to check against.</p>;
  const upload = async (f: File | undefined) => { if (f) await act(async () => api.giveBenchmark(pid, { name: f.name, b64: await toBase64(f) })); };
  return (
    <div className="b9v-card" aria-label="Benchmark to check against">
      <div className="b11-voice"><strong>Span the builder</strong><p>Do you have last month&apos;s report to check against? I will compare every figure I can find in it.</p></div>
      <label>Upload last month&apos;s report<input type="file" accept=".pdf,.csv,.txt,.xlsx,.docx" disabled={busy} onChange={(e) => void upload(e.target.files?.[0])} /></label>
      {v.signed_reports.length ? (
        <div className="b11-actions">
          <label>Or pick a signed report<select value={signedId} onChange={(e) => setSignedId(e.target.value)}>
            <option value="">Choose one</option>{v.signed_reports.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
          <Button disabled={busy || !signedId} onClick={() => void act(() => api.giveBenchmark(pid, { report_version_id: signedId }))}>Check against it</Button>
        </div>) : null}
      <div><Button disabled={busy} onClick={() => void act(() => api.goLive(pid, { no_benchmark: true }))}>I have none: go live without a check</Button></div>
    </div>
  );
}

function Lines({ lines, title, first }: { lines: VarianceLine[]; title: string; first: string }) {
  if (!lines.length) return null;
  return (
    <div className="ds-table-wrap">
      <table className="ds-table" aria-label={title}>
        <thead><tr><th>{first}</th><th className="num">This run</th><th className="num">Report</th><th className="num">Variance</th><th>Result</th></tr></thead>
        <tbody>{lines.map((l) => (
          <tr key={l.figure} data-status={l.status}>
            <td>{l.figure}</td><td className="num">{unit(l, l.run)}</td><td className="num">{unit(l, l.report)}</td>
            <td className="num">{l.diff === null ? "" : l.status === "matches" ? "0" : signed(l.diff, l.unit === "pct" ? 2 : undefined)}{l.diff !== null && l.unit === "pct" && l.status !== "matches" ? " pts" : ""}</td>
            <td><Pill tone={LINE[l.status][0]}>{LINE[l.status][1]}</Pill>{l.evidence.map((e) => <span key={e.text} className="b11-ev">{e.text}</span>)}</td>
          </tr>))}</tbody>
      </table>
    </div>
  );
}

function Result({ var_, r }: { var_: Variance; r: NonNullable<BuilderView["round"]> }) {
  return (
    <div className="b9v-card" aria-label="Check against the report">
      <div className="b11-head">
        <h2>Check against {var_.benchmark}</h2>
        <Pill tone={var_.summary.unexplained ? "failed" : "ok"}>{var_.summary.unexplained ? var_.headline : "Variance cleared"}</Pill>
        <span className="ds-muted">Pack version {r.pack_version}</span>
      </div>
      <Lines lines={var_.lines} title="Key figures against the report" first="Figure" />
      <Lines lines={var_.legs} title="Benchmark legs against the report" first="Benchmark leg" />
      {var_.unmatched.length ? <p className="ds-muted">Not compared, because this run has no figure for it: {var_.unmatched.map((u) => u.label).join(", ")}.</p> : null}
    </div>
  );
}

function Next({ v, pid, busy, act, note, setNote }: { v: BuilderView; pid: string; busy: boolean; act: (f: () => Promise<BuilderView>) => Promise<void>; note: string; setNote: (s: string) => void }) {
  const r = v.round!, bad = (r.variance?.summary.unexplained ?? 0) > 0;
  if (r.state === "live") return <p className="b9v-ok"><CheckIcon size={16} /> Live on the pack schedule, {schedule(v.pack?.schedule)}. <Link className="ds-link" to={`/centre/build/p/${encodeURIComponent(pid)}/dashboards`}>Lumen proposes a starter dashboard</Link></p>;
  if (r.state === "sent_back") return <p className="ds-muted" role="status">With the architect. {v.newer ? `Pack version ${v.newer.version} waits for the head of data; ` : "The architect issues the next pack version; "}the builder then runs it by itself.</p>;
  if (!r.variance) return <p className="ds-muted">Give the builder a report to check against, then decide.</p>;
  return (
    <>
      <p style={{ margin: 0 }}>{bad ? "Something does not match. Send it back with the evidence, or go live anyway." : `Looks good. Going live uses the schedule in the pack: ${schedule(v.pack?.schedule)}.`}</p>
      {bad && v.can.send_back ? <label>Note to the architect (optional)<input value={note} onChange={(e) => setNote(e.target.value)} /></label> : null}
      <div className="b11-actions">
        <Button variant={bad ? "secondary" : "primary"} disabled={busy || !v.can.go_live} onClick={() => void act(() => api.goLive(pid, { accept_variance: bad }))}>{bad ? "Go live anyway" : "Go live"}</Button>
        {bad ? <Button variant="primary" disabled={busy || !v.can.send_back} onClick={() => void act(() => api.sendBack(pid, note))}>Send back to the architect</Button> : null}
      </div>
    </>
  );
}

function Issue({ v, pid, busy, act }: { v: BuilderView; pid: string; busy: boolean; act: (f: () => Promise<BuilderView>) => Promise<void> }) {
  const tables = v.pack?.sql ?? [];
  const [table, setTable] = useState(tables[0]?.table ?? "");
  const [sql, setSql] = useState<string | null>(null);
  const [why, setWhy] = useState("");
  const cur = tables.find((t) => t.table === table);
  if (!cur) return null;
  return (
    <form className="b9v-card" aria-label="Issue the next pack version" onSubmit={(e) => { e.preventDefault(); void act(() => api.issuePack(pid, { changes: [{ table, sql: sql ?? cur.sql, why }] })); }}>
      <h2>Span the architect: issue the next pack version</h2>
      <label>Table to change<select value={table} onChange={(e) => { setTable(e.target.value); setSql(null); }}>{tables.map((t) => <option key={t.table} value={t.table}>{t.label}</option>)}</select></label>
      <label>How it is calculated<textarea rows={6} value={sql ?? cur.sql} onChange={(e) => setSql(e.target.value)} /></label>
      <label>Why<input required value={why} onChange={(e) => setWhy(e.target.value)} placeholder="What the evidence shows" /></label>
      <Button variant="primary" type="submit" disabled={busy}>Send to the head of data to approve</Button>
    </form>
  );
}
