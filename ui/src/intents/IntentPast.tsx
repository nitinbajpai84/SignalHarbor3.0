import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { apiGet } from "../api/client";
import ScreenState from "../components/ScreenState";
import { Button, Chip, EmptyState, PageFrame, Pill } from "../design";
import { pastCopy as t, typeName } from "./pastCopy";
import { ProvingChip } from "./ProvingPanel";
import "./past.css";

/** Past intents (/centre/intent/past, spec 12 Screens A, B and E). Every list and count comes from GET /api/intents/past for this viewer. */

export interface NextChip { kind: string; label: string; ref: string | null }
export interface PastCard {
  id: string; type: string; title: string; purpose: string; areas: string[]; state: string; opened: string | null; closed_at: string | null;
  closed_month: string | null; organiser: string | null; people_count: number; outcome_line: string; cancel_reason: string | null;
  next: NextChip[]; rating: { avg: number; n: number } | null; tier: string; role: string | null; time_box_ends?: string | null;
  also_in?: string[]; first?: boolean;
}
interface Counters {
  per_quarter: Record<string, Record<string, number>>; outcomes_used: { used: number; closed: number };
  targets: { running: number; done: number; total: number }; cancelled: number; closed_with_nothing: number;
  average_rating: number | null; mine: number; partial: boolean;
}
export interface PastDoc {
  months: { month: string; count: number; bands: { area: string; count: number; cards: PastCard[] }[] }[];
  older: boolean; count: number; any: boolean; areas: { area: string; count: number; mine: boolean }[]; all_count: number; tagged: boolean;
  types: Record<string, number>; outcomes: Record<string, number>; counters: Counters; similar: { count: number; term: string } | null;
  running: PastCard[]; mine_count: number;
}

const KEYS = ["area", "type", "outcome", "q", "from", "to", "mine", "page"];

function toggle(list: string | null, v: string): string {
  const s = new Set((list ?? "").split(",").filter(Boolean));
  if (s.has(v)) s.delete(v); else s.add(v);
  return [...s].join(",");
}

/** The type chip on Past: the word always, 14 px, ink text so it reads at 4.5:1 on any ground; the type shows in the border. */
function PastTypeChip({ type }: { type: string }) {
  return <span className="ds-chip pi-type" data-type={type}>{typeName[type] ?? type}</span>;
}

export function PastCardView({ c }: { c: PastCard }) {
  const cancelled = c.state === "cancelled";
  return (
    <article className="ds-card pi-card" aria-label={c.title}>
      <div className="pi-card__title">
        <div className="pi-row">
          <PastTypeChip type={c.type} />
          {c.role ? <Pill tone="draft">{c.role}</Pill> : null}
          {(c as PastCard & { proving?: string | null }).proving ? <Link to={`/centre/intent/${c.id}?focus=proving`} style={{ textDecoration: "none" }}><ProvingChip state={(c as PastCard & { proving?: string | null }).proving} since={(c as PastCard & { proving_since?: string | null }).proving_since} /></Link> : null}
        </div>
        <Link to={`/centre/intent/${c.id}`}>{c.title || t.untitled}</Link>
        <div className="pi-chips">
          {c.areas.map((a) => <Chip key={a} href={`/centre/intent/past?area=${encodeURIComponent(a)}`}>{a}</Chip>)}
        </div>
        {c.also_in && c.also_in.length ? <span className="ds-muted">{t.alsoIn(c.also_in)}</span> : null}
      </div>
      <div className="pi-card__mid">
        <span>{t.dates(c.opened, c.closed_at, cancelled)}{c.rating ? ` · ${t.rating(c.rating.avg, c.rating.n)}` : ""}</span>
        <span>{t.organiser(c.organiser)}</span>
        <span>{t.people(c.people_count)}</span>
      </div>
      <div className="pi-card__out">
        {cancelled
          ? <span><Pill tone="late">{t.cancelled}</Pill> <span className="pi-clamp">{c.cancel_reason}</span></span>
          : <span className="pi-clamp">{c.outcome_line || t.noOutcome}</span>}
        <div className="pi-chips">
          {c.next.length === 0 && !cancelled ? <span className="ds-muted">{t.noNext}</span> : null}
          {c.next.map((n, i) => (n.ref && n.kind !== "backlog"
            ? <Chip key={i} href={`/centre/intent/${n.ref}`}>{n.label}</Chip>
            : n.kind === "backlog" && n.ref ? <Chip key={i} href={`/centre/intent/backlog?item=${n.ref}`}>{n.label}</Chip>
              : <span key={i} className="ds-chip pi-dim">{n.label}</span>))}
        </div>
        <Link className="ds-link" to={`/centre/intent/past/${c.id}/chain`}>{t.chain}</Link>
      </div>
    </article>
  );
}

