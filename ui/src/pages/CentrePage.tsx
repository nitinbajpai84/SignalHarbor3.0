import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { ApiError, apiGet, Refused } from "../api/client";
import ScreenState, { type ScreenStateName } from "../components/ScreenState";
import { Button, Chip, Footnote, PageFrame, Pill, RoomTile, SideCard, StatCard, StatGrid } from "../design";
import { createDraft, getLists, startRoom, type Wall } from "../modules/m1_intent/api";
import { formFromDraft, toPreparation } from "../modules/m1_intent/form";
import { saveLink } from "../modules/m1_intent/room/guestToken";
import { startAssessment } from "../modules/m3_connect/api";
import { useSession } from "../useSession";
import { centreCopy as t, WALL_COPY } from "./centreCopy";

// Intent Centre home (spec section 7, artboard 1): three rooms as doors lit in order, the governed-state bars,
// what Nira is waiting on, four counters. The organiser (company_admin) starts rooms; the sponsor reads the same page.

const NA = t.na;
const NEW = "/centre/intent";

interface Cell { value?: unknown }
type Item = Record<string, Cell | undefined>;
interface Profile { reported_figures?: Record<string, Item>; governance?: { restricted_areas?: Record<string, Item>; field_rules?: Record<string, Item> } }
interface Group { id: number; title: string; state: string; reason: string; files: string[] }
interface Ask { group: number; title: string; holder: { name: string | null } | null }
interface Readiness { groups: Group[]; percent: number; asks: Ask[] }
interface Person { status: string }
interface Session { id?: string; state: string; seats: number }
interface Baselines { baselines: { id?: string; state: string }[] }
interface Charter { charter?: { status?: string; signing?: { signers?: { name: string }[] } } }
interface Closed { id: string; topic: string | null; by: string }
interface Assessments { assessments: { id?: string; state: string; created_at?: string }[]; signed_baseline: boolean; can_start?: boolean }
type Fetched<T> = T | null | "failed";
type Lit = "OPEN" | "NEXT" | "dim";

/** A door. The start actions are links that open the start panel on this page (?start=wall|truth), so they sit inside the tile. */
interface Room { n: number; name: string; line: string; counts: string[]; open: boolean; signed: boolean; action?: { label: string; href: string } }

const val = (i: Item | undefined, f: string): unknown => i?.[f]?.value;
const has = (v: unknown): boolean => (Array.isArray(v) ? v.length > 0 : v !== undefined && v !== null && String(v).trim() !== "");
const norm = (s: unknown): string => String(s ?? "").toLowerCase().replace(/[^a-z0-9]/g, "");
const live = (state: string): boolean => state !== "draft" && state !== "closed";

export interface GovernedBar { label: string; count: number; total: number }

/** Bars over the measures in reported_figures. A measure is matched to a rule or area by its id or its name (same letters, any case).
 * Returns null when there are no measures, so the panel reads "Not available yet" and never 0%. */
export function governedBars(p: Profile | null): GovernedBar[] | null {
  const figures = Object.entries(p?.reported_figures ?? {});
  if (figures.length === 0) return null;
  const rules = Object.entries(p?.governance?.field_rules ?? {});
  const areas = Object.entries(p?.governance?.restricted_areas ?? {});
  const names = (id: string, i: Item): string[] => [norm(id), norm(val(i, "measure")), norm(val(i, "name"))].filter(Boolean);
  const ruleFor = (id: string, i: Item) => rules.find(([k, r]) => names(id, i).some((n) => n === norm(k) || n === norm(val(r, "field"))))?.[1];
  // Restricted areas carry only a name and who may see, so a measure is sealed only when its own id or name equals an area's id or name.
  const sealed = (id: string, i: Item) => areas.some(([k, a]) => names(id, i).some((n) => n === norm(k) || n === norm(val(a, "area"))));
  const count = (test: (id: string, i: Item) => boolean) => figures.filter(([id, i]) => test(id, i)).length;
  return [
    { label: t.bars.owner, count: count((_, i) => has(val(i, "owner"))), total: figures.length },
    { label: t.bars.classified, count: count((id, i) => { // undecided = empty, "not_sure" or "not sure" (as holds() in m2_baseline GovernanceScreen)
      const c = String(val(ruleFor(id, i), "personal") ?? "").toLowerCase().replace("_", " ").trim(); return c !== "" && c !== "not sure"; }), total: figures.length },
    { label: t.bars.maySee, count: count((id, i) => has(val(ruleFor(id, i), "may_see"))), total: figures.length },
    { label: t.bars.sealed, count: count(sealed), total: figures.length },
  ];
}

