import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ApiError, apiGet, apiSend } from "../api/client";
import { Button } from "../design";
import ProvingReview from "./ProvingReview";
import WeeklyReport, { FigureCard, SeriesChart, SeriesTable, VerdictPill, WordPill, fmtDate, msg, weekName } from "./WeeklyReport";
import { P, type Proving } from "./provingCopy";
import "./proving.css";

// Spec 58 Screen A: the Proving panel on a closed Initiative's stage view, plus the chip, the rules card (Screen D) and the receipt line (Screen E).
// Mount: <ProvingPanel intentId=... /> under the header of a closed Initiative. It draws nothing when the intent has no Proving record.
// ?focus=proving (default), ?week=<week key> shows one report, ?focus=review shows the review.

const LIVE = ["waiting", "proving", "reviewing"];

/** The chip beside "Closed" on the header, the home card and the Past row. `since` is the start date when known. */
export function ProvingChip({ state, since, onClick }: { state: string | null | undefined; since?: string | null; onClick?: () => void }) {
  if (!state) return null;
  const text = state === "waiting" ? P.chip.waiting : state === "proved" ? P.chip.proved : state === "returned" ? P.chip.returned : state === "stopped" ? P.chip.stopped : P.chip.proving(since ? fmtDate(since) : "the release");
  const label = state === "proving" || state === "reviewing" ? (since ? text : "Proving") : text;
  return onClick
    ? <button type="button" className="pv__chip" data-state={state} onClick={onClick}>{label}</button>
    : <span className="pv__chip pv__chip--static" data-state={state}>{label}</span>;
}

/** Screen E, the "What came of this" line on the item a voice raised. `became` comes from the item's own record. */
export function CameOfThis({ became }: { became: { title: string; chip: string; href: string | null } | null | undefined }) {
  if (!became) return null;
  const t = P.came(became.title, became.chip);
  return <p className="pv__soft">{became.href ? <Link to={became.href}>{t}</Link> : t}</p>;
}

function StartForm({ intentId, current, done }: { intentId: string; current: string; done: () => void }) {
  const [at, setAt] = useState(current.slice(0, 10));
  const [why, setWhy] = useState("");
  const [err, setErr] = useState("");
  async function save(e: FormEvent) {
    e.preventDefault();
    if (!at || !why.trim()) { setErr(P.startNeeded); return; }
    try { await apiSend("POST", `/api/intents/${intentId}/proving/start`, { at, reason: why.trim() }); done(); } catch (x) { setErr(msg(x)); }
  }
  return (
    <form className="pv__card ds-card" onSubmit={save} aria-label={P.changeStart}>
      <label className="pv__field">{P.changeStart}<input type="date" value={at} onChange={(e) => setAt(e.target.value)} /></label>
      <label className="pv__field">{P.startReason}<textarea value={why} onChange={(e) => setWhy(e.target.value)} /></label>
      {err && <p className="pv__err" role="alert">{err}</p>}
      <div className="pv__row"><Button variant="primary" type="submit">{P.saveStart}</Button><Button onClick={done}>Cancel</Button></div>
    </form>
  );
}

const wide = () => typeof window === "undefined" || !window.matchMedia || window.matchMedia("(min-width: 700px)").matches;

