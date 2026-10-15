import { RadarThresholdsCard } from "./RadarThresholdsCard";
import { ProvingRulesCard } from "./ProvingPanel";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { ApiError, apiGet, apiSend } from "../api/client";
import ScreenState from "../components/ScreenState";
import { Button, Chip, Footnote, PageFrame, Pill, Strip, type PillTone } from "../design";

// All intents, counters and defaults for the company admin (spec 48, /centre/intent/admin?tab=). Reads only; the one act is a cancel with a reason.

const t = {
  title: "All intents", start: "Start something", download: "Download register (CSV)", nothingClosed: "Nothing closed yet",
  none: "No intents yet. They appear here when someone starts one.", noMatch: "No intent matches.", clear: "Clear filters", more: "Show more",
  tabs: { all: "All intents", overdue: "Overdue", unrated: "Unrated", counters: "Counters", defaults: "Defaults" },
  off: "The Intent centre is switched off for your company. Ask the platform operator.",
  filters: "Filters", search: "Search title and purpose", organiser: "Organiser", anyone: "Anyone", from: "Opened from", to: "Opened to", noArea: "No area",
  areas: "Areas", noAreas: "No areas yet.", setUpAreas: "Set up areas", tagPeople: "Tag people", sort: "Sort by",
  sorts: { opened: "Opened", ends: "Ends", title: "Title", type: "Type", state: "State" },
  cols: { title: "Title", kind: "Type and state", stage: "Stage", areas: "Areas", people: "People", dates: "Opened and ends", clock: "Clock", outcome: "Outcome", rating: "Rating" },
  types: { initiative: "Initiative", brainstorm: "Brainstorm", pulse: "Weekly check-in", problem: "Problem", decision: "Decision" } as Record<string, string>,
  states: { open: "Open", in_session: "In session", closing: "Closing", closed: "Closed", cancelled: "Cancelled" } as Record<string, string>,
  notStarted: "Not started", notClosed: "Not closed", notRated: "Not rated", byDesign: "Not rated by design", cancelledByAdmin: "Cancelled by admin",
  nextKinds: { initiative: "Initiative", problem: "Problem", decision: "Decision", backlog: "Backlog", handled: "Handled", nothing: "Nothing" } as Record<string, string>,
  nothingOverdue: "Nothing is overdue.", atRisk: "At risk", noSponsor: "No sponsor", every: "Every closed intent has at least one rating.",
  northLabel: "North", open: "Open", leaveHint: "Rows open the intent page.",
  counters: { empty: "No intents yet.", area: "Area", all: "All", untagged: (n: number) => `${n} ${n === 1 ? "person is" : "people are"} not tagged to any area and ${n === 1 ? "sees" : "see"} only what they are named in.`,
    everyone: "Everyone is tagged.", noAreaData: "Not available yet. No areas have been set up.", noArea: (n: number) => `${n} ${n === 1 ? "intent has" : "intents have"} no area.`, show: "Show them" },
  defaults: { time: "Time boxes", days: "working days", catalogue: "Catalogue default", changed: "Changed", weekly: "Weekly check-in", weeklyNote: "One week, recurring. Set by the check-in itself.",
    reset: "Back to catalogue defaults", sure: "Clear your time boxes?", yes: "Yes, clear them", keep: "Keep them", privacy: "Privacy",
    questions: "Weekly check-in questions", questionsNote: "Each organiser sets the four start questions when starting a check-in. The company does not change the wording here.",
    titles: "Keep intent titles private to this company", titlesNote: "The platform operator then sees that an intent exists, its type, state, areas and dates, but not its title.",
    affected: "Whether affected people may read an intent's content is chosen by its organiser when they start it. It is off unless they switch it on.",
    save: "Save defaults", discard: "Discard changes", saved: "Saved. New intents use these defaults. Open ones keep theirs.", bad: "That value is not valid. Use a whole number of one or more.",
    north: (type: string, mine: number, sum: number) => `Your ${type} time box is ${mine} working days. The stages add up to ${sum}. North will propose an extension early.` },
  cancel: { button: "Cancel this intent", warn: "This stops the intent. Its record is kept, shown in Past, and says you cancelled it and why. The organiser and sponsor are told.",
    reason: "Why are you cancelling it?", confirm: "Cancel this intent", keep: "Keep it running", changed: "This intent has just changed. Open it again to see where it stands." },
};

