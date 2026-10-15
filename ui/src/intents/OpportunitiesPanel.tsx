import { useEffect, useState, type CSSProperties, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError, apiGet, apiSend } from "../api/client";
import { Button, Chip, Pill, type PillTone } from "../design";
import { HypothesisRegions } from "./HypothesisRegions";
import { ANSWERS, C, CONFIDENCE, COUNTER_LABELS, SOURCES, STATE } from "./opportunitiesCopy";

// Spec 56: the "Opportunities" panel (Ops page, Intent home), the dashed suggested card, and the opportunity drawer (backlog `?opportunity=<id>`).
// All from /api/intents/opportunities; the person is told only what the server lets them see.
interface Num { label: string; value: number | null; unit: string; restricted?: boolean; trace: { kind: string; ref: string; at: string } }
interface Evidence { id: string; text: string; kind: "supports" | "disputes"; source: { kind: string; ref: string } | null; by: string | null; at: string }
interface Answer { value: string; mark: string }
export interface Opportunity {
  id: string; title: string; state: string; noticed_by: string | null; noticed_at: string; areas: string[];
  touches: { measures: { id: string; name: string | null }[]; processes: string[]; sources: string[] };
  pattern: { text: string; periods: string[]; numbers: Num[] }; evidence: Evidence[];
  judgement: { fits: boolean; why: string; confidence: string; start_answers: Record<string, Answer> } | null;
  picked_up_by: string | null; became: string | null;
  parked: { by: string | null; at: string; reason: string; review_date: string } | null; dismissed: { by: string | null; at: string; reason: string } | null;
  history: { at: string; by: string | null; action: string; note: string | null }[];
  can: { raise: boolean; add_evidence: boolean; dispute: boolean; pick_up: boolean; park: boolean; dismiss: boolean; bring_back: boolean; think_through?: boolean; edit_hypothesis?: boolean };
  href: string; start_href: string; hypothesis_ref?: { id: string; version?: number } | null; think_href?: string;
}
interface Listing {
  opportunities: Opportunity[]; counters: Record<string, number | null> | null; can_raise: boolean;
  thresholds: { set: boolean; missing: string[]; message: string | null };
}

const TONE: Record<string, PillTone> = { noticed: "open", under_review: "open", proposed: "ok", picked_up: "signed", parked: "draft", dismissed: "restricted" };
const LIVE = ["noticed", "under_review", "proposed"];
const TRACE: Record<string, string> = { run: "Run log", alert: "Alert", week_item: "Check-in item", feed: "Feed value", range_break: "Range check", edge: "Map link" };
const DATE = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" });
const MONTH = new Intl.DateTimeFormat("en-GB", { month: "long", year: "numeric", timeZone: "UTC" });
const when = (iso: string) => {
  if (/^\d{4}-\d{2}$/.test(iso)) return MONTH.format(new Date(`${iso}-01T00:00:00Z`)); /* a period, not a day */ const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso); return Number.isNaN(d.getTime()) ? iso : DATE.format(d); };
const asWords = (s: string) => s.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
const oneLine = (s: string) => (/^.*?[.!?](\s|$)/.exec(s)?.[0] ?? s).trim();
const msg = (e: unknown) => (e instanceof ApiError && e.status !== 0 && e.status < 500 ? e.message : C.couldNot);

function weekLink(ref: string): string | null { // "<intent id>/weeks/<week key>#<item id>"
  const m = /^([\w-]+)\/weeks\/([\w-]+)/.exec(ref);
  return m ? `/centre/intent/${m[1]}/week?week=${m[2]}` : null;
}
function recordLink(kind: string, ref: string): string | null {
  if (kind === "week_item") return weekLink(ref);
  if (kind === "alert") return "/centre/build/ops";
  if (kind === "run") return "/centre/build/pipelines";
  if (kind === "map_node") return `/centre/intent/map/${encodeURIComponent(ref)}`;
  return null;
}