function Overview({ intentId, p, setParams, reload }: { intentId: string; p: Proving; setParams: (q: Record<string, string>) => void; reload: () => void }) {
  const [editing, setEditing] = useState(false);
  const latestRef = useRef<HTMLDivElement>(null);
  const r = p.latest;
  const m = p.measure?.name ?? "the measure";
  const h = p.hypothesis;
  const reviewDue = p.state === "reviewing" || (p.review_date !== null && p.review_date <= new Date().toISOString().slice(0, 10) && LIVE.includes(p.state));
  const canOpenReview = reviewDue && (p.can.review || p.can.confirm_review);
  const firstConfirmed = p.reports.some((x) => x.state === "confirmed");
  const { proving_min_periods: need, counter_periods: check } = p.rules;
  return (
    <section className="pv" aria-label={P.title}>
      <div className="pv__row">
        <h2>{P.title}</h2>
        <ProvingChip state={p.state} since={p.start?.at} onClick={() => latestRef.current?.scrollIntoView?.({ behavior: "smooth" })} />
      </div>
      <div className="pv__cols">
        <div className="pv__main">
          <div className="pv__card ds-card">
            <h3>{P.hypothesisHead}</h3>
            {h ? (
              <>
                <p style={{ margin: 0 }}>{h.belief}</p>
                <p className="pv__soft">{[h.lens, h.measure?.name, h.target ? `Target ${h.target.value}${h.target.unit ? ` ${h.target.unit}` : ""}${h.target_by ? ` by ${fmtDate(h.target_by)}` : ""}` : null, p.review_date ? `Review ${fmtDate(p.review_date)}` : null, P.frozen(h.version)].filter(Boolean).join(" · ")}</p>
                {h.href && <Link className="pv__link" to={h.href}>{P.openHypothesis}</Link>}
              </>
            ) : <p className="pv__soft">{P.noHypothesis}</p>}
          </div>
          <div className="pv__card ds-card">
            <p style={{ margin: 0 }}><strong>North.</strong> {p.start
              ? P.live(fmtDate(p.start.at), p.start.from === "release" ? P.fromRelease(p.start.who, fmtDate(p.start.at)) : p.start.from === "go_live" ? P.fromGoLive(fmtDate(p.start.at)) : P.fromClosure(fmtDate(p.start.at)))
              : P.waitingLine(m)}</p>
            {p.start?.changed && <p className="pv__soft">{P.startChanged(p.start.changed.by, p.start.changed.reason)}</p>}
            {p.can.change_start && !firstConfirmed && p.start && !editing && <div><Button onClick={() => setEditing(true)}>{P.changeStart}</Button></div>}
            {editing && p.start && <StartForm intentId={intentId} current={p.start.at} done={() => { setEditing(false); reload(); }} />}
          </div>
          <div className="pv__card ds-card" ref={latestRef} id="pv-latest">
            <h3>{P.latest}</h3>
            {r ? (
              <>
                <div className="pv__row"><VerdictPill v={r.changed_verdict?.to ?? r.verdict} /><span className="pv__soft">{weekName(r.week_key)} · {r.state === "confirmed" && r.confirmed_by ? P.confirmedBy(r.confirmed_by, fmtDate(r.confirmed_at)) : P.state[r.state]}</span></div>
                <div className="pv__stats">
                  <FigureCard label={P.before} f={r.before} show={r.figures} unit={p.measure?.unit} missing={r.missing?.length ? r.missing.join("; ") : "no baseline was frozen"} />
                  <FigureCard label={P.now} f={r.now} show={r.figures} unit={p.measure?.unit} missing={r.missing?.length ? r.missing.join("; ") : "no period has landed since the start"} />
                  <FigureCard label={P.target} f={r.target} show={r.figures} unit={p.measure?.unit} missing={r.missing?.length ? r.missing.join("; ") : "no target was set"} />
                </div>
                <p className="pv__soft">{r.rule} {r.confidence_word ?? P.confidence[r.confidence]}.</p>
                <div><Button onClick={() => setParams({ week: r.week_key })}>Open this report</Button></div>
              </>
            ) : <p className="pv__soft">{p.state === "waiting" ? P.waitingLine(m) : P.firstReport}</p>}
          </div>
          <div className="pv__card ds-card">
            <h3>{P.series}</h3>
            {r && r.figures && r.series.length > 0
              ? (wide() ? <SeriesChart r={r} target={r.target?.value ?? null} label={`${m} since the start`} /> : <SeriesTable r={r} unit={r.now?.unit ?? ""} />)
              : <p className="pv__soft">{r && !r.figures ? P.noFigures : P.chartNone(m)}</p>}
          </div>
          <div className="pv__card ds-card">
            <h3>{P.earlier}</h3>
            {p.reports.length ? <ul className="pv__list">{p.reports.map((x) => (
              <li key={x.week_key}><a className="pv__link" href={`?week=${encodeURIComponent(x.week_key)}`} onClick={(e) => { e.preventDefault(); setParams({ week: x.week_key }); }}>{weekName(x.week_key)}</a> <WordPill w={x.verdict_word} /> <span className="pv__soft">{P.state[x.state]}</span></li>
            ))}</ul> : <p className="pv__soft">{P.noReports}</p>}
          </div>
          {canOpenReview && <div className="pv__bar"><Button variant="primary" onClick={() => setParams({ focus: "review" })}>{P.openReview}</Button></div>}
        </div>
        <aside className="pv__aside">
          <details className="pv__card ds-card" open={wide()}>
            <summary><strong>{P.how}</strong></summary>
            {need === null || check === null ? <p className="pv__soft">{P.howNotSet}</p> : <p className="pv__soft">{P.periodsNeed(need)} {P.periodsCheck(check)}</p>}
            <ul className="pv__list">{P.howRules.map((x) => <li key={x}>{x}</li>)}</ul>
          </details>
          <details className="pv__card ds-card" open={wide()}>
            <summary><strong>{P.hears}</strong></summary>
            {p.receipts && (p.receipts.named > 0 || p.receipts.anonymous > 0 || p.sponsor)
              ? <p className="pv__soft">{P.hearsLine(p.sponsor, p.receipts.named, p.receipts.anonymous)}</p>
              : <p className="pv__soft">{P.hearsNone}</p>}
          </details>
        </aside>
      </div>
    </section>
  );
}