/** null = the module is switched off for this company (403): the room is not shown. Any other failure reads "Not available yet". */
async function get<T>(path: string): Promise<Fetched<T>> {
  try {
    return await apiGet<T>(path);
  } catch (e: unknown) {
    return e instanceof Refused ? null : "failed";
  }
}

const ok = <T,>(x: Fetched<T>): T | null => (x === null || x === "failed" ? null : x);

function buildRooms(s: Fetched<Session[]>, b: Fetched<Baselines>, a: Fetched<Assessments>, w: Fetched<{ walls: Wall[] }>, organiser: boolean): Room[] {
  const out: Room[] = [];
  const s1 = ok(s) ?? [];
  const all = ok(w)?.walls ?? [];
  const running = all.filter((x) => live(x.state));
  const b1 = ok(b)?.baselines ?? [];
  const a1 = ok(a);
  const wall = s1.find((x) => live(x.state) && x.id);
  const wallHref = wall ? `${NEW}/wall/${encodeURIComponent(wall.id!)}` : "";
  const together = s1.find((x) => x.state === "together" && x.id);
  const baseline = b1.find((x) => x.state === "signed" && x.id) ?? b1.find((x) => x.id);
  const mine = (a1?.assessments ?? []).filter((x) => x.id).sort((x, y) => String(x.created_at ?? "").localeCompare(String(y.created_at ?? ""))).pop();
  if (s !== null) {
    const start = running.length > 0 ? { label: WALL_COPY.startAnother, href: "?start=wall" } : wall ? { label: t.openWall, href: wallHref } : { label: WALL_COPY.start, href: "?start=wall" };
    out.push({ n: 1, ...t.think, signed: s1.some((x) => x.state === "closed"), open: running.length > 0 || !!wall,
      action: organiser && s !== "failed" ? start : wall ? { label: t.openWall, href: wallHref } : undefined,
      counts: ok(w) === null ? [NA] : [t.cardsOnWall(running.reduce((n, x) => n + x.cards_count, 0)), t.contributed(running.reduce((n, x) => n + x.people_count, 0))] });
  }
  if (b !== null) out.push({ n: 2, ...t.define, signed: b1.some((x) => x.state === "signed"), open: b1.some((x) => x.state !== "signed"),
    action: together ? { label: t.openDefine, href: `${NEW}/define/${encodeURIComponent(together.id!)}` }
      : baseline ? { label: t.openBaseline, href: `${NEW}/baseline/${encodeURIComponent(baseline.id!)}` } : undefined,
    counts: b === "failed" ? [NA] : [t.baselines(b1.length), t.signed(b1.filter((x) => x.state === "signed").length),
      ...(all.length > 1 ? [WALL_COPY.define(all.length, all.reduce((n, x) => n + x.cards_count, 0))] : [])] });
  if (a !== null) out.push({ n: 3, ...t.truth, signed: false, open: !!a1?.assessments.some((x) => x.state === "draft"),
    action: mine ? { label: t.openTrial, href: `${NEW}/truth/${encodeURIComponent(mine.id!)}` }
      : organiser && a1?.can_start ? { label: t.startTruth, href: "?start=truth" } : undefined,
    counts: a1 ? [a1.signed_baseline ? t.signedReady : t.noSigned] : [NA] });
  return out;
}

/** Lit in order: open when it has work in progress, next when the room before is signed (room 1 is always next), otherwise dim. */
function lit(rooms: Room[], i: number): Lit {
  const r = rooms[i]!;
  return r.open ? "OPEN" : i === 0 || rooms[i - 1]!.signed ? "NEXT" : "dim";
}