type Tab = keyof typeof t.tabs;
const TABS = Object.keys(t.tabs) as Tab[];
const TYPES = ["initiative", "brainstorm", "pulse", "problem", "decision"];
const STATES = ["open", "in_session", "closing", "closed", "cancelled"];

export interface AdminRow {
  id: string; type: string; title: string; purpose: string; state: string; bucket: string; stage: string | null; areas: string[]; organiser: string;
  sponsor: string | null; people_more: number; opened: string; ends: string; extensions: number; clock: { key: string; text: string };
  closed_at: string | null; outcome: { first_line: string; next: string[] } | null; rating: { count: number; mean: number | null; by_design: boolean };
  could_rate: number; cancelled_by_admin: boolean; days_overdue?: number;
}
interface ListOut {
  items: AdminRow[]; counts: { open: number; overdue: number; closed: number; cancelled: number; total: number }; next: number | null;
  tabs: { overdue: number; unrated: number }; organisers: string[]; areas: string[]; has_no_area: boolean; total_all: number; closed_in_view: number;
  north?: string | null; reminder_note?: string;
}
interface Counters {
  rows: { area: string; name: string; types: Record<string, { open: number; overdue: number; closed: number; cancelled: number }> }[];
  totals: Record<string, { open: number; overdue: number; closed: number; cancelled: number; total: number }>; untagged: number | null; areas_set_up: boolean; no_area: number; total: number;
}
interface Register { columns: string[]; rows: Record<string, string | number>[]; tz: string; company: string; company_name: string }
interface Settings {
  time_boxes: Record<string, { title: string; days: number; catalogue: number; changed: boolean; stages_total: number }>; titles_private: boolean;
}

/** Spec 48 spells the three reads /api/intents/admin/<what>, but the permission table does not name them yet; it does name
 *  /api/intents/settings, which answers the same reads with ?view=. Set this to true once the three /admin lines are in the table. */
const ADMIN_ROUTES_NAMED = true;

function adminGet<T>(what: "list" | "counters" | "register", qs: string): Promise<T> {
  return apiGet<T>(ADMIN_ROUTES_NAMED ? `/api/intents/admin/${what}${qs ? `?${qs}` : ""}` : `/api/intents/settings?view=${what}${qs ? `&${qs}` : ""}`);
}

const query = (o: Record<string, string | undefined>) => Object.entries(o).filter(([, v]) => v).map(([k, v]) => `${k}=${encodeURIComponent(v as string)}`).join("&");
const daysAgo = (iso: string | null) => (iso ? Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 86400000)) : 0);

function csvText(r: Register): string {
  const cell = (v: string | number | undefined) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  return "﻿" + [r.columns.map(cell).join(","), ...r.rows.map((row) => r.columns.map((c) => cell(row[c])).join(","))].join("\r\n") + "\r\n";
}

