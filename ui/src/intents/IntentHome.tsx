import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";

import { apiGet, Refused } from "../api/client";
import ScreenState, { type ScreenStateName } from "../components/ScreenState";
import { Button, Chip, Footnote, PageFrame, SideCard, StatCard, StatGrid, Strip } from "../design";
import { governedBars } from "../pages/CentrePage";
import { CentreMeasures } from "./CentreMeasures";
import { OpportunitiesPanel } from "./OpportunitiesPanel";
import PackSuggestions from "./PackSuggestions";
import YourTurnStrip from "./YourTurnStrip";
import IntentCard, { TypeChip, type HomeCard } from "./IntentCard";
import { ProvingChip } from "./ProvingPanel";
import { RadarView } from "./RadarView";
import { R } from "./radarCopy";
import { homeCopy as t } from "./intentHomeCopy";

// The Intent Centre home (spec 04) with first run and the no-areas panel (spec 18). One call, GET /api/intents/home; the server decides
// what the viewer may see. Filters live in the URL; the Mine / All choice is also kept in browser storage as a convenience.

interface Lane { id: string; name: string; cards: { id: string; also_in: string | null }[] }
interface Line { id: string; what: string; title: string; days: string; days_warn: boolean; href: string }
interface PastRow { id: string; type: string; type_name: string; state: string; title: string; date: string | null; one_liner: string; href: string }
interface Counter { key: string; label: string; value: string; note: string; ids: string[] }
interface Suggestions {
  state: "ok" | "no_pack" | "not_yet"; line?: string; heading?: string; strip?: string; source?: string;
  items?: { id: string; type: string; type_name: string; title: string; purpose: string }[];
}
interface TypeRow { type: string; name: string; line: string; chip: string }
interface Earlier { line: string; walls: { label: string; href: string }[]; charters: { label: string; href: string }[] }
export interface HomeData {
  screen: "home" | "first_run" | "no_areas";
  subline: string;
  cards: HomeCard[];
  lanes: Lane[];
  your_turn: Line[];
  past: PastRow[];
  past_total: number;
  counters: Counter[];
  viewer: { name: string; first_name: string; email: string; admin: boolean; may_start: boolean; governed: boolean; opportunities: boolean; areas: { id: string; name: string }[] };
  first_run: { opening: string; suggestions: Suggestions; types: TypeRow[]; earlier: Earlier | null; admin_name: string | null };
}

const BASE = "/centre/intent";
const TYPES = ["initiative", "brainstorm", "pulse", "problem", "decision"];
const TYPE_NAME: Record<string, string> = { initiative: "Initiative", brainstorm: "Brainstorm", pulse: "Weekly check-in", problem: "Problem", decision: "Decision" };
const STATES = ["open", "in_session", "closing", "draft", "all"];
const VIEW_KEY = "intent-home-view";
const COL: CSSProperties = { display: "flex", flexDirection: "column", gap: "var(--ds-s3)" };
const ROW: CSSProperties = { display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" };
const STICKY: CSSProperties = { position: "sticky", top: 0, zIndex: 5, background: "var(--ds-surface)", padding: "8px 0" }; // spec 04: Start an intent stays in view
const PANEL: CSSProperties = { ...COL, padding: 16 };

function usePhone(): boolean {
  const q = typeof window.matchMedia === "function" ? window.matchMedia("(max-width: 480px)") : null;
  const [phone, setPhone] = useState(q?.matches ?? false);
  useEffect(() => {
    if (!q) return;
    const on = () => setPhone(q.matches);
    q.addEventListener("change", on);
    return () => q.removeEventListener("change", on);
  }, [q]);
  return phone;
}

const shortDay = (iso: string): string => new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });

function storedView(): string | null {
  try { return window.localStorage.getItem(VIEW_KEY); } catch { return null; }
}
function storeView(v: string): void {
  try { window.localStorage.setItem(VIEW_KEY, v); } catch { /* storage is a convenience only */ }
}

function Copy({ text }: { text: string }) {
  const [done, setDone] = useState(false);
  const copy = () => { void navigator.clipboard?.writeText(text).then(() => setDone(true), () => setDone(false)); };
  return <Button onClick={copy}>{done ? t.copied : t.copyRequest}</Button>;
}