export default function ProvingPanel({ intentId }: { intentId: string }) {
  const [params, setParams] = useSearchParams();
  const [p, setP] = useState<Proving | null>(null);
  const [gone, setGone] = useState(false);
  const [failed, setFailed] = useState(false);
  const [n, setN] = useState(0);
  useEffect(() => {
    let live = true;
    apiGet<Proving>(`/api/intents/${intentId}/proving`).then((d) => { if (live) { setP(d); setFailed(false); setGone(false); } })
      .catch((e: unknown) => { if (!live) return; if (e instanceof ApiError && (e.status === 404 || e.status === 403)) setGone(true); else setFailed(true); });
    return () => { live = false; };
  }, [intentId, n]);
  const go = useCallback((q: Record<string, string>) => { const next = new URLSearchParams(params); ["week", "focus"].forEach((k) => next.delete(k)); Object.entries(q).forEach(([k, v]) => next.set(k, v)); setParams(next); }, [params, setParams]);
  const reload = () => setN((x) => x + 1);
  if (gone) return null; // no Proving record, or not for this viewer: the panel is hidden
  if (failed) return <section className="pv"><p role="alert">{P.unreadable} <Button onClick={reload}>{P.retry}</Button></p></section>;
  if (p && !Array.isArray((p as { reports?: unknown }).reports)) return null; // no Proving yet (the read answers without reports): hidden, never a crash
  if (!p) return <section className="pv" aria-busy="true"><p>Reading Proving.</p></section>;
  const week = params.get("week");
  if (week) return <WeeklyReport intentId={intentId} weekKey={week} proving={p} goWeek={(k) => go({ week: k })} onBack={() => go({})} onChanged={reload} />;
  if (params.get("focus") === "review") return <ProvingReview intentId={intentId} proving={p} onBack={() => go({})} onChanged={() => { reload(); go({}); }} />;
  return <Overview intentId={intentId} p={p} setParams={go} reload={reload} />;
}

/** Screen D: the Proving rules card on the admin Defaults tab. counter_periods is shown read only; it is set on the radar thresholds card. */
export function ProvingRulesCard() {
  const [v, setV] = useState<{ min: number | null; counter: number | null } | null>(null);
  const [text, setText] = useState("");
  const [note, setNote] = useState("");
  useEffect(() => {
    apiGet<Record<string, unknown>>("/api/intents/settings").then((s) => {
      const pr = (s.proving ?? {}) as Record<string, unknown>;
      const min = typeof pr.proving_min_periods === "number" ? pr.proving_min_periods : null;
      setV({ min, counter: typeof pr.counter_periods === "number" ? pr.counter_periods : null }); setText(min === null ? "" : String(min));
    }).catch(() => setV({ min: null, counter: null }));
  }, []);
  if (!v) return <section className="ds-card pv__card" aria-busy="true"><h2>{P.rules.title}</h2></section>;
  async function save() {
    if (!/^[1-9]\d*$/.test(text)) { setNote(P.rules.bad); return; }
    try { await apiSend("PUT", "/api/intents/settings", { proving: { proving_min_periods: Number(text) } }); setNote(P.rules.saved); } catch { setNote(P.couldNot); }
  }
  return (
    <section className="ds-card pv__card" aria-label={P.rules.title}>
      <h2 style={{ margin: 0, fontSize: 18 }}>{P.rules.title}</h2>
      <label className="pv__field">{P.rules.min}<input inputMode="numeric" value={text} onChange={(e) => { setText(e.target.value); setNote(""); }} style={{ maxWidth: 120 }} /></label>
      {v.min === null && <p className="pv__soft">{P.rules.notSet}</p>}
      <p style={{ margin: 0 }}>{P.rules.counter}: <strong>{v.counter ?? "Not set"}</strong> <Link className="pv__link" to="/centre/intent/admin?tab=defaults">{P.rules.linkRadar}</Link></p>
      <div className="pv__row"><Button variant="primary" onClick={() => void save()}>{P.rules.save}</Button>{note && <span role="status" className="pv__soft">{note}</span>}</div>
    </section>
  );
}