function saveCsv(r: Register) {
  const day = new Date().toLocaleDateString("en-CA", { timeZone: r.tz });
  const url = URL.createObjectURL(new Blob([csvText(r)], { type: "text/csv;charset=utf-8" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: `intent-register-${r.company}-${day}.csv` });
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

const style = `
.ia-tabs { display: flex; gap: 6px; flex-wrap: wrap; margin: 4px 0 12px; }
.ia-tabsel { display: none; min-height: 44px; margin: 4px 0 12px; padding: 8px 10px; border-radius: 8px; border: 1px solid var(--ds-line-2); background: var(--ds-ground); color: var(--ds-ink); font: inherit; width: 100%; }
.ia-filters { display: flex; flex-direction: column; gap: 10px; margin-bottom: 12px; }
.ia-filters__row { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.ia-filters label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--ds-ink-muted); }
.ia-filters input, .ia-filters select, .ia-field { min-height: 40px; box-sizing: border-box; padding: 8px 10px; border-radius: 8px; border: 1px solid var(--ds-line-2); background: var(--ds-ground); color: var(--ds-ink); font: inherit; font-size: 14px; }
.ia-fbtn { display: none; }
.ia-head, .ia-row { display: grid; grid-template-columns: minmax(180px, 2.2fr) 1.3fr 1fr 1fr 1fr 1.2fr 1.2fr 1.5fr 1fr; gap: 12px; align-items: start; padding: 12px 14px; }
.ia-head { font-size: 11px; letter-spacing: 1px; text-transform: uppercase; color: var(--ds-ink-muted); border-bottom: 1px solid var(--ds-line); }
.ia-head button { all: unset; cursor: pointer; }
.ia-row { border-bottom: 1px solid var(--ds-line); font-size: 13px; color: var(--ds-ink-soft); }
.ia-row small { display: block; color: var(--ds-ink-muted); font-size: 12px; margin-top: 2px; }
.ia-row a.ia-title { color: var(--ds-ink); font-weight: 600; font-size: 14px; }
.ia-list { padding: 0; overflow: hidden; }
.ia-chips { display: flex; gap: 4px; flex-wrap: wrap; }
.ia-amber { color: var(--ds-amber); }
.ia-simple { display: flex; flex-direction: column; gap: 4px; padding: 12px 14px; border-bottom: 1px solid var(--ds-line); font-size: 13px; color: var(--ds-ink-soft); }
.ia-card { padding: 16px 18px; margin-bottom: 14px; display: flex; flex-direction: column; gap: 10px; }
.ia-card h2 { margin: 0; font-size: 16px; }
.ia-box { display: grid; grid-template-columns: 1fr 120px 1fr; gap: 12px; align-items: center; font-size: 14px; }
.ia-box > span:first-child { font-weight: 600; } .ia-box > span:nth-child(2) { font-weight: 400; display: flex; gap: 8px; align-items: center; }
.ia-box .ia-grey { color: var(--ds-ink-muted); font-size: 12px; }
.ia-cnt { width: 100%; border-collapse: collapse; font-size: 13px; }
.ia-cnt th, .ia-cnt td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--ds-line); vertical-align: top; }
.ia-cnt td button { all: unset; cursor: pointer; color: var(--ds-teal-bright); }
.ia-bar { position: sticky; bottom: 0; display: flex; gap: 10px; align-items: center; padding: 12px 16px; background: var(--ds-surface); border-top: 1px solid var(--ds-line); margin-top: 8px; }
.ia-toast { color: var(--ds-teal-bright); font-size: 13px; }
.ia-dialog { position: fixed; inset: 0; background: rgba(0,0,0,.55); display: flex; align-items: center; justify-content: center; z-index: 50; }
.ia-dialog > div { width: min(480px, 100%); background: var(--ds-surface); border: 1px solid var(--ds-line-2); border-radius: 12px; padding: 20px; display: flex; flex-direction: column; gap: 12px; }
.ia-dialog textarea { min-height: 90px; padding: 10px; border-radius: 8px; border: 1px solid var(--ds-line-2); background: var(--ds-ground); color: var(--ds-ink); font: inherit; }
@media (max-width: 760px) {
  .ia-tabs { display: none; } .ia-tabsel { display: block; } .ia-fbtn { display: inline-flex; } .ia-filters[data-open="false"] { display: none; }
  .ia-head { display: none; }
  .ia-row { grid-template-columns: 1fr; gap: 6px; }
  .ia-box { grid-template-columns: 1fr; gap: 4px; }
  .ia-cnt, .ia-cnt tbody, .ia-cnt tr, .ia-cnt td, .ia-cnt th { display: block; width: 100%; box-sizing: border-box; } .ia-cnt thead { display: none; }
  .ia-cnt tr { border: 1px solid var(--ds-line); border-radius: 10px; margin-bottom: 10px; padding: 6px 4px; }
  .ia-dialog { align-items: stretch; } .ia-dialog > div { width: 100%; border-radius: 0; }
}
`;

const stateTone = (s: string): PillTone => (s === "closed" ? "signed" : s === "cancelled" ? "draft" : "open");
const clockTone = (k: string): PillTone => (k === "overdue" || k === "late" ? "late" : k === "at_risk" ? "failed" : k === "done" ? "ok" : "open");

function ratingText(r: AdminRow["rating"]): string {
  if (r.by_design) return t.byDesign;
  if (!r.count) return t.notRated;
  return r.mean !== null ? `${r.mean.toFixed(1)} from ${r.count}` : `${r.count} ${r.count === 1 ? "rating" : "ratings"}`;
}

const nameOf = (x: AdminRow) => x.title?.trim() || `${t.types[x.type] ?? x.type}${x.opened ? `, started ${x.opened}` : ""}`;

function Row({ x, extra }: { x: AdminRow; extra?: "overdue" | "unrated" }) {
  const nav = useNavigate();
  const go = () => nav(`/centre/intent/${x.id}`);
  if (extra) {
    return (
      <div className="ia-simple" onClick={go} style={{ cursor: "pointer" }}>
        <Link to={`/centre/intent/${x.id}`} className="ia-title" onClick={(e) => e.stopPropagation()}>{nameOf(x)}</Link>
        <span className="ia-chips"><Chip>{t.types[x.type]}</Chip>{x.stage ? <Chip>{x.stage}</Chip> : null}</span>
        {extra === "overdue"
          ? <small>{x.days_overdue ? `${x.days_overdue} ${x.days_overdue === 1 ? "day" : "days"} overdue` : x.clock.text}. {x.extensions ? `${x.extensions} ${x.extensions === 1 ? "extension" : "extensions"} used. ` : ""}Organiser {x.organiser}. {x.sponsor ?? t.noSponsor}.</small>
          : <small>Closed {daysAgo(x.closed_at)} days ago. Organiser {x.organiser}. {x.could_rate} {x.could_rate === 1 ? "person" : "people"} could rate.</small>}
      </div>
    );
  }
  return (
    <div className="ia-row" onClick={go} style={{ cursor: "pointer" }}>
      <div><Link to={`/centre/intent/${x.id}`} className="ia-title" onClick={(e) => e.stopPropagation()}>{nameOf(x)}</Link><small>{x.purpose}</small></div>
      <div className="ia-chips"><Chip>{t.types[x.type]}</Chip><Pill tone={stateTone(x.state)}>{t.states[x.state]}</Pill>{x.cancelled_by_admin ? <Pill tone="failed">{t.cancelledByAdmin}</Pill> : null}</div>
      <div>{x.stage ?? (x.state === "open" ? t.notStarted : "")}</div>
      <div className="ia-chips">{x.areas.length ? x.areas.map((a) => <Chip key={a}>{a}</Chip>) : <span className="ia-amber">{t.noArea}</span>}</div>
      <div>{x.organiser}{x.people_more ? <small>{`+${x.people_more} people`}</small> : null}</div>
      <div>{x.opened ? <>{x.opened}<small>{`to ${x.ends}`}{x.extensions ? `, ${x.extensions} extension${x.extensions === 1 ? "" : "s"}` : ""}</small></> : t.notStarted}</div>
      <div><Pill tone={clockTone(x.clock.key)}>{x.clock.text}</Pill></div>
      <div>{x.outcome ? <>{x.outcome.first_line}<span className="ia-chips">{x.outcome.next.map((k) => <Chip key={k}>{t.nextKinds[k] ?? k}</Chip>)}</span></> : x.state === "cancelled" ? t.states.cancelled : t.notClosed}</div>
      <div>{ratingText(x.rating)}</div>
    </div>
  );
}

function useAdminList(qs: string) {
  const [out, setOut] = useState<ListOut | null>(null);
  const [state, setState] = useState<"loading" | "error" | "refused" | "ok">("loading");
  const [msg, setMsg] = useState<string | undefined>();
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let live = true;
    setState("loading");
    adminGet<ListOut>("list", qs).then(
      (d) => { if (live) { setOut(d); setState("ok"); } },
      (e: unknown) => { if (live) { setMsg(e instanceof ApiError && e.status !== 0 && e.status < 500 ? e.message : undefined); setState(e instanceof ApiError && e.status === 403 ? "refused" : "error"); } });
    return () => { live = false; };
  }, [qs, attempt]);
  return { out, state, msg, retry: () => setAttempt((a) => a + 1) };
}