function CounterStrip({ c }: { c: Counters }) {
  const quarters = Object.entries(c.per_quarter).sort(([a], [b]) => b.localeCompare(a));
  const q = quarters[0];
  return (
    <section aria-label={t.counters.perQuarter} className="pi-stack">
      <div className="pi-counters">
        <div className="ds-card pi-counter"><span>{t.counters.perQuarter}</span>
          <strong>{q ? `${q[0]}: ${Object.values(q[1]).reduce((a, b) => a + b, 0)}` : t.counters.noQuarter}</strong>
          {q ? <span>{Object.entries(q[1]).map(([k, n]) => `${typeName[k]} ${n}`).join(" · ")}</span> : null}</div>
        <div className="ds-card pi-counter"><span>{t.counters.used(c.outcomes_used.used, c.outcomes_used.closed)}</span>
          <strong>{c.outcomes_used.used} / {c.outcomes_used.closed}</strong><span>{t.counters.targets(c.targets.running, c.targets.done)}</span></div>
        <div className="ds-card pi-counter"><span>{t.counters.cancelled} · {t.counters.nothing}</span>
          <strong>{c.cancelled} · {c.closed_with_nothing}</strong></div>
        <div className="ds-card pi-counter"><span>{t.counters.rating} · {t.counters.mine}</span>
          <strong>{c.average_rating ?? "-"} · {c.mine}</strong>{c.average_rating === null ? <span>{t.counters.notYet}</span> : null}</div>
      </div>
      {c.partial ? <span className="ds-muted">{t.counters.partial}</span> : null}
    </section>
  );
}

