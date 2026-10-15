import { useEffect, useState, type FormEvent } from "react";

import { ApiError, apiGet, apiSend } from "../api/client";
import { Button, Pill, type PillTone } from "../design";
import { P, type Figure, type Proving, type Report, type Trace, type Verdict } from "./provingCopy";
import "./proving.css";

// Spec 58 Screen B: one weekly uplift report. Before, Now, Target, series, attribution notes, the verdict and the organiser's actions.
const DATE = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const MONTH = new Intl.DateTimeFormat("en-GB", { month: "long", year: "numeric", timeZone: "UTC" });
export const fmtDate = (iso: string | null | undefined): string => {
  if (!iso) return "";
  if (/^\d{4}-\d{2}$/.test(iso)) return MONTH.format(new Date(`${iso}-01T00:00:00Z`));
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
  return Number.isNaN(d.getTime()) ? iso : DATE.format(d);
};
export const weekName = (k: string) => { const w = /^(\d{4})-W(\d{2})$/.exec(k); return /^\d{4}-\d{2}-\d{2}$/.test(k) ? P.weekOf(fmtDate(k)) : w ? `Week ${Number(w[2])}, ${w[1]}` : k; };
export const msg = (e: unknown) => (e instanceof ApiError && e.status !== 0 && e.status < 500 ? e.message : P.couldNot);
export const VERDICT_TONE: Record<Verdict, PillTone> = { working: "ok", partly: "open", not: "failed", too_early: "draft" };
export const VerdictPill = ({ v }: { v: Verdict }) => <Pill tone={VERDICT_TONE[v] ?? "draft"}>{P.verdict[v] ?? v}</Pill>;
const WORD_TONE: Record<string, PillTone> = { Working: "ok", Partly: "open", "Not working": "failed", "Too early": "draft" };
export const WordPill = ({ w }: { w: string }) => <Pill tone={WORD_TONE[w] ?? "draft"}>{w}</Pill>;
export const traceLabel = (t: Trace | null | undefined) => (t ? (t.kind === "record" || t.kind === "alert" || t.kind === "intent" ? t.ref ?? P.trace.record : P.trace[t.kind] ?? "From a record") : null);
const fmtN = (v: number) => new Intl.NumberFormat("en-GB", { maximumFractionDigits: 2 }).format(v);
export const num = (f: Figure, unit?: string | null) => `${new Intl.NumberFormat("en-GB", { maximumFractionDigits: 2 }).format(f.value as number)}${f.unit || unit ? ` ${f.unit || unit}` : ""}`;
const span = (p: unknown): string | null => Array.isArray(p) ? (p.length > 1 ? `${fmtDate(String(p[0]))} to ${fmtDate(String(p[p.length - 1]))}` : p.length ? fmtDate(String(p[0])) : null) : typeof p === "number" ? `${p} periods` : null;

export function FigureCard({ label, f, show, missing, unit }: { label: string; f: Figure | null; show: boolean; missing: string; unit?: string | null }) {
  let body: string;
  if (!show) body = P.noFigures;
  else if (!f || f.value === null) body = P.figureMissing(missing);
  else body = num(f, unit);
  const sub = show && f && f.value !== null ? [span(f.periods), f.period ? fmtDate(f.period) : null, f.by ? `by ${fmtDate(f.by)}` : null].filter(Boolean).join(", ") : "";
  const tr = show ? traceLabel(f?.trace) : null;
  return (
    <div className="pv__stat">
      <span className="pv__soft">{label}</span>
      <strong>{body}</strong>
      {sub && <span className="pv__soft">{sub}</span>}
      {tr && <span className="pv__soft">{tr}</span>}
    </div>
  );
}

/** The measure's series with its usual range, target and start; a plain SVG that scales to the column. */
export function SeriesChart({ r, target, label }: { r: Report; target: number | null; label: string }) {
  const pts = r.series;
  const vals = [...pts.map((p) => p.value), ...(target !== null ? [target] : []), ...(r.normal_range ? [r.normal_range.low, r.normal_range.high] : [])];
  const lo = Math.min(...vals), hi = Math.max(...vals), W = 600, H = 200, PX = 28, top = 14, bot = 30;
  const y = (v: number) => H - bot - ((v - lo) / (hi - lo || 1)) * (H - bot - top);
  const step = pts.length > 1 ? (W - 2 * PX) / (pts.length - 1) : 0;
  const x = (i: number) => PX + i * step;
  const start = r.start_period ? pts.findIndex((p) => p.period >= (r.start_period as string)) : -1;
  return (
    <svg className="pv__chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
      {r.normal_range && <rect className="band" x={PX} width={W - 2 * PX} y={y(r.normal_range.high)} height={Math.max(2, y(r.normal_range.low) - y(r.normal_range.high))}><title>Usual range</title></rect>}
      {target !== null && <line className="tgt" x1={PX} x2={W - PX} y1={y(target)} y2={y(target)}><title>Target</title></line>}
      {start >= 0 && <line className="st" x1={x(start)} x2={x(start)} y1={top} y2={H - bot}><title>The start</title></line>}
      <polyline className="ln" points={pts.map((p, i) => `${x(i)},${y(p.value)}`).join(" ")} />
      {pts.map((p, i) => <g key={p.period}><circle className="dot" cx={x(i)} cy={y(p.value)} r={3}><title>{`${fmtDate(p.period)}: ${p.value}`}</title></circle>{(pts.length < 9 || i % 2 === 0) && <text x={x(i)} y={H - 8} textAnchor="middle">{p.period.slice(-5)}</text>}</g>)}
    </svg>
  );
}