const wide = () => typeof window === "undefined" || !window.matchMedia || window.matchMedia("(min-width: 700px)").matches;
let areaCache: Promise<Record<string, string>> | null = null;
function useAreaNames(): Record<string, string> {
  const [names, setNames] = useState<Record<string, string>>({});
  useEffect(() => {
    let live = true;
    areaCache ??= apiGet<{ areas: { id: string; name: string }[] }>("/api/intents/areas").then((r) => Object.fromEntries(r.areas.map((a) => [a.id, a.name]))).catch(() => ({}));
    void areaCache.then((n) => { if (live) setNames(n); });
    return () => { live = false; };
  }, []);
  return names;
}
const areaLine = (o: Opportunity, names: Record<string, string>) => o.areas.map((a) => names[a] ?? "An area").join(", ");

function StateChip({ s }: { s: string }) { return <Pill tone={TONE[s] ?? "draft"}>{STATE[s] ?? s}</Pill>; }

/** The dashed card for a proposed opportunity: no state pill, never actionable on its own. Opens the drawer, or the backlog panel. */
export function SuggestedCard({ o, onOpen }: { o: Opportunity; onOpen?: (id: string) => void }) {
  const names = useAreaNames();
  const body = (
    <>
      <strong>{o.title}</strong>
      <span style={{ display: "flex", flexWrap: "wrap", gap: 6, maxWidth: "100%" }}><Chip>Initiative</Chip><span className="ds-chip" style={{ whiteSpace: "normal", maxWidth: "100%", padding: "6px 12px" }}>{C.suggested}</span></span>
      {o.areas.length > 0 && <span className="ds-soft">{areaLine(o, names)}</span>}
      {o.judgement && <span className="ds-soft">{CONFIDENCE[o.judgement.confidence] ?? o.judgement.confidence}</span>}
    </>
  );
  const style = { border: "1px dashed var(--ds-line-2, var(--ds-teal))", borderRadius: "var(--ds-radius)", padding: 14, display: "flex", flexDirection: "column", gap: 6, textAlign: "left", background: "transparent", color: "var(--ds-ink)", width: "100%", maxWidth: 280, font: "inherit", textDecoration: "none" } as const;
  return onOpen
    ? <button type="button" aria-label={`${o.title}. ${C.suggested}`} style={style} onClick={() => onOpen(o.id)}>{body}</button>
    : <Link to={o.href} aria-label={`${o.title}. ${C.suggested}`} style={style}>{body}</Link>;
}

const touched = (o: Opportunity) => [...o.touches.measures.map((m) => m.name ?? C.restricted), ...o.touches.processes.map(asWords), ...o.touches.sources.map(asWords)].join(", ");

function Row({ o, onOpen, judged }: { o: Opportunity; onOpen?: (id: string) => void; judged: boolean }) {
  const inner = (
    <>
      <StateChip s={o.state} />{wide() ? " " : <br />}<strong>{o.title}</strong>
      {touched(o) && <span className="ds-soft"> · {touched(o)}</span>}
      {o.pattern.periods.length > 0 && <span className="ds-soft"> · {o.pattern.periods.length} {o.pattern.periods.length === 1 ? "period" : "periods"}</span>}
      <span className="ds-soft"> · {o.noticed_by ?? "Someone"}, {when(o.noticed_at)} · {o.evidence.length ? `${o.evidence.length} evidence ${o.evidence.length === 1 ? "line" : "lines"}` : C.noEvidence}</span>
      {judged && o.judgement && <span className="ds-soft"> · {oneLine(o.judgement.why)}</span>}
    </>
  );
  return (
    <li style={{ listStyle: "none", padding: "6px 0", borderTop: "1px solid var(--ds-line)" }}>
      {onOpen ? <button type="button" onClick={() => onOpen(o.id)} style={{ all: "unset", cursor: "pointer", display: "block" }}>{inner}</button>
        : <Link to={o.href} style={{ color: "inherit", textDecoration: "none", display: "block" }}>{inner}</Link>}
    </li>
  );
}

