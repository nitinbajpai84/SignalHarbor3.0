import { Fragment, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ApiError, apiGet } from "../api/client";
import { Button, Chip, EmptyState } from "../design";

// Search and filters (spec 15): one search box, seven chip groups, a sort and the result card, answered by GET /api/intents.
// Chips and sort live in the address; the search text stays in page memory (people type names into it).

type View = "home" | "past";
interface Card {
  id: string; type: string; title: string | null; title_private: boolean; state: string; stage_name: string | null; areas: string[]; people_count: number;
  can_open: boolean; purpose: string | null; organiser: string | null; outcome_text: string | null; rating: { n: number; avg: number | null } | null;
  timebox: { status: string; ends: string | null; closed_at: string | null; cancelled_at: string | null; days_left: number | null; extended: boolean };
  match: { field: string; snippet: string } | null;
}
interface Result { items: Card[]; total: number; total_visible: number; next_cursor: string | null; facets: Record<string, Record<string, number>>; index: { built_at: string | null; rows: number } }

const TYPES: [string, string][] = [["initiative", "Initiative"], ["brainstorm", "Brainstorm"], ["pulse", "Weekly check-in"], ["problem", "Problem"], ["decision", "Decision"]];
const TYPE_NAME = Object.fromEntries(TYPES);
const STATE_NAME: Record<string, string> = { draft: "Draft", open: "Open", in_session: "In session", closing: "Closing", closed: "Closed", cancelled: "Cancelled" };
const ROLES: [string, string][] = [["organiser", "Organiser"], ["sponsor", "Sponsor"], ["participant", "Participant"], ["affected", "Affected"], ["observer", "Observer"],
  ["decider", "Decider"], ["owner", "Owner"], ["reporter", "Reporter"], ["named", "Named in a share link"]];
const TIMEBOX_HOME: [string, string][] = [["not_started", "Not started yet"], ["running", "Running to time"], ["extended", "Extended"], ["past_end", "Past its end"]];
const TIMEBOX_PAST: [string, string][] = [["closed_in_time", "Closed within time"], ["closed_late", "Closed late"]];
const OUTCOMES: [string, string][] = [["initiative", "Start an Initiative"], ["backlog", "Added to backlog"], ["problem", "Started a Problem"], ["nothing", "Nothing, and why"]];
const RATED: [string, string][] = [["rated", "Rated (3 or more ratings)"], ["not_rated", "Not rated yet"]];
const SORTS: Record<View, [string, string][]> = {
  home: [["newest", "Newest"], ["ending", "Ending soonest"], ["people", "Most people"], ["rated", "Best rated"]],
  past: [["newest", "Newest closed"], ["people", "Most people"], ["rated", "Best rated"]],
};
const SINGLE = new Set(["type", "role", "rated"]);
const PAUSE_MS = 250, MIN_CHARS = 2, SHOWN_AREAS = 5, PAGE = 20;
const hint = "You are searching titles, purposes, areas, organisers and outcomes. Card text is searched only in intents you may read.";

const day = (s: string | null) => (s ? new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" }).format(new Date(s)) : "");
const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? "" : "s"}`;

function timeLine(c: Card): string {
  const t = c.timebox;
  if (t.status === "not_started") return "Not started yet";
  if (t.status === "cancelled") return `Cancelled ${day(t.cancelled_at)}`;
  if (t.status === "closed_in_time") return `Closed ${day(t.closed_at)}, within time`;
  if (t.status === "closed_late") return `Closed ${day(t.closed_at)}, late`;
  if (t.status === "none") return c.type === "pulse" ? "Not available yet: the series has no single end date" : "Not available yet: no end date was set";
  if (t.status === "past_end") return `Ended ${plural(Math.abs(t.days_left ?? 0), "working day")} ago, past its end`;
  return `Ends ${day(t.ends)}, ${plural(t.days_left ?? 0, "working day")} left${t.extended ? ". Extended" : ""}`;
}

function Marked({ text, words }: { text: string; words: string[] }) {
  if (!words.length) return <>{text}</>;
  const re = new RegExp(`(${words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "ig");
  return <>{text.split(re).map((p, i) => (i % 2 ? <mark key={i}>{p}</mark> : <Fragment key={i}>{p}</Fragment>))}</>;
}