export default function IntentPast() {
  const [params, setParams] = useSearchParams();
  const [doc, setDoc] = useState<PastDoc | null | "failed">(null);
  const [text, setText] = useState(params.get("q") ?? "");
  const [open, setOpen] = useState(false);
  const [shut, setShut] = useState<Set<string>>(new Set());
  const query = useMemo(() => {
    const p = new URLSearchParams();
    KEYS.forEach((k) => { const v = params.get(k); if (v) p.set(k, v); });
    return p.toString();
  }, [params]);
  const mine = params.get("mine") === "1";

  useEffect(() => {
    let live = true;
    apiGet<PastDoc>(`/api/intents/past${query ? `?${query}` : ""}`).then((d) => live && setDoc(d), () => live && setDoc("failed"));
    return () => { live = false; };
  }, [query]);
  useEffect(() => {  // a short pause before the search filters (12 open question 1: 300 ms)
    if (text === (params.get("q") ?? "")) return;
    const id = setTimeout(() => set("q", text.trim() || null), 300);
    return () => clearTimeout(id);
  }); // eslint-disable-line react-hooks/exhaustive-deps

  function set(k: string, v: string | null) {
    const p = new URLSearchParams(params);
    if (v) p.set(k, v); else p.delete(k);
    if (k !== "page") p.delete("page");
    setParams(p, { replace: true });
  }
  const flip = (key: string) => setShut((s) => { const n = new Set(s); if (n.has(key)) n.delete(key); else n.add(key); return n; });

  if (doc === null) return <PageFrame title={t.title} subline={t.subline}><ScreenState state="loading" /></PageFrame>;
  if (doc === "failed") return <PageFrame title={t.title} subline={t.subline}><ScreenState state="error" message={t.loadError} /></PageFrame>;

  const types = (params.get("type") ?? "").split(",").filter(Boolean);
  const outs = (params.get("outcome") ?? "").split(",").filter(Boolean);
  const filtered = KEYS.some((k) => k !== "page" && k !== "mine" && params.get(k));
  const words = [params.get("area"), ...types.map((x) => typeName[x]), ...outs.map((o) => t.outcomeNames[o]), params.get("q") && `'${params.get("q")}'`,
    params.get("from") && `${t.from} ${params.get("from")}`, params.get("to") && `${t.to} ${params.get("to")}`].filter(Boolean) as string[];

  const rail = (
    <div className={`pi-rail${open ? "" : " pi-rail--closed"}`} aria-label={t.filters}>
      <span className="ds-rail__group">{t.areas}</span>
      {!doc.tagged ? <p className="ds-muted">{t.noArea} <Link className="ds-link" to="/company/bring">{t.openProfile}</Link></p> : null}
      <button type="button" className="ds-rail__item" aria-current={!params.get("area")} onClick={() => set("area", null)}>{t.allAreas} ({doc.all_count})</button>
      {doc.areas.map((a) => (
        <button key={a.area} type="button" className="ds-rail__item" aria-current={params.get("area") === a.area}
          onClick={() => set("area", params.get("area") === a.area ? null : a.area)}>{a.area} ({a.count})</button>
      ))}
      <span className="ds-rail__group">{t.types}</span>
      <div className="pi-chips" role="group" aria-label={t.types}>
        {Object.entries(doc.types).map(([k, n]) => (
          <span key={k} className={n ? "" : "pi-dim"}><Chip tone={types.includes(k) ? "active" : "default"} onClick={() => set("type", toggle(params.get("type"), k) || null)}>{typeName[k]} {n}</Chip></span>
        ))}
      </div>
      <span className="ds-rail__group">{t.outcomes}</span>
      <div className="pi-chips" role="group" aria-label={t.outcomes}>
        {Object.entries(doc.outcomes).map(([k, n]) => (
          <span key={k} className={n ? "" : "pi-dim"}><Chip tone={outs.includes(k) ? "active" : "default"} onClick={() => set("outcome", toggle(params.get("outcome"), k) || null)}>{t.outcomeNames[k]} {n}</Chip></span>
        ))}
      </div>
      <label>{t.from}<input type="month" value={params.get("from") ?? ""} onChange={(e) => set("from", e.target.value || null)} /></label>
      <label>{t.to}<input type="month" value={params.get("to") ?? ""} onChange={(e) => set("to", e.target.value || null)} /></label>
      <label className="pi-row" style={{ flexDirection: "row" }}>
        <input type="checkbox" role="switch" checked={mine} onChange={(e) => set("mine", e.target.checked ? "1" : null)} /> {t.onlyMine}
      </label>
      {filtered ? <Button onClick={() => { setText(""); setParams(mine ? { mine: "1" } : {}, { replace: true }); }}>{t.clear}</Button> : null}
    </div>
  );

  let lastYear = "";
  return (
    <PageFrame title={t.title} subline={t.subline} rail={rail}
      actions={<span className="pi-filters-btn"><Button onClick={() => setOpen(!open)}>{open ? t.close : t.filters}</Button></span>}>
      <div className="pi-stack">
        <input className="pi-search" type="search" aria-label={t.search} placeholder={t.search} value={text} onChange={(e) => setText(e.target.value)} />
        {doc.similar ? (
          <div className="ds-card pi-agent pi-row">
            <span>{t.similar(doc.similar.count, doc.similar.term)}</span>
            {params.get("area") ? <button type="button" className="ds-link" style={{ background: "none", border: 0, cursor: "pointer" }} onClick={() => set("area", null)}>{t.similarAll}</button> : null}
          </div>
        ) : null}
        {doc.any ? <CounterStrip c={doc.counters} /> : null}
        {mine && doc.running.length ? (
          <section className="pi-stack" aria-label={t.stillRunning}>
            <h2 className="pi-band" style={{ cursor: "default" }}>{t.stillRunning}</h2>
            {doc.running.map((c) => (
              <article key={c.id} className="ds-card pi-card" aria-label={c.title}>
                <div className="pi-card__title"><div className="pi-row"><PastTypeChip type={c.type} />{c.role ? <Pill tone="draft">{c.role}</Pill> : null}</div>
                  <Link to={`/centre/intent/${c.id}`}>{c.title || t.untitled}</Link></div>
                <div className="pi-card__mid"><span>{t.running(c.time_box_ends)}</span></div>
              </article>
            ))}
          </section>
        ) : null}
        {!doc.any && !(mine && doc.running.length) ? (
          mine
            ? <EmptyState title={t.mineEmptyTitle} lines={[t.mineEmptyLine]} links={[{ label: t.seeRunning, href: "/centre/intent" }]} />
            : <EmptyState title={t.emptyTitle} lines={[t.emptyLine]} links={[{ label: t.start, href: "/centre/intent" }]} />
        ) : null}
        {doc.any && doc.count === 0 ? (
          params.get("from") || params.get("to")
            ? <div className="ds-card ds-empty"><strong className="ds-empty__title">{t.noRange}</strong>
                <Button onClick={() => setParams((p) => { const n = new URLSearchParams(p); n.delete("from"); n.delete("to"); return n; }, { replace: true })}>{t.clearDates}</Button></div>
            : <div className="ds-card ds-empty"><strong className="ds-empty__title">{t.noMatch}</strong><p>{t.activeFilters(words)}</p>
                <Button onClick={() => { setText(""); setParams({}, { replace: true }); }}>{t.clear}</Button></div>
        ) : null}
        {doc.months.map((m) => {
          const year = m.month.slice(0, 4);
          const head = mine && year !== lastYear ? <h2 className="pi-band" style={{ cursor: "default", fontSize: 14 }}>{year}</h2> : null;
          lastYear = year;
          return (
            <section key={m.month} className="pi-stack" aria-label={t.month(m.month)}>
              {head}
              <button type="button" className="pi-month" aria-expanded={!shut.has(m.month)} onClick={() => flip(m.month)}>
                {t.month(m.month)} <span className="ds-muted">{m.count}</span>
              </button>
              {shut.has(m.month) ? null : m.bands.map((b) => (
                <div key={b.area} className="pi-stack">
                  <button type="button" className="pi-band" aria-expanded={!shut.has(`${m.month}/${b.area}`)} onClick={() => flip(`${m.month}/${b.area}`)}>
                    {b.area} · {b.count}
                  </button>
                  {shut.has(`${m.month}/${b.area}`) ? null : b.cards.map((c) => <PastCardView key={`${b.area}-${c.id}`} c={c} />)}
                </div>
              ))}
            </section>
          );
        })}
        {doc.older ? <Button onClick={() => set("page", String(Number(params.get("page") ?? 1) + 1))}>{t.older}</Button> : null}
      </div>
    </PageFrame>
  );
}