/** variant "ops": every opportunity with the raise button (Ops page). variant "home": open ones only, three rows then "Show all" (Intent home). */
export function OpportunitiesPanel({ variant, onOpen, reload = 0 }: { variant: "ops" | "home"; onOpen?: (id: string) => void; reload?: number }) {
  const [data, setData] = useState<Listing | null>(null);
  const [failed, setFailed] = useState(false);
  const [raising, setRaising] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let live = true;
    apiGet<Listing>("/api/intents/opportunities").then((d) => { if (live) { setData(d); setFailed(false); } }).catch(() => { if (live) setFailed(true); });
    return () => { live = false; };
  }, [attempt, reload]);
  if (failed) return variant === "home" ? null : <section className="ds-card ds-side"><h2>{C.title}</h2><p role="alert">The opportunities could not be read. Nothing was changed. <Button onClick={() => setAttempt((n) => n + 1)}>Try again</Button></p></section>;
  if (!data) return variant === "home" ? null : <section className="ds-card ds-side" aria-busy="true"><h2>{C.title}</h2><p>Reading what the operations monitor noticed.</p></section>;

  if (variant === "home") {
    const open = data.opportunities.filter((o) => LIVE.includes(o.state));
    if (!open.length) return null; // the panel is not drawn when there are none
    const rows = (
      <>
        <ul style={{ margin: 0, padding: 0 }}>{open.slice(0, 3).map((o) => <Row key={o.id} o={o} onOpen={onOpen} judged />)}</ul>
        {open.length > 3 && <Link to="/centre/intent/backlog?status=suggested">Show all ({open.length})</Link>}
      </>
    );
    return (
      <details className="ds-card ds-side" open={wide()} aria-label={C.homeTitle}>
        <summary><strong>{wide() ? `${C.homeTitle} (${open.length})` : `Opportunities (${open.length})`}</strong></summary>
        {rows}
      </details>
    );
  }
  const stripped = data.opportunities ?? [];
  const counters = data.counters;
  return (
    <section className="ds-card ds-side" aria-label={C.title}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center", justifyContent: "space-between" }}>
        <div><h2 style={{ margin: 0 }}>{C.title}</h2><p className="ds-soft">{C.sub}</p></div>
        {data.can_raise && <Button variant="primary" onClick={() => setRaising(true)} className="opp-raise" style={wide() ? undefined : { width: "100%" }}>{C.raise}</Button>}
      </div>
      {!data.thresholds?.set && <p className="ds-soft">{data.thresholds ? C.notSet : "Not available yet"}</p>}
      {stripped.length ? <ul style={{ margin: 0, padding: 0 }}>{stripped.map((o) => <Row key={o.id} o={o} onOpen={onOpen} judged={false} />)}</ul> : <p>{C.empty}</p>}
      {stripped.length > 0 && <Link to="/centre/intent/backlog?status=suggested">{C.seeAll}</Link>}
      {counters && <p className="ds-soft" aria-label={C.counters}>{COUNTER_LABELS.map(([k, l]) => `${l}: ${k === "judged_yes_then_picked_up" && counters[k] === null ? C.fewer : counters[k] ?? "Not available yet"}`).join(" · ")}</p>}
      {raising && <RaiseSheet onClose={() => setRaising(false)} onDone={(id) => { setRaising(false); setAttempt((n) => n + 1); onOpen?.(id); }} />}
    </section>
  );
}