function ResultCard({ c, words, onArea }: { c: Card; words: string[]; onArea: (a: string) => void }) {
  const r = c.rating;
  return (
    <article className="ds-card" style={{ display: "flex", flexDirection: "column", gap: 6, padding: 16 }}>
      <div><Chip>{TYPE_NAME[c.type] ?? c.type}</Chip></div>
      <h3 style={{ margin: 0 }}>
        {c.title_private ? "Title private to the company" : <Link className="ds-link" to={`/centre/intent/${c.id}`}><Marked text={c.title ?? ""} words={words} /></Link>}
      </h3>
      {c.purpose && <p style={{ margin: 0 }}>{c.purpose.length > 140 ? `${c.purpose.slice(0, 140)}...` : c.purpose}</p>}
      {c.match && c.match.snippet && <p className="ds-muted" style={{ margin: 0 }}>{`Matched in: ${c.match.field}. `}<Marked text={c.match.snippet} words={words} /></p>}
      <div className="ds-frame__actions">
        <Chip>{c.stage_name ? `${STATE_NAME[c.state] ?? c.state}, ${c.stage_name}` : STATE_NAME[c.state] ?? c.state}</Chip>
        {c.areas.length === 0 ? <span className="ds-muted">No area named</span>
          : <>{c.areas.slice(0, 3).map((a) => <Chip key={a} onClick={() => onArea(a)}>{a}</Chip>)}{c.areas.length > 3 && <span className="ds-muted">{`+${c.areas.length - 3}`}</span>}</>}
      </div>
      <p className="ds-muted" style={{ margin: 0 }}>{[c.organiser && `Organised by ${c.organiser}`, plural(c.people_count, "person").replace("persons", "people")].filter(Boolean).join(". ")}</p>
      <p className="ds-muted" style={{ margin: 0 }}>{timeLine(c)}</p>
      <p style={{ margin: 0 }}>{c.state === "closed" ? (c.outcome_text || "Not available yet: no outcome was written.") : c.state === "cancelled" ? "" : "No outcome yet"}</p>
      {r && <p className="ds-muted" style={{ margin: 0 }}>{r.avg !== null ? `${r.avg} from ${r.n} ratings` : r.n > 0 ? `${plural(r.n, "rating")} so far, the average shows from three` : "Not rated yet"}</p>}
      {!c.can_open && <p className="ds-muted" style={{ margin: 0 }}>You can see that this exists. Ask the organiser to add you to open it.</p>}
      <div><Link className="ds-btn" to={`/centre/intent/${c.id}`}>{c.can_open ? "Open" : "View summary"}</Link></div>
    </article>
  );
}

const CSS = `.sf-sheet{background:var(--ds-surface);color:var(--ds-ink);width:100%;max-width:none;margin:auto 0 0;border:0;border-radius:16px 16px 0 0;padding:16px;max-height:90vh}.sf-sheet::backdrop{background:rgba(0,0,0,.4)}
.sf-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.sf-chips,.sf-chips-phone{display:flex;flex-direction:column;gap:8px}.sf-fbtn{display:none}.sf-strip{display:flex;gap:6px;overflow-x:auto}
@media (max-width:700px){.sf-grid{grid-template-columns:1fr}.sf-chips{display:none}.sf-fbtn{display:inline-block}}`;