function NoAreas({ d }: { d: HomeData }) {
  const nav = useNavigate();
  const v = d.viewer;
  return (
    <section className="ds-card" style={PANEL} aria-label={t.eyebrow}>
      <Strip label={t.north}><p>{t.hello(v.first_name)}</p></Strip>
      <p>{t.explain}</p>
      <p className="ds-soft">{t.request(v.name || v.email, v.email)}</p>
      <div><Copy text={t.request(v.name || v.email, v.email)} /></div>
      <p>{t.adminIs(d.first_run.admin_name)}</p>
      {v.may_start
        ? <Button variant="primary" style={{ minHeight: 44 }} onClick={() => nav(`${BASE}/new`)}>{t.start}</Button>
        : <p className="ds-soft">{t.adminStarts}</p>}
    </section>
  );
}

function FirstRun({ d, phone }: { d: HomeData; phone: boolean }) {
  const nav = useNavigate();
  const f = d.first_run, s = f.suggestions, may = d.viewer.may_start;
  const wide = phone ? { width: "100%", minHeight: 44 } : undefined;
  return (
    <div style={{ ...COL, maxWidth: 760 }}>
      <Strip label={t.north}><p>{f.opening || t.northFallback}</p></Strip>
      <p>{t.help}</p>
      {s.state === "ok" ? <PackSuggestions /> : <p className="ds-soft">{s.line}</p>}
      <section style={COL} aria-label={t.fiveKinds}>
        <h2 style={{ fontSize: 17, margin: 0 }}>{t.fiveKinds}</h2>
        {f.types.map((r) => (
          <div key={r.type} className="ds-card" style={{ ...ROW, padding: 12, justifyContent: "space-between" }}>
            <div style={{ ...COL, gap: 4, flex: "1 1 260px" }}>
              <div style={ROW}><TypeChip type={r.type} name={r.name} /><span className="ds-muted" style={{ fontSize: 12 }}>{r.chip}</span></div>
              <span>{r.line}</span>
            </div>
            {may && <Button style={wide} onClick={() => nav(`${BASE}/new?type=${r.type}`)} aria-label={`${t.startRow} ${r.name}`}>{t.startRow}</Button>}
          </div>
        ))}
        {!may && <p className="ds-soft">{t.adminStartsFirst}</p>}
      </section>
      {may && <p>{t.notSure} <Link className="ds-link" to={`${BASE}/new`}>{t.tellNorth}</Link></p>}
      {f.earlier && (
        <p>{f.earlier.line}{" "}
          {[...f.earlier.walls, ...f.earlier.charters].map((l) => <Link key={l.href} className="ds-link" to={l.href} style={{ marginRight: 8 }}>{l.label}</Link>)}
        </p>
      )}
      <Footnote>{t.firstFootnote}</Footnote>
    </div>
  );
}

function LaneView({ lane, cards, limit, phone, mayStart }: { lane: Lane; cards: Map<string, HomeCard>; limit: number; phone: boolean; mayStart: boolean }) {
  const [open, setOpen] = useState(false);
  const shown = lane.cards.filter((c) => cards.has(c.id));
  const list = open ? shown : shown.slice(0, limit);
  const layout: CSSProperties = phone || open
    ? { display: "grid", gap: 12, gridTemplateColumns: phone ? "1fr" : "repeat(auto-fill, minmax(260px, 1fr))" }
    : { display: "grid", gap: 12, gridAutoFlow: "column", gridAutoColumns: "280px", overflowX: "auto", paddingBottom: 4 };
  return (
    <section style={{ ...COL, gap: 8 }} aria-label={lane.name}>
      <div style={{ ...ROW, justifyContent: "space-between" }}>
        <strong>{lane.name} <span className="ds-soft">({shown.length})</span></strong>
        {shown.length > limit && <button type="button" className="ds-link" style={{ background: "none", border: 0, cursor: "pointer" }} onClick={() => setOpen(!open)}>{open ? t.showFewer : t.showAll(shown.length)}</button>}
      </div>
      {shown.length === 0 ? (
        <p className="ds-soft">{t.laneEmpty(lane.name)}{mayStart && <> <Link className="ds-link" to={`${BASE}/new?area=${encodeURIComponent(lane.id)}`}>{t.startFor(lane.name)}</Link></>}</p>
      ) : (
        <div style={layout}>{list.map((c) => { const card = cards.get(c.id)!; const pv = card as HomeCard & { proving?: string | null; proving_since?: string | null }; return <div key={c.id}><IntentCard card={card} alsoIn={c.also_in} area={lane.name} />{pv.proving && <Link to={`/centre/intent/${c.id}?focus=proving`} style={{ textDecoration: "none" }}><ProvingChip state={pv.proving} since={pv.proving_since} /></Link>}</div>; })}</div>
      )}
    </section>
  );
}