export function SeriesTable({ r, unit }: { r: Report; unit: string }) {
  const base = r.before?.value ?? null;
  return (
    <table className="pv__table">
      <caption className="pv__soft" style={{ textAlign: "left" }}>{P.seriesTable}</caption>
      <thead><tr><th scope="col">{P.period}</th><th scope="col">{P.value}</th>{base !== null && <th scope="col">{P.fromBefore}</th>}</tr></thead>
      <tbody>{r.series.map((p) => <tr key={p.period}><td>{fmtDate(p.period)}</td><td>{fmtN(p.value)}{unit ? ` ${unit}` : ""}</td>{base !== null && <td>{p.change == null ? "" : (p.change > 0 ? "+" : "") + fmtN(p.change)}</td>}</tr>)}</tbody>
    </table>
  );
}

function NoteForm({ intentId, week, done }: { intentId: string; week: string; done: () => void }) {
  const [text, setText] = useState("");
  const [rec, setRec] = useState("");
  const [none, setNone] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  async function save(e: FormEvent) {
    e.preventDefault();
    if (!text.trim() || (!none && !rec.trim())) { setErr(P.noteNeeded); return; }
    setBusy(true); setErr("");
    try { await apiSend("POST", `/api/intents/${intentId}/proving/reports/${encodeURIComponent(week)}/notes`, { text: text.trim(), trace: none ? "No record" : rec.trim() }); done(); } catch (x) { setErr(msg(x)); setBusy(false); }
  }
  return (
    <form className="pv__card ds-card" onSubmit={save} aria-label={P.addNote}>
      <label className="pv__field">{P.noteText}<textarea value={text} onChange={(e) => setText(e.target.value)} /></label>
      <label className="pv__field">{P.noteRecord}<input value={rec} disabled={none} onChange={(e) => setRec(e.target.value)} /></label>
      <label className="pv__row" style={{ minHeight: 44 }}><input type="checkbox" checked={none} onChange={(e) => setNone(e.target.checked)} /> {P.noRecord}</label>
      {err && <p className="pv__err" role="alert">{err}</p>}
      <div className="pv__row"><Button variant="primary" type="submit" disabled={busy}>{P.saveNote}</Button><Button onClick={done}>Cancel</Button></div>
    </form>
  );
}

function ChangeForm({ r, done, send }: { r: Report; done: () => void; send: (b: Record<string, unknown>) => Promise<void> }) {
  const [v, setV] = useState<Verdict>(r.verdict);
  const [why, setWhy] = useState("");
  const [err, setErr] = useState("");
  return (
    <form className="pv__card ds-card" aria-label={P.change} onSubmit={(e) => { e.preventDefault(); if (v === r.verdict || !why.trim()) { setErr(P.changeNeeded); return; } void send({ verdict: v, reason: why.trim() }); }}>
      <label className="pv__field">{P.newVerdict}<select value={v} onChange={(e) => setV(e.target.value as Verdict)}>{(Object.keys(P.verdict) as Verdict[]).map((k) => <option key={k} value={k}>{P.verdict[k]}</option>)}</select></label>
      <label className="pv__field">{P.changeReason}<textarea value={why} onChange={(e) => setWhy(e.target.value)} /></label>
      {err && <p className="pv__err" role="alert">{err}</p>}
      <div className="pv__row"><Button variant="primary" type="submit">{P.saveChange}</Button><Button onClick={done}>Cancel</Button></div>
    </form>
  );
}