function AllTab({ initial }: { initial: Record<string, string> }) {
  const [f, setF] = useState<Record<string, string>>(initial);
  const [sort, setSort] = useState("opened");
  const [dir, setDir] = useState("desc");
  const [pages, setPages] = useState<AdminRow[]>([]);
  const [after, setAfter] = useState(0);
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState(initial.q ?? "");
  const [reg, setReg] = useState<"idle" | "busy" | "failed">("idle");
  useEffect(() => { const h = setTimeout(() => setF((o) => (o.q === q ? o : { ...o, q })), 350); return () => clearTimeout(h); }, [q]);
  const qs = useMemo(() => query({ ...f, sort, dir, after: after ? String(after) : undefined }), [f, sort, dir, after]);
  const base = useMemo(() => query({ ...f, sort, dir }), [f, sort, dir]);
  const { out, state, msg, retry } = useAdminList(qs);
  useEffect(() => { setAfter(0); setPages([]); }, [base]);
  useEffect(() => { if (out) setPages((p) => (after === 0 ? out.items : [...p, ...out.items])); }, [out]);  // eslint-disable-line react-hooks/exhaustive-deps
  const toggle = (key: string, v: string) => setF((o) => { const cur = (o[key] ?? "").split(",").filter(Boolean); const next = cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v]; return { ...o, [key]: next.join(",") }; });
  const on = (key: string, v: string) => (f[key] ?? "").split(",").includes(v);
  const clearAll = () => { setF({}); setQ(""); };
  const download = async () => {
    setReg("busy");
    try { saveCsv(await adminGet<Register>("register", query(f))); setReg("idle"); } catch { setReg("failed"); }
  };
  const c = out?.counts;
  const anyFilter = Object.values(f).some(Boolean);
  const head = (key: string, label: string) => <button type="button" onClick={() => { setDir(sort === key && dir === "desc" ? "asc" : "desc"); setSort(key); }}>{label}{sort === key ? (dir === "asc" ? " ▲" : " ▼") : ""}</button>;
  return (
    <ScreenState state={state === "ok" ? "populated" : state} message={state === "refused" ? msg ?? t.off : msg} onRetry={retry}>
      {out && out.total_all === 0 ? (
        <div className="n-empty"><p className="ebody">{t.none} <Link to="/centre/intent/new">{t.start}</Link></p></div>
      ) : out ? (
        <>
          <p className="ds-soft" data-testid="count-line">{c!.total} {c!.total === 1 ? "intent" : "intents"}: {c!.open} open, {c!.overdue} overdue, {c!.closed} closed, {c!.cancelled} cancelled</p>
          <button type="button" className="ds-btn ia-fbtn" aria-expanded={open} onClick={() => setOpen(!open)}>{t.filters}</button>
          <div className="ia-filters" data-open={open}>
            <div className="ia-filters__row" aria-label="Type">{TYPES.map((k) => <Chip key={k} tone={on("type", k) ? "active" : "default"} onClick={() => toggle("type", k)}>{t.types[k]}</Chip>)}</div>
            <div className="ia-filters__row" aria-label="State">{STATES.map((k) => <Chip key={k} tone={on("state", k) ? "active" : "default"} onClick={() => toggle("state", k)}>{t.states[k]}</Chip>)}</div>
            <div className="ia-filters__row" aria-label={t.areas}>
              {out.areas.length === 0 && !out.has_no_area ? <span className="ds-muted">{t.noAreas} <Link to="/centre/intent/admin/areas">{t.setUpAreas}</Link></span> : null}
              {out.areas.map((a) => <Chip key={a} tone={on("area", a) ? "active" : "default"} onClick={() => toggle("area", a)}>{a}</Chip>)}
              {out.has_no_area ? <Chip tone={on("area", "none") ? "active" : "default"} onClick={() => toggle("area", "none")}>{t.noArea}</Chip> : null}
            </div>
            <div className="ia-filters__row">
              <label>{t.search}<input type="search" value={q} onChange={(e) => setQ(e.target.value)} /></label>
              <label>{t.organiser}<select value={f.organiser ?? ""} onChange={(e) => setF({ ...f, organiser: e.target.value })}><option value="">{t.anyone}</option>{out.organisers.map((o) => <option key={o}>{o}</option>)}</select></label>
              <label>{t.from}<input type="date" value={f.opened_from ?? ""} onChange={(e) => setF({ ...f, opened_from: e.target.value })} /></label>
              <label>{t.to}<input type="date" value={f.opened_to ?? ""} onChange={(e) => setF({ ...f, opened_to: e.target.value })} /></label>
              <label>{t.sort}<select value={sort} onChange={(e) => setSort(e.target.value)}>{Object.entries(t.sorts).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
            </div>
          </div>
          {pages.length === 0 && out.counts.total === 0 ? (
            <div className="n-empty"><p className="ebody">{t.noMatch} {anyFilter ? <Button onClick={clearAll}>{t.clear}</Button> : null}</p></div>
          ) : (
            <section className="ds-card ia-list" aria-label={t.title}>
              <div className="ia-head">
                <span>{head("title", t.cols.title)}</span><span>{head("type", t.cols.kind)}</span><span>{t.cols.stage}</span><span>{t.cols.areas}</span><span>{t.cols.people}</span>
                <span>{head("opened", t.cols.dates)}</span><span>{head("ends", t.cols.clock)}</span><span>{t.cols.outcome}</span><span>{t.cols.rating}</span>
              </div>
              {pages.map((x) => <Row key={x.id} x={x} />)}
            </section>
          )}
          {out.next !== null ? <p><Button onClick={() => setAfter(out.next!)}>{t.more}</Button></p> : null}
          <p>
            <Button onClick={download} disabled={out.closed_in_view === 0 || reg === "busy"}>{out.closed_in_view === 0 ? t.nothingClosed : t.download}</Button>
            {reg === "failed" ? <span role="alert" className="ia-amber"> The register could not be made. Please try again.</span> : null}
          </p>
        </>
      ) : null}
    </ScreenState>
  );
}