function Sheet({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  return (
    <div role="dialog" aria-label={title} className="ds-card ds-side" style={{ position: "fixed", inset: "10% auto auto 50%", transform: "translateX(-50%)", width: "min(520px, 94vw)", maxHeight: "80vh", overflow: "auto", zIndex: 40, boxShadow: "0 8px 40px rgba(0,0,0,.4)" }}>
      <h2 style={{ margin: 0 }}>{title}</h2>
      {children}
      <div><Button onClick={onClose}>Cancel</Button></div>
    </div>
  );
}

const field = { display: "flex", flexDirection: "column", gap: 4, fontSize: 13 } as const;
function SourcePick({ kind, ref_, setKind, setRef }: { kind: string; ref_: string; setKind: (s: string) => void; setRef: (s: string) => void }) {
  return (
    <>
      <label style={field}>Source record (optional)
        <select value={kind} onChange={(e) => setKind(e.target.value)}><option value="">None</option>{Object.entries(SOURCES).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
      </label>
      {kind && <label style={field}>Which record<input value={ref_} onChange={(e) => setRef(e.target.value)} /></label>}
    </>
  );
}
const source = (kind: string, ref: string) => (kind && ref.trim() ? { kind, ref: ref.trim() } : undefined);

function RaiseSheet({ onClose, onDone }: { onClose: () => void; onDone: (id: string) => void }) {
  const [title, setTitle] = useState(""), [noticed, setNoticed] = useState(""), [text, setText] = useState("");
  const [kind, setKind] = useState(""), [ref_, setRef] = useState("");
  const [measures, setMeasures] = useState<string[]>([]), [sources, setSources] = useState<string[]>([]);
  const [opts, setOpts] = useState<{ m: { code: string; name: string }[]; s: { source: string; title?: string }[] }>({ m: [], s: [] });
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    Promise.all([apiGet<{ measures: { code: string; name?: string; label?: string }[] }>("/api/company/feeds").catch(() => ({ measures: [] })),
      apiGet<{ pipelines: { source: string; title?: string }[] }>("/api/company/build/pipelines").catch(() => ({ pipelines: [] }))])
      .then(([f, p]) => { if (live) setOpts({ m: (f.measures ?? []).map((x) => ({ code: x.code.toUpperCase(), name: x.name ?? x.label ?? x.code })), s: p.pipelines ?? [] }); });
    return () => { live = false; };
  }, []);
  const flip = (xs: string[], set: (v: string[]) => void, v: string) => set(xs.includes(v) ? xs.filter((x) => x !== v) : [...xs, v]);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return setErr(C.titleNeeded);
    if (!measures.length && !sources.length) return setErr(C.needTouch);
    apiSend<Opportunity>("POST", "/api/intents/opportunities", {
      title, noticed, touches: { measures, sources },
      evidence: text.trim() ? { text, kind: "supports", source: source(kind, ref_) } : undefined,
    }).then((o) => onDone(o.id)).catch((x) => setErr(msg(x)));
  };
  return (
    <Sheet title={C.raise} onClose={onClose}>
      <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <label style={field}>Title<input value={title} onChange={(e) => setTitle(e.target.value)} /></label>
        <label style={field}>What you noticed<textarea rows={3} value={noticed} onChange={(e) => setNoticed(e.target.value)} /></label>
        <fieldset style={field}><legend>Measures it touches</legend>
          {opts.m.length ? opts.m.map((m) => <label key={m.code}><input type="checkbox" checked={measures.includes(m.code)} onChange={() => flip(measures, setMeasures, m.code)} /> {m.name}</label>) : <span className="ds-soft">Not available yet: no measures to pick.</span>}
        </fieldset>
        <fieldset style={field}><legend>Sources it touches</legend>
          {opts.s.length ? opts.s.map((s) => <label key={s.source}><input type="checkbox" checked={sources.includes(s.source)} onChange={() => flip(sources, setSources, s.source)} /> {s.title || asWords(s.source)}</label>) : <span className="ds-soft">Not available yet: no sources to pick.</span>}
        </fieldset>
        <label style={field}>First evidence line (optional)<textarea rows={2} value={text} onChange={(e) => setText(e.target.value)} /></label>
        <SourcePick kind={kind} ref_={ref_} setKind={setKind} setRef={setRef} />
        {err && <p role="alert" className="ds-warn">{err}</p>}
        <div><Button variant="primary" type="submit">Raise it</Button></div>
      </form>
    </Sheet>
  );
}