// Doors side by side at desk width; stacked once the column is narrower than two doors (phone).
export const DOORS_GRID = "repeat(auto-fit, minmax(min(100%, 240px), 1fr))";
const DOORS: CSSProperties = { listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "var(--ds-s2)", gridTemplateColumns: DOORS_GRID };
const DOOR: CSSProperties = { display: "flex", flexDirection: "column", gap: "var(--ds-s1)" };
const FIELD: CSSProperties = { display: "flex", flexDirection: "column", gap: 4, fontSize: 13 };
const INPUT: CSSProperties = { minHeight: 44, padding: "8px 12px", borderRadius: 8, border: "1px solid var(--ds-line-2)", background: "var(--ds-ground)", color: "var(--ds-ink)", font: "inherit" };
const ROW: CSSProperties = { display: "flex", gap: "var(--ds-s1)", flexWrap: "wrap", alignItems: "center" };

export default function CentrePage() {
  const go = useNavigate();
  const { user } = useSession();
  const organiser = !!user?.roles.includes("company_admin");
  const [params, setParams] = useSearchParams();
  const asked = organiser ? params.get("start") : null;
  const close = () => setParams({}, { replace: true });

  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState("");
  const [days, setDays] = useState(5);
  const [topic, setTopic] = useState("");
  const [purpose, setPurpose] = useState("");
  const [openCount, setOpenCount] = useState(0);
  useEffect(() => { if (asked === "wall") setDays(5); }, [asked]);

  // The lean Prepare's own steps (DraftedSession.tsx): draft from the profile, start the room, keep the link for this tab.
  const startWall = async (d: number | null) => {
    if (openCount > 0 && !topic.trim()) { setStartError(WALL_COPY.topicNeeded); return; } // IC-2t: the server says the same
    setStarting(true);
    setStartError("");
    try {
      const prep = toPreparation(formFromDraft(await getLists()));
      const made = await createDraft({ ...prep, ...(purpose.trim() ? { purpose: purpose.trim() } : {}), topic: topic.trim() || null, wall_window_days: d }, true);
      saveLink(made.id, (await startRoom(made.id)).join_path);
      go(`${NEW}/wall/${encodeURIComponent(made.id)}`);
    } catch (e) {
      setStartError(e instanceof ApiError && e.message ? e.message : t.failed);
      setStarting(false);
    }
  };
  const startTruth = async () => {
    setStarting(true);
    setStartError("");
    try {
      go(`${NEW}/truth/${encodeURIComponent((await startAssessment()).assessment.id)}`);
    } catch (e) {
      setStartError(e instanceof ApiError && e.message ? e.message : t.failed);
      setStarting(false);
    }
  };

  const [state, setState] = useState<ScreenStateName>("loading");
  const [attempt, setAttempt] = useState(0);
  const [fetched, setFetched] = useState<Parameters<typeof buildRooms> | null>(null);
  const [walls, setWalls] = useState<Wall[]>([]);
  const [bars, setBars] = useState<ReturnType<typeof governedBars>>(null);
  const [ready, setReady] = useState<Readiness | null>(null);
  const [closed, setClosed] = useState<Closed[]>([]);
  const [done, setDone] = useState<[number, number] | null>(null);

  useEffect(() => {
    let on = true;
    (async () => {
      try {
        const [p, r, iv, s, b, a, wl] = await Promise.all([
          apiGet<Profile>("/api/profile"), apiGet<Readiness>("/api/profile/readiness"),
          get<{ people: Person[] }>("/api/interview"), get<Session[]>("/api/modules/m1_intent/sessions"),
          get<Baselines>("/api/modules/m2_baseline/baselines"), get<Assessments>("/api/modules/m3_connect/assessments"),
          get<{ walls: Wall[] }>("/api/modules/m1_intent/walls"),
        ]);
        if (!on) return;
        const people = ok(iv)?.people;
        const all = ok(wl)?.walls ?? [];
        setBars(governedBars(p));
        setReady(r);
        setDone(people ? [people.filter((x) => x.status === "done").length, people.length] : null);
        setWalls(all.filter((x) => live(x.state)));
        const charters = await Promise.all(all.filter((x) => x.state === "closed").map(async (x) => ({ x, c: ok(await get<Charter>(`/api/modules/m1_intent/sessions/${encodeURIComponent(x.id)}/charter`))?.charter })));
        if (!on) return;
        setClosed(charters.filter(({ c }) => c?.status === "signed").map(({ x, c }) => ({ id: x.id, topic: x.topic, by: (c?.signing?.signers ?? []).map((n) => n.name).join(", ") })));
        setOpenCount(all.filter((x) => x.state !== "closed").length);
        setFetched([s, b, a, wl, false]);
        setState("populated");
      } catch {
        if (on) setState("error");
      }
    })();
    return () => { on = false; };
  }, [attempt]);

  const retry = useCallback(() => { setState("loading"); setAttempt((n) => n + 1); }, []);
  const waiting = ready
    ? (ready.asks.length > 0
        ? ready.asks.map((x) => ({ k: x.group, title: x.title, why: x.holder?.name ?? "" }))
        : ready.groups.filter((g) => g.state === "missing" || g.state === "partly").map((g) => ({ k: g.id, title: g.title, why: g.reason }))
      ).slice(0, 3)
    : [];
  const files = ready ? ready.groups.reduce((n, g) => n + g.files.length, 0) : null;
  const populated = state === "populated";
  const rooms = fetched ? buildRooms(fetched[0], fetched[1], fetched[2], fetched[3], organiser) : [];

  const aside = populated ? (
    <>
      <SideCard title={t.governed}>
        {bars === null ? <p>{NA}</p> : (
          <>
            <p>{t.measures(bars[0]!.total)}</p>
            {bars.map((b) => {
              const pct = Math.round((100 * b.count) / b.total);
              return (
                <div key={b.label} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <p style={{ display: "flex", justifyContent: "space-between" }}><span>{b.label}</span><strong>{b.count === 0 || b.count === b.total ? `${b.count} of ${b.total}` : `${pct}%`}</strong></p>
                  <div role="progressbar" aria-label={b.label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} style={{ height: 6, background: "var(--ds-line-2)", borderRadius: 3 }}>
                    <div style={{ width: `${pct}%`, height: "100%", background: "var(--ds-teal)", borderRadius: 3 }} />
                  </div>
                </div>
              );
            })}
          </>
        )}
      </SideCard>
      <SideCard title={t.waiting}>
        {waiting.length === 0 ? <p>{t.nothingWaiting}</p> : (
          <>
            <ol aria-label={t.waiting} style={{ margin: 0, paddingLeft: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: "var(--ds-s2)" }}>
              {waiting.map((w, i) => (
                <li key={w.k} style={{ display: "flex", gap: "var(--ds-s2)" }}>
                  <span className="ds-warn">{String(i + 1).padStart(2, "0")}</span>
                  <span><strong>{w.title}</strong>{w.why ? <span className="ds-soft"><br />{w.why}</span> : null}</span>
                </li>
              ))}
            </ol>
            {organiser ? <Link className="ds-link" to={`${NEW}/bring`}>{t.askForThese}</Link> : null}
          </>
        )}
      </SideCard>
      <SideCard title={t.soFar}>
        <Link className="ds-link" to={`${NEW}/outcomes`}>{t.outcomes}</Link>
        <Link className="ds-link" to={`${NEW}/graph`}>{t.map}</Link>
      </SideCard>
      <Footnote>{t.footnote}</Footnote>
    </>
  ) : undefined;

  return (
    <PageFrame
      crumbs={t.eyebrow}
      title={t.title}
      subline={populated && files !== null && done ? t.read(files, done[0]) : t.subline}
      actions={organiser ? <Chip href={`${NEW}/bring`}>{t.bring}</Chip> : undefined}
      aside={aside}
    >
      {startError ? <p role="alert" className="ds-warn">{startError}</p> : null}
      {asked === "wall" ? (
        <section aria-label={t.wallWindowTitle}>
          <SideCard title={WALL_COPY.panelTitle}>
            <label style={FIELD}>{WALL_COPY.topicLabel}<input style={INPUT} value={topic} maxLength={60} placeholder={WALL_COPY.topicHint} onChange={(e) => setTopic(e.target.value)} /></label>
            <label style={FIELD}>{WALL_COPY.purposeLabel}<input style={INPUT} value={purpose} maxLength={500} onChange={(e) => setPurpose(e.target.value)} /></label>
            <label style={FIELD}>{t.wallWindowTitle}
              <span style={ROW}>
                <input style={{ ...INPUT, width: "5rem" }} type="number" min="1" max="20" value={days}
                  onChange={(e) => setDays(Math.min(20, Math.max(1, Number.parseInt(e.target.value, 10) || 5)))} />
                {t.wallWindowLabel}
              </span>
            </label>
            <p>{t.wallWindowHelp}</p>
            <div style={ROW}>
              <Button variant="primary" disabled={starting} onClick={() => void startWall(days)}>{t.wallWindowStart}</Button>
              <Button disabled={starting} onClick={() => void startWall(null)}>{t.wallWindowUseDefault}</Button>
              <Button disabled={starting} onClick={close}>{t.notNow}</Button>
            </div>
          </SideCard>
        </section>
      ) : null}
      {asked === "truth" ? (
        <section aria-label={t.startTruth}>
          <SideCard title={t.startTruth}>
            <p>{t.truthHelp}</p>
            <div style={ROW}>
              <Button variant="primary" disabled={starting} onClick={() => void startTruth()}>{t.truthGo}</Button>
              <Button disabled={starting} onClick={close}>{t.notNow}</Button>
            </div>
          </SideCard>
        </section>
      ) : null}
      <ScreenState state={state} onRetry={retry} message={state === "error" ? t.error : state === "loading" ? t.loading : undefined}>
        <ul aria-label={t.rooms} style={DOORS}>
          {rooms.map((r, i) => {
            const l = lit(rooms, i);
            return (
              <li key={r.n} style={DOOR}>
                <span><Pill tone={l === "OPEN" ? "open" : "draft"}>{t.roomLabel(r.n, l)}</Pill></span>
                <RoomTile number={r.n} name={r.name} state={l === "OPEN" ? "open" : l === "NEXT" ? "next" : "dim"} line={r.line} counts={r.counts} action={r.action} />
              </li>
            );
          })}
        </ul>
        {walls.length > 0 ? (
          <SideCard title={WALL_COPY.walls}>
            <ul aria-label={WALL_COPY.walls} style={{ listStyle: "none", paddingLeft: 0 }}>
              {walls.map((x) => {
                const name = x.topic ?? WALL_COPY.noTopic;
                return (
                  <li key={x.id} style={{ ...ROW, justifyContent: "space-between", padding: "6px 0" }}>
                    <span>{name} · {WALL_COPY.cards(x.cards_count)}</span>
                    <Link className="ds-link" to={`${NEW}/wall/${encodeURIComponent(x.id)}`} aria-label={`${WALL_COPY.open} ${name}`}>{WALL_COPY.open}</Link>
                  </li>
                );
              })}
            </ul>
          </SideCard>
        ) : null}
        {closed.length > 0 ? (
          <SideCard title={WALL_COPY.closed}>
            <ul aria-label={WALL_COPY.closed} style={{ listStyle: "none", paddingLeft: 0 }}>
              {closed.map((x) => (
                <li key={x.id} style={{ ...ROW, justifyContent: "space-between", padding: "6px 0" }}>
                  <span>{WALL_COPY.signedLine(x.topic ?? WALL_COPY.noTopic, x.by)}</span>
                  <Link className="ds-link" to={`${NEW}/charter/${encodeURIComponent(x.id)}`} aria-label={`${WALL_COPY.openCharter} ${x.topic ?? WALL_COPY.noTopic}`}>{WALL_COPY.openCharter}</Link>
                </li>
              ))}
            </ul>
          </SideCard>
        ) : null}
        <StatGrid cols={4}>
          <StatCard label={t.counters.files} value={files ?? NA} text={files === null} note={ready ? t.inputs(ready.groups.filter((g) => g.state === "read").length, ready.groups.length) : undefined} />
          <StatCard label={t.counters.interviews} value={done ? `${done[0]} / ${done[1]}` : NA} text={!done} />
          <StatCard label={t.counters.lens} value={ready ? `${ready.percent}%` : NA} text={!ready} note={ready ? t.ofBaseline : undefined} />
          <StatCard label={t.counters.time} value={NA} text />
        </StatGrid>
      </ScreenState>
    </PageFrame>
  );
}