function OverdueTab() {
  const over = useAdminList("overdue=1");
  const risk = useAdminList("at_risk=1");
  return (
    <ScreenState state={over.state === "ok" ? "populated" : over.state} message={over.state === "refused" ? over.msg ?? t.off : over.msg} onRetry={over.retry}>
      {over.out?.north ? <Strip label={t.northLabel}><p>{over.out.north}</p></Strip> : null}
      <section className="ds-card ia-list" aria-label={t.tabs.overdue}>
        {over.out?.items.length ? over.out.items.map((x) => <Row key={x.id} x={x} extra="overdue" />) : <p className="ia-simple">{t.nothingOverdue}</p>}
      </section>
      {risk.out?.items.length ? <><h2 style={{ fontSize: 14, margin: "16px 0 8px" }}>{t.atRisk}</h2><section className="ds-card ia-list">{risk.out.items.map((x) => <Row key={x.id} x={x} extra="overdue" />)}</section></> : null}
    </ScreenState>
  );
}

function UnratedTab() {
  const { out, state, msg, retry } = useAdminList("unrated=1");
  return (
    <ScreenState state={state === "ok" ? "populated" : state} message={state === "refused" ? msg ?? t.off : msg} onRetry={retry}>
      <section className="ds-card ia-list" aria-label={t.tabs.unrated}>
        {out?.items.length ? out.items.map((x) => <Row key={x.id} x={x} extra="unrated" />) : <p className="ia-simple">{t.every}</p>}
      </section>
      {out?.items.length ? <Footnote>{out.reminder_note}</Footnote> : null}
    </ScreenState>
  );
}