type SheetName = "evidence" | "dispute" | "park" | "dismiss" | null;

/** Screen C: the opportunity panel. Mounted over the backlog at `?opportunity=<id>` (file 21's frame), and on the Ops page. */
export function OpportunityDrawer({ id, onClose, onChanged }: { id: string; onClose: () => void; onChanged?: () => void }) {
  const [o, setO] = useState<Opportunity | null>(null);
  const [state, setState] = useState<"loading" | "error" | "ready">("loading");
  const [sheet, setSheet] = useState<SheetName>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [again, setAgain] = useState(0);
  const nav = useNavigate();
  const names = useAreaNames();
  useEffect(() => {
    let live = true;
    if (again === 0) setState("loading");
    apiGet<Opportunity>(`/api/intents/opportunities/${encodeURIComponent(id)}`).then((r) => { if (live) { setO(r); setState("ready"); } }).catch(() => { if (live) setState("error"); });
    return () => { live = false; };
  }, [id, again]);
  const done = (r: Opportunity) => { setO(r); setSheet(null); setErr(null); setBusy(false); onChanged?.(); };
  const send = (path: string, body: Record<string, unknown>, then?: (r: Opportunity) => void) => {
    setBusy(true);
    apiSend<Opportunity>("POST", `/api/intents/opportunities/${encodeURIComponent(id)}/${path}`, body).then((r) => { done(r); then?.(r); }).catch((e) => { setErr(msg(e)); setBusy(false); });
  };
  const frame: CSSProperties = { position: "fixed", top: 0, right: 0, bottom: 0, width: "min(480px, 100vw)", overflow: "auto", zIndex: 30, background: "var(--ds-surface)", borderLeft: "1px solid var(--ds-line)", color: "var(--ds-ink)", display: "flex", flexDirection: "column" };
  const shell = (body: ReactNode) => (
    <aside role="dialog" aria-label="Opportunity" style={frame}>
      <div style={{ padding: "12px 18px 0" }}><Button onClick={onClose}>{wide() ? "Close" : "Back"}</Button></div>
      {body}
    </aside>
  );
  if (state === "loading") return shell(<p style={{ padding: 18 }}>Reading the opportunity.</p>);
  if (state === "error" || !o) return shell(<p style={{ padding: 18 }} role="alert">We could not find that. It may have been closed, or it is not for you to see.</p>);

  const closed = o.state === "picked_up" || o.state === "dismissed";
  const actions: ReactNode[] = [];
  if (o.can.pick_up) actions.push(<Button key="pick" variant="primary" disabled={busy || !o.judgement} onClick={() => send("state", { action: "pick_up" }, (r) => nav(r.start_href))}>Pick it up</Button>);
  if (o.can.think_through) actions.push(<Button key="think" disabled={busy} onClick={() => send("state", { action: "think_through" }, (r) => nav(r.think_href ?? `/centre/intent/new?type=brainstorm&from=${r.id}`))}>Think it through first</Button>);
  if (o.can.add_evidence) actions.push(<Button key="ev" onClick={() => setSheet("evidence")}>Add evidence</Button>);
  if (o.can.dispute) actions.push(<Button key="dis" onClick={() => setSheet("dispute")}>Dispute</Button>);
  if (o.can.park) actions.push(<Button key="park" onClick={() => setSheet("park")}>Park</Button>);
  if (o.can.dismiss) actions.push(<Button key="dm" onClick={() => setSheet("dismiss")}>Dismiss</Button>);
  if (o.can.bring_back) actions.push(<Button key="back" disabled={busy} onClick={() => send("state", { action: "bring_back" })}>Bring back</Button>);
  const nobody = o.pattern.numbers.length === 0;
  const first = o.touches.measures[0]?.id;
  const trace = (n: Num) => {
    const href = n.trace.kind === "week_item" ? weekLink(n.trace.ref) : n.trace.kind === "alert" ? "/centre/build/ops" : n.trace.kind === "feed" && first ? `/centre/intent/map/measure:${first}` : n.trace.kind === "run" ? "/centre/build/pipelines" : null;
    const label = `${TRACE[n.trace.kind] ?? "Record"}, ${when(n.trace.at)}`;
    return href ? <Link to={href}>{label}</Link> : <span>{label}</span>;
  };
  return shell(
    <>
      <div style={{ padding: "8px 18px", display: "flex", flexDirection: "column", gap: 14, flex: 1 }}>
        <header>
          <h2 style={{ margin: "0 0 6px" }}>{o.title}</h2>
          <StateChip s={o.state} /> <span className="ds-soft">{o.areas.length ? areaLine(o, names) : "No area named"}</span>
        </header>
        <section aria-label="What was noticed"><h3>What was noticed</h3>
          <p className="ds-soft">{o.noticed_by ?? "Someone"}</p>
          <p>{nobody && !o.pattern.text ? C.noNumbers(o.noticed_by ?? "someone") : o.pattern.text}</p>
          {nobody ? o.pattern.text && <p className="ds-soft">{C.noNumbers(o.noticed_by ?? "someone")}</p> : (
            <ul>{o.pattern.numbers.map((n, i) => <li key={i}>{n.label}: {n.restricted || n.value === null ? C.restricted : `${n.value} ${n.unit}`} ({trace(n)})</li>)}</ul>
          )}
          <p><strong>Touches</strong></p>
          <div>{o.touches.measures.length + o.touches.processes.length + o.touches.sources.length === 0 ? C.noTouches : (
            <>
              {o.touches.measures.map((m) => m.name ? <Chip key={m.id} href={`/centre/intent/map/measure:${m.id}`}>{m.name}</Chip> : <Chip key={m.id}>{C.restricted}</Chip>)}
              {o.touches.processes.map((p) => <Chip key={p} href={`/centre/intent/map/process:${p}`}>{asWords(p)}</Chip>)}
              {o.touches.sources.map((s) => <Chip key={s} href={`/centre/intent/map/source:${s}`}>{asWords(s)}</Chip>)}
            </>)}</div>
        </section>
        <section aria-label="Evidence"><h3>Evidence</h3>
          {o.evidence.length ? <ul>{o.evidence.map((e) => {
            const href = e.source ? recordLink(e.source.kind, e.source.ref) : null;
            return <li key={e.id}>{e.text} <span className="ds-soft">({e.kind === "supports" ? "supports" : "disputes"}, {e.by ?? "someone"}, {when(e.at)}{e.source ? "; " : ""}{e.source && (href ? <Link to={href}>{SOURCES[e.source.kind] ?? asWords(e.source.kind)}</Link> : (SOURCES[e.source.kind] ?? asWords(e.source.kind)))})</span></li>;
          })}</ul> : <p>{C.noEvidenceLong}</p>}
        </section>
        <section aria-label="North's judgement"><h3>North's judgement</h3>
          {o.judgement ? <p><strong>{o.judgement.fits ? "Fits an Initiative: Yes" : "Fits an Initiative: No"}.</strong> {o.judgement.why} <span className="ds-soft">{CONFIDENCE[o.judgement.confidence] ?? o.judgement.confidence}. A suggestion from North.</span></p> : <p>{C.notJudged}</p>}
        </section>
        <HypothesisRegions oppId={o.id} hypothesisRef={o.hypothesis_ref?.id ?? null} canEdit={!!o.can.edit_hypothesis} rejected={o.state === "rejected"} onChanged={() => { setAgain((n) => n + 1); onChanged?.(); }} />
        <section aria-label="Proposed start answers"><h3>Proposed start answers</h3>
          {o.judgement && Object.keys(o.judgement.start_answers).length ? <ul>{ANSWERS.filter(([k]) => o.judgement?.start_answers[k]).map(([k, l]) => <li key={k}>{l}: {o.judgement?.start_answers[k]?.value} <Chip>{C.guessed}</Chip></li>)}</ul> : <p>{C.noAnswers}</p>}
        </section>
        {o.became && <p><Link to={`/centre/intent/${o.became}`}>Became an Initiative</Link></p>}
        {o.state === "parked" && o.parked && <p>Parked by {o.parked.by ?? "someone"}: {o.parked.reason}. Review on {when(o.parked.review_date)}.</p>}
        {o.state === "dismissed" && o.dismissed && <p>Dismissed by {o.dismissed.by ?? "someone"}: {o.dismissed.reason}.</p>}
        <p className="ds-soft">Did the measure move? {C.moved}</p>
        <section aria-label="History"><h3>History</h3>
          <ul>{o.history.map((h, i) => <li key={i}>{when(h.at)}: {asWords(h.action)} by {h.by ?? "someone"}{h.note ? `. ${h.note}` : ""}</li>)}</ul>
        </section>
      </div>
      <div style={{ position: "sticky", bottom: 0, padding: 12, background: "var(--ds-surface)", borderTop: "1px solid var(--ds-line)", display: "flex", flexWrap: "wrap", gap: 8 }}>
        {err && !sheet && <p role="alert" className="ds-warn" style={{ width: "100%", margin: 0 }}>{err}</p>}
        {closed && !actions.length && <span className="ds-soft">This opportunity is closed.</span>}
        {wide() ? actions : <>{actions[0]}{actions.length > 1 && <details><summary>More</summary>{actions.slice(1)}</details>}</>}
      </div>
      {sheet && <ActionSheet kind={sheet} busy={busy} err={err} onClose={() => { setSheet(null); setErr(null); }} send={send} />}
    </>,
  );
}