export default function IntentHome() {
  const nav = useNavigate();
  const phone = usePhone();
  const [params, setParams] = useSearchParams();
  // "Save and leave" on a start screen arrives with the line to show once (file 22: "Draft kept in Your drafts")
  const loc = useLocation();
  const [toast, setToast] = useState<string | null>(() => { const m = (loc.state as { toast?: unknown } | null)?.toast; return typeof m === "string" ? m : null; });
  useEffect(() => {
    if (!toast) return;
    nav(loc.pathname + loc.search, { replace: true, state: null }); // so a reload does not show it again
    const id = window.setTimeout(() => setToast(null), 6000);
    return () => window.clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [toast]);
  const toastLine = toast ? <p role="status" className="ds-card" style={{ margin: 0, padding: "10px 14px" }}>{toast}</p> : null;
  const [state, setState] = useState<ScreenStateName>("loading");
  const [d, setD] = useState<HomeData | null>(null);
  const [profile, setProfile] = useState<Parameters<typeof governedBars>[0]>(null);
  const [attempt, setAttempt] = useState(0);
  const [sheet, setSheet] = useState(false);
  const [ids, setIds] = useState<string[] | null>(() => params.get("ids")?.split(",").filter(Boolean) ?? null);

  useEffect(() => {
    let live = true;
    apiGet<HomeData>("/api/intents/home").then(
      (x) => {
        if (!live) return;
        setD(x);
        setState("populated");
        if (x.viewer.governed) apiGet<Parameters<typeof governedBars>[0]>("/api/profile").then((p) => { if (live) setProfile(p); }, () => undefined);
      },
      (e: unknown) => { if (live) setState(e instanceof Refused ? "refused" : "error"); },
    );
    return () => { live = false; };
  }, [attempt]);

  const retry = useCallback(() => { setState("loading"); setAttempt((n) => n + 1); }, []);
  const typeSel = (params.get("type") ?? "").split(",").filter((x) => TYPES.includes(x));
  const stateSel = STATES.includes(params.get("state") ?? "") ? params.get("state")! : "all";
  const areaSel = params.get("area") ?? "";
  const view = params.get("view") ?? storedView() ?? (d?.viewer.admin ? "all" : "mine");
  const set = (k: string, v: string) => {
    const next = new URLSearchParams(params);
    if (v) next.set(k, v); else next.delete(k);
    setParams(next, { replace: true });
  };
  const setView = (v: string) => { storeView(v); set("view", v); };

  const visible = useMemo(() => (d?.cards ?? []).filter((c) =>
    (stateSel === "all" ? c.state !== "draft" || c.mine : c.state === stateSel) && (view === "all" || c.mine) && (!ids || ids.includes(c.id))), [d, stateSel, view, ids]);
  const byType = useMemo(() => new Map(visible.filter((c) => typeSel.length === 0 || typeSel.includes(c.type)).map((c) => [c.id, c])), [visible, typeSel]);
  const filtersOn = typeSel.length + (stateSel !== "all" ? 1 : 0) + (areaSel ? 1 : 0);

  const pageState: ScreenStateName = state;
  if (pageState !== "populated" || !d) {
    return (
      <PageFrame crumbs={t.eyebrow} title={t.title}>
        <ScreenState state={pageState} message={pageState === "loading" ? t.loading : pageState === "error" ? t.error : undefined} onRetry={retry} />
      </PageFrame>
    );
  }

  const v = d.viewer;
  const startBtn = v.may_start
    ? <Button variant="primary" style={phone ? { width: "100%", minHeight: 44 } : undefined} onClick={() => nav(`${BASE}/new`)}>{t.start}</Button>
    : <span className="ds-soft">{t.askAdmin}</span>;
  const actions = <>{phone || !v.admin ? null : <Chip href={`${BASE}/bring`}>{t.bring}</Chip>}<Chip href="/centre/library">{t.library}</Chip></>;

  if (d.screen === "first_run") {
    return <PageFrame crumbs={t.eyebrow} title={t.firstHeading}>{toastLine}<FirstRun d={d} phone={phone} /></PageFrame>;
  }
  if (d.screen === "no_areas" && d.cards.length === 0) {
    return <PageFrame crumbs={t.eyebrow} title={t.title}>{toastLine}<NoAreas d={d} /></PageFrame>;
  }

  const lanes = d.lanes.filter((l) => !areaSel || l.id === areaSel);
  const anyCard = lanes.some((l) => l.cards.some((c) => byType.has(c.id)));
  const counts = (pred: (c: HomeCard) => boolean) => visible.filter(pred).length;
  const draftsOfMine = d.cards.some((c) => c.state === "draft");
  const bars = governedBars(profile);
  const seesAside = v.governed || v.may_start;
  const pastRows = d.past.filter((p) => (typeSel.length === 0 || typeSel.includes(p.type)) && (!ids || ids.includes(p.id)));
  const pastHref = `${BASE}/past${typeSel.length ? `?type=${typeSel.join(",")}` : ""}`;

  const typeChips = (
    <div style={ROW} role="group" aria-label={t.types}>
      {TYPES.map((k) => {
        const n = counts((c) => c.type === k);
        const on = typeSel.includes(k);
        return (
          <span key={k} style={{ opacity: n === 0 && !on ? 0.5 : 1 }}>
            <Chip tone={on ? "active" : "default"} onClick={() => set("type", (on ? typeSel.filter((x) => x !== k) : [...typeSel, k]).join(","))}>{TYPE_NAME[k]} {n}</Chip>
          </span>
        );
      })}
    </div>
  );
  const stateChips = (
    <div style={ROW} role="group" aria-label={t.states}>
      {STATES.filter((s) => s !== "draft" || draftsOfMine).map((s) => {
        const n = s === "all" ? (d.cards.filter((c) => c.state !== "draft" || c.mine)).length : d.cards.filter((c) => c.state === s).length;
        return (
          <span key={s} style={{ opacity: n === 0 && stateSel !== s ? 0.5 : 1 }}>
            <Chip tone={stateSel === s ? "active" : "default"} onClick={() => set("state", s === "all" ? "" : s)}>{t.stateNames[s]}</Chip>
          </span>
        );
      })}
    </div>
  );
  const areaSelect = (
    <label style={ROW}>
      <span className="ds-soft">{t.area}</span>
      <select className="ds-input" value={areaSel} onChange={(e) => set("area", e.target.value)} aria-label={t.area}>
        <option value="">{t.allAreas}</option>
        {(v.areas.length > 1 ? v.areas : []).map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
      </select>
    </label>
  );
  const mineAll = (
    <div style={ROW} role="group" aria-label={`${t.mine} / ${t.all}`}>
      <Chip tone={view === "mine" ? "active" : "default"} onClick={() => setView("mine")}>{t.mine}</Chip>
      <Chip tone={view === "all" ? "active" : "default"} onClick={() => setView("all")}>{t.all}</Chip>
    </div>
  );

  const aside = seesAside ? (
    <>
      {v.governed && (
        <SideCard title={t.governed} note={t.initiativesOnly}>
          {bars === null ? <p>{t.governedNa}</p> : (
            <>
              <p>{t.measures(bars[0]!.total)}</p>
              {bars.map((b) => {
                const pct = Math.round((100 * b.count) / b.total);
                return (
                  <div key={b.label} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    <p style={{ display: "flex", justifyContent: "space-between" }}><span>{b.label}</span><strong>{`${b.count} of ${b.total}`}</strong></p>
                    <div role="progressbar" aria-label={b.label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} style={{ height: 6, background: "var(--ds-line-2)", borderRadius: 3 }}>
                      <div style={{ width: `${pct}%`, height: "100%", background: "var(--ds-teal)", borderRadius: 3 }} />
                    </div>
                  </div>
                );
              })}
            </>
          )}
        </SideCard>
      )}
      <SideCard title={t.kept}>
        <Link className="ds-link" to={`${BASE}/outcomes`}>{t.outcomes}</Link>
        <Link className="ds-link" to={`${BASE}/graph`}>{t.map}</Link>
      </SideCard>
      <Footnote>{t.footnote}</Footnote>
    </>
  ) : <Footnote>{t.footnote}</Footnote>;

  if (params.get("view") === "radar") return <PageFrame crumbs={t.eyebrow} title={t.title} subline={d.subline}><RadarView /></PageFrame>;
  return (
    <PageFrame crumbs={t.eyebrow} title={t.title} subline={d.subline} actions={actions} aside={aside}>
      <div style={COL}>
        {toastLine}
        <div style={STICKY}>{startBtn}</div>
        {d.screen === "no_areas" && <p className="ds-soft">{t.namedOnly}</p>}

        <YourTurnStrip />
        {v.may_start && <PackSuggestions />}
        {v.opportunities && <OpportunitiesPanel variant="home" />}
        {v.opportunities && <Link to="/centre/intent?view=radar&tab=mine">{R.open}</Link>}

        {phone ? (
          <div style={COL}>
            <div style={ROW}><Button onClick={() => setSheet(!sheet)} aria-expanded={sheet}>{t.filters(filtersOn)}</Button>{mineAll}</div>
            {sheet && (
              <div className="ds-card" style={PANEL} role="dialog" aria-label={t.filters(filtersOn)}>
                {typeChips}{stateChips}{areaSelect}
                <Button variant="primary" style={{ minHeight: 44 }} onClick={() => setSheet(false)}>{t.apply}</Button>
              </div>
            )}
          </div>
        ) : <div style={{ ...ROW, gap: 16 }}>{typeChips}{stateChips}{areaSelect}{mineAll}</div>}

        {ids && <p style={ROW}><span className="ds-soft">{t.idsFilter}</span><Chip onClick={() => setIds(null)}>{t.clear}</Chip></p>}

        <div id="lanes" style={COL}>
          {!anyCard && (view === "mine" && (d.cards.length > 0)
            ? <p className="ds-soft">{t.nothingMine}</p>
            : <p className="ds-soft">{t.noneRunning}</p>)}
          {lanes.filter((l) => areaSel === l.id || l.cards.some((c) => byType.has(c.id))).map((l) => <LaneView key={l.id} lane={l} cards={byType} limit={phone ? 5 : 4} phone={phone} mayStart={v.may_start} />)}
        </div>

        <section id="past" className="ds-card" style={{ ...COL, padding: 14, gap: 8 }} aria-label={t.past}>
          <strong>{t.past}</strong>
          {pastRows.length === 0 ? <p className="ds-soft">{t.pastEmpty}</p> : pastRows.map((p) => (
            <div key={p.id} style={{ ...ROW, justifyContent: "space-between", borderTop: "1px solid var(--ds-line)", paddingTop: 8 }}>
              <div style={{ ...COL, gap: 2, flex: "1 1 240px" }}>
                <span style={ROW}><strong>{p.title}</strong>{!phone && <TypeChip type={p.type} name={p.type_name} />}{!phone && p.date && <span className="ds-soft">{p.state === "cancelled" ? t.cancelled : t.closed} {shortDay(p.date)}</span>}</span>
                <span className="ds-soft">{p.one_liner}</span>
              </div>
              {!phone && <Link className="ds-link" to={p.href}>{t.openOutcome}</Link>}
            </div>
          ))}
          {d.past_total > 0 && <Link className="ds-link" to={pastHref}>{t.showAllPast}</Link>}
        </section>

        <section aria-label={t.counters}>
          <StatGrid cols={4}>
            {d.counters.map((c) => (
              <div key={c.key} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <StatCard label={c.label} value={c.value} note={c.note} tone={c.value === "Not available yet" ? "muted" : "soft"} text={c.value.length > 8} />
                {c.ids.length > 0 && (
                  <button type="button" className="ds-link" style={{ background: "none", border: 0, cursor: "pointer", textAlign: "left", padding: 0 }}
                    onClick={() => { setIds(c.ids); document.getElementById(c.key === "M01" ? "lanes" : "past")?.scrollIntoView?.({ behavior: "smooth" }); }}>
                    {t.showIntents}
                  </button>
                )}
              </div>
            ))}
          </StatGrid>
        </section>
        {v.admin && <CentreMeasures onShowIntents={(x) => { setIds(x); document.getElementById("lanes")?.scrollIntoView?.({ behavior: "smooth" }); }} />}
      </div>
    </PageFrame>
  );
}