function CountersTab() {
  const nav = useNavigate();
  const [c, setC] = useState<Counters | null>(null);
  const [state, setState] = useState<"loading" | "error" | "ok">("loading");
  useEffect(() => { adminGet<Counters>("counters", "").then((d) => { setC(d); setState("ok"); }, () => setState("error")); }, []);
  const cell = (n?: { open: number; overdue: number; closed: number; cancelled: number }) => (n ? `${n.open} open, ${n.overdue} overdue, ${n.closed} closed, ${n.cancelled} cancelled` : "");
  const link = (area?: string, type?: string) => nav(`/centre/intent/admin?${query({ tab: "all", area, type })}`);
  return (
    <ScreenState state={state === "ok" ? "populated" : state} onRetry={() => location.reload()}>
      {c && c.total === 0 ? <p className="ia-simple">{c.areas_set_up ? t.counters.empty : <>{t.counters.empty} {t.noAreas} <Link to="/centre/intent/admin/areas">{t.setUpAreas}</Link></>}</p> : c ? (
        <>
          <table className="ds-card ia-cnt" aria-label={t.tabs.counters}>
            <thead><tr><th>{t.counters.area}</th>{TYPES.map((k) => <th key={k}>{t.types[k]}</th>)}<th>{t.counters.all}</th></tr></thead>
            <tbody>
              {c.rows.map((r) => (
                <tr key={r.area}><td>{r.name}</td>
                  {TYPES.map((k) => <td key={k}>{r.types[k] ? <button type="button" onClick={() => link(r.area, k)}>{cell(r.types[k])}</button> : ""}</td>)}
                  <td><button type="button" onClick={() => link(r.area)}>{cell(Object.values(r.types).reduce((a, n) => ({ open: a.open + n.open, overdue: a.overdue + n.overdue, closed: a.closed + n.closed, cancelled: a.cancelled + n.cancelled }), { open: 0, overdue: 0, closed: 0, cancelled: 0 }))}</button></td></tr>
              ))}
              <tr><td><strong>All areas</strong></td>{TYPES.map((k) => <td key={k}><button type="button" onClick={() => link(undefined, k)}>{cell(c.totals[k])}</button></td>)}<td>{c.total} in all</td></tr>
            </tbody>
          </table>
          <p className="ds-soft">{!c.areas_set_up || c.untagged === null ? t.counters.noAreaData : c.untagged === 0 ? t.counters.everyone : t.counters.untagged(c.untagged)}</p>
          {c.no_area ? <p className="ds-soft">{t.counters.noArea(c.no_area)} <button type="button" className="ds-btn" onClick={() => link("none")}>{t.counters.show}</button></p> : null}
          <p><Link to="/centre/intent/admin/areas">{t.setUpAreas}</Link> · <Link to="/centre/intent/admin/areas/people">{t.tagPeople}</Link></p>
        </>
      ) : null}
    </ScreenState>
  );
}