export default function SearchFilters({ view }: { view: View }) {
  const [params, setParams] = useSearchParams();
  const [text, setText] = useState("");
  const [q, setQ] = useState("");
  const [data, setData] = useState<Result | null>(null);
  const [cards, setCards] = useState<Card[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "rebuilding" | "error">("loading");
  const [hide, setHide] = useState(false);
  const [moreAreas, setMoreAreas] = useState(false);
  const [sheet, setSheet] = useState<URLSearchParams | null>(null);
  const [sheetCount, setSheetCount] = useState<number | null>(null);
  const dlg = useRef<HTMLDialogElement>(null);

  const sel = (p: URLSearchParams, k: string) => (p.get(k) ?? "").split(",").filter(Boolean);
  const sort = params.get("sort") ?? "newest";
  const build = (p: URLSearchParams, extra: Record<string, string> = {}, search = q) => {
    const u = new URLSearchParams({ view });
    ["type", "state", "area", "role", "timebox", "outcome", "rated"].forEach((k) => p.get(k) && u.set(k, p.get(k)!));
    u.set("sort", sort);
    if (search.trim().length >= MIN_CHARS) u.set("q", search.trim());
    Object.entries(extra).forEach(([k, v]) => u.set(k, v));
    return `/api/intents?${u}`;
  };
  const fail = (e: unknown) => setState(e instanceof ApiError && e.status === 503 ? "rebuilding" : "error");
  const load = () => {
    setState("loading");
    apiGet<Result>(build(params, { limit: String(PAGE) })).then((d) => { setData(d); setCards(d.items); setState("ready"); }).catch(fail);
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [params.toString(), q, view]);
  useEffect(() => {  // a short pause after typing; Enter and the clear button search at once
    const id = window.setTimeout(() => setQ(text), text === "" ? 0 : PAUSE_MS);
    return () => window.clearTimeout(id);
  }, [text]);
  useEffect(() => { // the phone sheet's live count, from a counts-only call
    if (!sheet) return;
    apiGet<Result>(build(sheet, { limit: "0" })).then((d) => setSheetCount(d.total)).catch(() => setSheetCount(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sheet?.toString()]);
  useEffect(() => { const d = dlg.current; if (!d) return; if (sheet && !d.open) d.showModal?.(); if (!sheet && d.open) d.close?.(); }, [sheet]);

  const set = (p: URLSearchParams, apply: (n: URLSearchParams) => void) => { const n = new URLSearchParams(p); apply(n); return n; };
  const flip = (p: URLSearchParams, k: string, v: string) => set(p, (n) => {
    const cur = sel(p, k);
    const next = SINGLE.has(k) ? (cur.includes(v) ? [] : [v]) : cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v];
    if (next.length) n.set(k, next.join(",")); else n.delete(k);
  });
  const active = ["type", "state", "area", "role", "timebox", "outcome", "rated"].flatMap((k) => sel(params, k).map((v) => [k, v] as const));
  const words = q.toLowerCase().split(/\s+/).filter((w) => w.length >= MIN_CHARS);
  const clearAll = () => setParams(set(params, (n) => ["type", "state", "area", "role", "timebox", "outcome", "rated"].forEach((k) => n.delete(k))));

  const label = (k: string, v: string) => {
    const all = { type: TYPES, role: ROLES, timebox: [...TIMEBOX_HOME, ...TIMEBOX_PAST], outcome: OUTCOMES, rated: RATED, state: Object.entries(STATE_NAME), area: [[v, v]] }[k] as [string, string][];
    return `${{ type: "Type", state: "State", area: "Area", role: "My role", timebox: "Time box", outcome: "Outcome", rated: "Rated" }[k]}: ${all.find(([x]) => x === v)?.[1] ?? v}`;
  };

  const groups = (p: URLSearchParams, pick: (n: URLSearchParams) => void) => {
    const f = data?.facets ?? {};
    const states = view === "home" ? ["draft", "open", "in_session", "closing"] : ["closed", "cancelled"];
    const areas = Object.keys(f.area ?? {}).sort();
    const defs: [string, string, [string, string][]][] = [
      ["type", "Type", TYPES], ["state", "State", states.map((s): [string, string] => [s, STATE_NAME[s] ?? s])],
      ["area", "Area", (moreAreas ? areas : areas.slice(0, SHOWN_AREAS)).map((a): [string, string] => [a, a])], ["role", "My role", ROLES],
      ["timebox", "Time box status", view === "home" ? TIMEBOX_HOME : TIMEBOX_PAST], ...(view === "past" ? [["outcome", "Outcome kind", OUTCOMES] as [string, string, [string, string][]]] : []),
      ["rated", "Rated", RATED],
    ];
    return defs.map(([k, name, opts]) => (
      <div key={k} role="group" aria-label={name} style={{ display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center" }}>
        <strong>{name}</strong>
        {k === "area" && areas.length === 0 && <span className="ds-muted">No areas set up yet. Your company admin adds them in the company profile.</span>}
        {opts.map(([v, t]) => {
          const n = f[k]?.[v] ?? 0;
          return <span key={v} style={n === 0 && !sel(p, k).includes(v) ? { opacity: 0.45 } : undefined}><Chip tone={sel(p, k).includes(v) ? "active" : "default"} onClick={() => pick(flip(p, k, v))}>{`${t} ${n}`}</Chip></span>;
        })}
        {k === "area" && areas.length > SHOWN_AREAS && !moreAreas && <Chip onClick={() => setMoreAreas(true)}>More areas</Chip>}
      </div>
    ));
  };

  const empty = () => {
    const filtered = active.length > 0, searched = q.trim().length >= MIN_CHARS;
    if (data && data.total_visible === 0 && !filtered && !searched) {
      return view === "past" ? <EmptyState title="Nothing has finished yet." lines={["An intent appears here once it is closed or cancelled."]} links={[{ label: "Back to running intents", href: "/centre/intent" }]} />
        : <EmptyState title="Nothing is running that you can see." lines={["Past intents are kept. Open them to see what came out."]} links={[{ label: "Past intents", href: "/centre/intent/past" }]} />;
    }
    const lines = searched && !filtered ? ["Try fewer words, or check the spelling. Card text is searched only in intents you may read."] : searched ? ["Clear the filters to search everything you can see."] : ["Remove one, or clear them all."];
    return (
      <div>
        <EmptyState title={searched ? `No intent matches "${q.trim()}"${filtered ? " with these filters" : ""}.` : "No intent matches these filters."} lines={lines} />
        {searched && !filtered ? <Button onClick={() => { setText(""); setQ(""); }}>Clear search</Button> : <Button onClick={clearAll}>Clear all filters</Button>}
      </div>
    );
  };

  const more = () => data?.next_cursor && apiGet<Result>(build(params, { limit: String(PAGE), cursor: data.next_cursor })).then((d) => { setCards((c) => [...c, ...d.items]); setData({ ...d, total: data.total }); }).catch(fail);

  return (
    <section aria-label="Find an intent">
      <style>{CSS}</style>
      <div className="ds-frame__actions" style={{ marginBottom: 8 }}>
        <input type="search" className="ds-input" style={{ flex: "1 1 18rem" }} aria-label="Search intents" placeholder="Search by title, purpose, area, organiser or outcome" value={text}
          onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") setQ(text); if (e.key === "Escape") { setText(""); setQ(""); } }} />
        <label className="ds-muted" htmlFor="sf-sort">Sort</label>
        <select id="sf-sort" className="ds-input" value={sort} onChange={(e) => setParams(set(params, (n) => n.set("sort", e.target.value)))}>
          {SORTS[view].map(([v, t]) => <option key={v} value={v}>{t}</option>)}
        </select>
        <button type="button" className="sf-fbtn ds-btn" onClick={() => { setSheetCount(null); setSheet(new URLSearchParams(params)); }}>{`Filters${active.length ? ` (${active.length})` : ""}`}</button>
      </div>
      {!hide && <p className="ds-muted">{hint} <button type="button" className="ds-link" onClick={() => setHide(true)}>Got it</button></p>}
      <div className="sf-chips">{groups(params, (n) => setParams(n))}</div>
      {active.length > 0 && (
        <div className="sf-strip" role="list" aria-label="Active filters">
          {active.map(([k, v]) => <span role="listitem" key={`${k}${v}`}><Chip onClick={() => setParams(flip(params, k, v))}>{`${label(k, v)} x`}</Chip></span>)}
          <Button onClick={clearAll}>Clear all filters</Button>
        </div>
      )}
      {state === "loading" && <p role="status" className="ds-muted">Loading the list.</p>}
      {state === "rebuilding" && <div role="status"><EmptyState title="The list is being refreshed." lines={["This takes a few seconds. Try again in a moment."]} /><Button onClick={load}>Try again</Button></div>}
      {state === "error" && <div role="alert"><EmptyState title="The list did not load." lines={["Nothing was changed. Try again in a moment."]} /><Button onClick={load}>Try again</Button></div>}
      {state === "ready" && data && (
        <>
          <p className="ds-muted">{active.length > 0 || q.trim().length >= MIN_CHARS ? `${plural(data.total, "intent")} of ${data.total_visible} you can see` : plural(data.total, "intent")}
            {" "}{data.index.built_at ? `List refreshed ${day(data.index.built_at)}, ${new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit" }).format(new Date(data.index.built_at))}` : "Not available yet: the list has not been built."}</p>
          {cards.length === 0 ? empty() : <div className="sf-grid">{cards.map((c) => <ResultCard key={c.id} c={c} words={words} onArea={(a) => setParams(set(params, (n) => n.set("area", a)))} />)}</div>}
          {data.next_cursor && <Button onClick={more}>Show more</Button>}
        </>
      )}
      <dialog ref={dlg} className="sf-sheet" aria-label="Filters" onClose={() => setSheet(null)}>
        {sheet && (
          <div className="sf-chips-phone">
            <div className="ds-frame__actions"><strong>{`Filters${sheetCount !== null ? `, ${plural(sheetCount, "intent")}` : ""}`}</strong><Button aria-label="Close" onClick={() => setSheet(null)}>x</Button></div>
            {groups(sheet, (n) => setSheet(n))}
            <div className="ds-frame__actions">
              <Button disabled={sel(sheet, "type").length + sel(sheet, "state").length + sel(sheet, "area").length + sel(sheet, "role").length + sel(sheet, "timebox").length + sel(sheet, "outcome").length + sel(sheet, "rated").length === 0}
                onClick={() => setSheet(set(sheet, (n) => ["type", "state", "area", "role", "timebox", "outcome", "rated"].forEach((k) => n.delete(k))))}>Clear all</Button>
              <Button variant="primary" disabled={sheetCount === 0} onClick={() => { setParams(sheet); setSheet(null); }}>{sheetCount === 0 ? "Show no intents" : `Show ${sheetCount ?? ""} intents`.replace("  ", " ")}</Button>
            </div>
          </div>
        )}
      </dialog>
    </section>
  );
}