function ActionSheet({ kind, busy, err, onClose, send }: { kind: "evidence" | "dispute" | "park" | "dismiss"; busy: boolean; err: string | null; onClose: () => void; send: (path: string, body: Record<string, unknown>) => void }) {
  const [text, setText] = useState(""), [date, setDate] = useState(""), [ev, setEv] = useState<"supports" | "disputes">("supports");
  const [k, setK] = useState(""), [r, setR] = useState("");
  const title = { evidence: "Add evidence", dispute: "Dispute", park: "Park", dismiss: "Dismiss" }[kind];
  const label = kind === "evidence" ? "What the evidence is" : "Reason";
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (kind === "park" || kind === "dismiss") send("state", { action: kind, reason: text, review_date: kind === "park" ? date : undefined });
    else send("evidence", { text, kind: kind === "dispute" ? "disputes" : ev, source: source(k, r) });
  };
  return (
    <Sheet title={title} onClose={onClose}>
      <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <label style={field}>{label}<textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} required /></label>
        {kind === "evidence" && (
          <fieldset style={field}><legend>It</legend>
            <label><input type="radio" name="ev" checked={ev === "supports"} onChange={() => setEv("supports")} /> Supports the opportunity</label>
            <label><input type="radio" name="ev" checked={ev === "disputes"} onChange={() => setEv("disputes")} /> Disputes it</label>
          </fieldset>
        )}
        {kind === "park" && <label style={field}>Review date<input type="date" value={date} onChange={(e) => setDate(e.target.value)} required /></label>}
        {(kind === "evidence" || kind === "dispute") && <SourcePick kind={k} ref_={r} setKind={setK} setRef={setR} />}
        {err && <p role="alert" className="ds-warn">{err}</p>}
        <div><Button variant="primary" type="submit" disabled={busy}>{title}</Button></div>
      </form>
    </Sheet>
  );
}