function DefaultsTab() {
  const [saved, setSaved] = useState<Settings | null>(null);
  const [days, setDays] = useState<Record<string, string>>({});
  const [priv, setPriv] = useState(false);
  const [state, setState] = useState<"loading" | "error" | "ok">("loading");
  const [toast, setToast] = useState("");
  const [asking, setAsking] = useState(false);
  const apply = useCallback((s: Settings) => {
    setSaved(s); setPriv(s.titles_private);
    setDays(Object.fromEntries(Object.entries(s.time_boxes).map(([k, v]) => [k, String(v.days)])));
  }, []);
  const load = useCallback(() => { apiGet<Settings>("/api/intents/settings").then((s) => { apply(s); setState("ok"); }, () => setState("error")); }, [apply]);
  useEffect(load, [load]);
  if (!saved) return <ScreenState state={state === "error" ? "error" : "loading"} onRetry={load} />;
  const whole = (v: string) => /^[1-9]\d*$/.test(v);
  const dirty = priv !== saved.titles_private || Object.entries(saved.time_boxes).some(([k, v]) => days[k] !== String(v.days));
  const invalid = Object.values(days).some((v) => !whole(v));
  const save = async () => {
    const time_boxes = Object.fromEntries(Object.entries(saved.time_boxes).filter(([k, v]) => days[k] !== String(v.days)).map(([k, v]) => [k, Number(days[k]) === v.catalogue ? null : Number(days[k])]));
    try { apply(await apiSend<Settings>("PUT", "/api/intents/settings", { time_boxes, titles_private: priv })); setToast(t.defaults.saved); } catch { setToast(t.defaults.bad); }
  };
  const reset = async () => {
    setAsking(false);
    try { apply(await apiSend<Settings>("PUT", "/api/intents/settings", { time_boxes: Object.fromEntries(Object.keys(saved.time_boxes).map((k) => [k, null])) })); setToast(t.defaults.saved); } catch { setToast(t.defaults.bad); }
  };
  const lines = Object.entries(saved.time_boxes).filter(([k, v]) => whole(days[k] ?? "") && Number(days[k]) < v.stages_total && v.stages_total > 0);
  return (
    <>
      <section className="ds-card ia-card">
        <h2>{t.defaults.time}</h2>
        {Object.entries(saved.time_boxes).map(([k, v]) => (
          <label key={k} className="ia-box">
            <span>{v.title}</span>
            <span><input className="ia-field" inputMode="numeric" aria-label={`${v.title} working days`} value={days[k] ?? ""} onChange={(e) => setDays({ ...days, [k]: e.target.value })} style={{ width: 64 }} /> {t.defaults.days}</span>
            <span className="ia-grey">{t.defaults.catalogue}: {v.catalogue}{whole(days[k] ?? "") && Number(days[k]) !== v.catalogue ? <> <Pill tone="restricted">{t.defaults.changed}</Pill></> : null}</span>
          </label>
        ))}
        <p className="ds-muted" style={{ margin: 0 }}><strong>{t.defaults.weekly}</strong>: {t.defaults.weeklyNote}</p>
        {lines.map(([k, v]) => <Strip key={k} label={t.northLabel} tone="amber"><p>{t.defaults.north(v.title, Number(days[k]), v.stages_total)}</p></Strip>)}
        {asking ? <p role="alertdialog">{t.defaults.sure} <Button onClick={reset}>{t.defaults.yes}</Button> <Button onClick={() => setAsking(false)}>{t.defaults.keep}</Button></p>
          : <p style={{ margin: 0 }}><Button disabled={Object.values(saved.time_boxes).every((v) => !v.changed)} onClick={() => setAsking(true)}>{t.defaults.reset}</Button></p>}
      </section>
      <section className="ds-card ia-card"><h2>{t.defaults.questions}</h2><p className="ds-soft" style={{ margin: 0 }}>{t.defaults.questionsNote}</p></section>
      <section className="ds-card ia-card">
        <h2>{t.defaults.privacy}</h2>
        <label style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
          <input type="checkbox" role="switch" checked={priv} onChange={(e) => setPriv(e.target.checked)} style={{ marginTop: 4 }} />
          <span>{t.defaults.titles}<br /><span className="ds-muted" style={{ fontSize: 12 }}>{t.defaults.titlesNote}</span></span>
        </label>
        <p className="ds-soft" style={{ margin: 0 }}>{t.defaults.affected}</p>
      </section>
      <RadarThresholdsCard />
      <ProvingRulesCard />
      <div className="ia-bar">
        <Button variant="primary" disabled={!dirty || invalid} onClick={save}>{t.defaults.save}</Button>
        <Button disabled={!dirty} onClick={() => { apply(saved); setToast(""); }}>{t.defaults.discard}</Button>
        {invalid ? <span role="alert" className="ia-amber">{t.defaults.bad}</span> : toast ? <span role="status" className="ia-toast">{toast}</span> : null}
      </div>
    </>
  );
}