export default function WeeklyReport({ intentId, weekKey, proving, goWeek, onBack, onChanged }: {
  intentId: string; weekKey: string; proving: Proving; goWeek: (k: string) => void; onBack: () => void; onChanged: () => void;
}) {
  const [r, setR] = useState<Report | null>(null);
  const [failed, setFailed] = useState(false);
  const [mode, setMode] = useState<"" | "note" | "change">("");
  const [err, setErr] = useState("");
  const [n, setN] = useState(0);
  useEffect(() => {
    let live = true;
    apiGet<Report>(`/api/intents/${intentId}/proving/reports/${encodeURIComponent(weekKey)}`).then((d) => { if (live) { setR(d); setFailed(false); } }).catch(() => { if (live) setFailed(true); });
    return () => { live = false; };
  }, [intentId, weekKey, n]);
  if (failed) return <section className="pv"><p role="alert">{P.unreadable} <Button onClick={() => setN(n + 1)}>{P.retry}</Button></p><Button onClick={onBack}>{P.back}</Button></section>;
  if (!r) return <section className="pv" aria-busy="true"><p>Reading the report.</p></section>;
  const measure = proving.measure?.name ?? r.measure?.name ?? "the measure";
  const can = r.can ?? { confirm: false, add_note: false };
  const open = r.state === "drafted" && proving.state !== "proved" && proving.state !== "returned" && proving.state !== "stopped";
  const settled = proving.state === "proved" || proving.state === "returned" || proving.state === "stopped";
  const missing = (what: string) => (r.missing && r.missing.length ? r.missing.join("; ") : what);
  const reload = () => { setMode(""); setN((x) => x + 1); onChanged(); };
  async function confirm(body: Record<string, unknown>) {
    setErr("");
    try { await apiSend("POST", `/api/intents/${intentId}/proving/reports/${encodeURIComponent(weekKey)}/confirm`, body); reload(); } catch (x) { setErr(msg(x)); }
  }
  const unit = r.measure?.unit ?? r.before?.unit ?? "";
  return (
    <section className="pv" aria-label={weekName(r.week_key)}>
      <div className="pv__row"><Button onClick={onBack}>{P.back}</Button><h2>{weekName(r.week_key)}</h2></div>
      <div className="pv__cols">
        <div className="pv__main">
          {r.state === "no_change" && <p className="pv__card ds-card" role="status"><strong>North.</strong> {P.noChange(measure)}</p>}
          <div className="pv__stats">
            <FigureCard label={P.before} f={r.before} show={r.figures} unit={r.measure?.unit} missing={missing("no baseline was frozen")} />
            <FigureCard label={P.now} f={r.now} show={r.figures} unit={r.measure?.unit} missing={missing("no period has landed since the start")} />
            <FigureCard label={P.target} f={r.target} show={r.figures} unit={r.measure?.unit} missing={missing("no target was set")} />
          </div>
          <div className="pv__card ds-card">
            <h3>{P.series}</h3>
            {r.figures && r.series.length > 0 ? (<><SeriesChart r={r} target={r.target?.value ?? null} label={`${measure} since the start`} /><SeriesTable r={r} unit={unit} /></>)
              : <p className="pv__soft">{r.figures ? "No period since the start." : P.noFigures}</p>}
          </div>
          <div className="pv__card ds-card">
            <h3>{P.notes}</h3>
            {r.figures ? ((r.notes ?? []).length ? <ul className="pv__list">{(r.notes ?? []).map((x, i) => <li key={i}>{x.text}<br /><span className="pv__soft">{x.by}, {fmtDate(x.at)}. {traceLabel(x.trace) ?? P.noRecord}</span></li>)}</ul> : <p className="pv__soft">{P.noNotes}</p>) : <p className="pv__soft">{P.noFigures}</p>}
            {can.add_note && !settled && mode !== "note" && <div><Button onClick={() => setMode("note")}>{P.addNote}</Button></div>}
            {mode === "note" && <NoteForm intentId={intentId} week={weekKey} done={reload} />}
          </div>
          <div className="pv__card ds-card">
            <div className="pv__row"><VerdictPill v={r.changed_verdict?.to ?? r.verdict} /><strong>{P.verdictBy}</strong><span className="pv__soft">{r.confidence_word ?? P.confidence[r.confidence] ?? ""}</span></div>
            <p style={{ margin: 0 }}>{r.rule}</p>
            {r.changed_verdict && <p className="pv__soft">{P.changed(P.verdict[r.changed_verdict.from], r.confirmed_by ?? "The organiser", P.verdict[r.changed_verdict.to], r.changed_verdict.reason)}</p>}
            <p className="pv__soft">{r.state === "confirmed" && r.confirmed_by ? P.confirmedBy(r.confirmed_by, fmtDate(r.confirmed_at)) : P.state[r.state]}</p>
          </div>
          {mode === "change" && <ChangeForm r={r} done={() => setMode("")} send={confirm} />}
          {err && <p className="pv__err" role="alert">{err}</p>}
          {open && can.confirm && r.state !== "no_change" && mode !== "change" && (
            <div className="pv__bar pv__bar--sticky"><Button variant="primary" onClick={() => void confirm({})}>{P.confirm}</Button><Button onClick={() => setMode("change")}>{P.change}</Button></div>
          )}
        </div>
        <aside className="pv__aside">
          <div className="pv__card ds-card">
            <h3>{P.earlier}</h3>
            <label className="pv__field"><span className="pv__soft">{P.earlier}</span>
              <select aria-label={P.earlier} value={weekKey} onChange={(e) => goWeek(e.target.value)}>{proving.reports.map((x) => <option key={x.week_key} value={x.week_key}>{weekName(x.week_key)}, {x.verdict_word}</option>)}</select>
            </label>
          </div>
        </aside>
      </div>
    </section>
  );
}