/** The cancel dialog of screen D. The intent page shows it for the company admin while the intent is open, in session or closing. */
export function AdminCancelDialog({ intentId, onClose, onDone }: { intentId: string; onClose: () => void; onDone: () => void }): ReactNode {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const confirm = async () => {
    setBusy(true);
    try { await apiSend("POST", `/api/intents/${encodeURIComponent(intentId)}/admin-cancel`, { reason: reason.trim() }); onDone(); }
    catch (e) { setBusy(false); setError(e instanceof ApiError && e.status === 409 ? t.cancel.changed : e instanceof ApiError ? e.message : "That did not work. Please try again."); if (e instanceof ApiError && e.status === 409) setTimeout(onClose, 1800); }
  };
  return (
    <div className="ia-dialog" role="dialog" aria-modal="true" aria-label={t.cancel.button}>
      <style>{style}</style>
      <div>
        <p style={{ margin: 0 }}>{t.cancel.warn}</p>
        <label>{t.cancel.reason}<textarea value={reason} onChange={(e) => setReason(e.target.value)} /></label>
        {error ? <p role="alert" className="ia-amber" style={{ margin: 0 }}>{error}</p> : null}
        <div style={{ display: "flex", gap: 8 }}>
          <Button variant="primary" disabled={!reason.trim() || busy} onClick={confirm}>{t.cancel.confirm}</Button>
          <Button onClick={onClose}>{t.cancel.keep}</Button>
        </div>
      </div>
    </div>
  );
}

/** Company admin views (/centre/intent/admin). */
export default function IntentAdmin() {
  const [params, setParams] = useSearchParams();
  const tab = (TABS as string[]).includes(params.get("tab") ?? "") ? (params.get("tab") as Tab) : "all";
  const [counts, setCounts] = useState<{ overdue: number; unrated: number } | null>(null);
  useEffect(() => { adminGet<ListOut>("list", "limit=1").then((d) => setCounts(d.tabs), () => setCounts(null)); }, []);
  const label = (k: Tab) => (k === "overdue" && counts ? `${t.tabs[k]} (${counts.overdue})` : k === "unrated" && counts ? `${t.tabs[k]} (${counts.unrated})` : t.tabs[k]);
  const initial = useMemo(() => Object.fromEntries(["type", "state", "area", "organiser", "q", "opened_from", "opened_to"].map((k) => [k, params.get(k) ?? ""]).filter(([, v]) => v)), []); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <PageFrame title={t.title} actions={<Link to="/centre/intent/new" className="ds-btn">{t.start}</Link>}>
      <style>{style}</style>
      <nav className="ia-tabs" aria-label="Views">{TABS.map((k) => <Chip key={k} tone={tab === k ? "active" : "default"} href={`/centre/intent/admin?tab=${k}`}>{label(k)}</Chip>)}</nav>
      <select className="ia-tabsel" aria-label="View" value={tab} onChange={(e) => setParams({ tab: e.target.value })}>{TABS.map((k) => <option key={k} value={k}>{label(k)}</option>)}</select>
      {tab === "all" ? <AllTab key={params.toString()} initial={initial} /> : tab === "overdue" ? <OverdueTab /> : tab === "unrated" ? <UnratedTab /> : tab === "counters" ? <CountersTab /> : <DefaultsTab />}
    </PageFrame>
  );
}
