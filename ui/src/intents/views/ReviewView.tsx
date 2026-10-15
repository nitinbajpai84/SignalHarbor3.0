import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { apiGet, apiSend } from "../../api/client";
import ScreenState from "../../components/ScreenState";
import { useLoad } from "../../components/useLoad";
import { Button, Chip, DataTable, PageFrame, Pill, SideCard, StatCard, StatGrid } from "../../design";

// Spec 40: the reviewer's week (Screen A), the session (B), closing (C), trends (D) and the reporter's page (E, exported as MineView).

type Fate = "problem" | "backlog" | "handled" | "nothing";
interface Item {
  id: string; kind: "broke" | "ran" | "thought"; text: string; severity: string | null; count: number | null; amount: number | { value: number; currency: string } | null; ref: string | null;
  topic: string | null; unit?: string | null; people_count: number | null; seen_weeks: number | null; fate: Fate | null; fate_reason: string | null; fate_ref: string | null;
  by_name: string | null; anonymous?: boolean; history?: { fate: Fate; fate_reason: string }[];
}
interface Group { kind: Item["kind"]; ref?: string | null; topic?: string | null; item_ids: string[]; line: string; source_item_ids: string[] }
interface Clock { now: string; ends_at: string; remaining_seconds: number }
interface Week {
  week_key: string; title?: string; state: string; participants_count: number; responded_count: number; items: Item[]; collecting?: boolean;
  severity_summary?: { items: Record<string, number>; times: number; amounts: { currency: string; value: number }[] }; areas?: string[]; version?: number;
  digest: { fallback?: boolean; groups: Group[]; repeats: { item_id: string; seen_in: string[]; split: boolean }[]; summary_line: string } | null;
  session: { started_at: string; ended_at: string | null; minutes_used: number | null } | null; closure: { summary: string; closed_at: string } | null;
  read_only: boolean; clock: Clock | null; broke_open: string[]; viewer: { is_reviewer: boolean; can_decide: boolean; can_close: boolean };
}
interface Trends {
  available: boolean; closed_weeks: number; reason?: string; weeks?: string[]; rows?: { process: string | null; counts: number[]; total: number }[]; processes?: (string | null)[];
  repeated?: { text: string; process: string | null; weeks: string[]; seen_weeks: number; latest_fate: Fate | null; latest_week: string }[]; reading?: string; title?: string;
}

export const reviewCopy = {
  kind: { broke: "Broke", ran: "Ran well", thought: "On your mind" } as Record<string, string>,
  sections: ["broke", "ran", "thought", "repeats"] as const,
  sectionName: { broke: "Broke", ran: "Ran well", thought: "On your mind", repeats: "Repeats" } as Record<string, string>,
  state: { collecting: "Collecting", ready: "Ready to review", reviewing: "In review", in_session: "In review session", closing: "Closing", closed: "Closed" } as Record<string, string>,
  fates: { problem: "Becomes a Problem", backlog: "Goes to the backlog", handled: "Already handled", nothing: "Nothing" } as Record<Fate, string>,
  fateDone: { problem: "Became a Problem", backlog: "Went to the backlog", handled: "Already handled", nothing: "Nothing" } as Record<Fate, string>,
  severity: { stopped: "Stopped us", slowed: "Slowed us", cost: "Cost money", cost_money: "Cost money" } as Record<string, string>,
  noAnswers: "Not available yet: the week has no answers recorded.",
  collecting: "Not available yet: the week is still collecting answers.",
  nothingHere: "Nothing in this section.",
  notLinked: "Not linked",
  noItems: "No items this week.",
  needs: "Needs a decision",
  none: "No decision yet",
  why: "Why? Say it in a line.",
  whyError: "Please say why.",
  save: "Save decision",
  change: "Change decision",
  notSame: "Not the same",
  startSession: "Start review session",
  noReview: "Nothing to review: the week has no items.",
  close: "Close the week",
  northOff: "North has nothing to add yet.",
  northNoGroup: "North could not group this week's items. They are listed as written.",
  use: "Use this",
  askNorth: "Ask North",
  linkHandled: "Link to what handled it",
  linkProblem: "Problem created (its id or page)",
  linkBacklog: "Backlog item added (its id or page)",
  createProblem: "Create the Problem draft",
  createBacklog: "Add to the backlog",
  newTitle: "Title",
  areasLabel: "Areas",
  orLink: "Or link one that already exists (its id)",
  draftLabel: "North's draft, yours to edit",
  draftFallback: "North could not word these lines this time. They are the counted lines.",
  allOfThem: "Show the whole group",
  openProblem: "Open the Problem draft",
  openBacklog: "Open the backlog item",
  sevHead: "How hard it bit",
  noSeverity: "Not available yet: no broke items this week.",
  refused: "You cannot open this week.",
  notReview: "There is no review here. Only the reviewer of a check-in reads its weeks.",
  chooseHead: "Choose a week to review",
  noWeeks: "No weeks to review yet. The first one opens when the check-in starts.",
  trendsNone: "No item has come up in more than one week.",
  noProcesses: "No processes recorded yet.",
  mineEmpty: "You did not add an item this week.",
  mineHead: (d: string) => `Your items, week of ${d}`,
  seeAll: "See the whole week",
  needsFor: (n: number) => `${n} broke item${n === 1 ? "" : "s"} still ${n === 1 ? "needs" : "need"} a decision`,
  seen: (n: number) => `Seen ${n} weeks`,
  undecided: (n: number) => `${n} item${n === 1 ? " has" : "s have"} no decision. They close as Nothing with the reason "Not reviewed this week".`,
};
const t = reviewCopy;
const day = (key: string) => { const d = new Date(`${key}T00:00:00`); return `${d.getDate()} ${["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][d.getMonth()]}`; };
const sev = (s: string | null) => (s ? t.severity[s] ?? "Not marked" : "Not marked");
const money = (a: Item["amount"]) => (a && typeof a === "object" ? `${a.currency} ${a.value}` : a ? String(a) : "");
const sevChip = (i: Item) => [sev(i.severity), i.count ? `${i.count} ${i.unit ?? "times"}` : "", money(i.amount)].filter(Boolean).join(", ");
const fateLink = (fate: Fate | null, ref: string | null, from: string) => (!ref ? null : ref.startsWith("/centre/") ? ref : fate === "problem" ? `/centre/intent/new?type=problem&from=${from}&draft=${ref}` : fate === "backlog" ? `/centre/intent/backlog?item=${ref}` : `/centre/intent/${ref}`);
const fail = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong. Try again.");
const wk = (id: string, key: string) => `/api/intents/${id}/weeks/${key}`;

function SourceChip({ ids, items, active, onToggle }: { ids: string[]; items: Item[]; active: boolean; onToggle: () => void }) {
  const n = ids.filter((i) => items.some((x) => x.id === i)).length;
  return n ? <Chip tone={active ? "active" : "default"} onClick={onToggle}>{active ? t.allOfThem : `${n} item${n === 1 ? "" : "s"}`}</Chip> : null;
}

function Decision({ intentId, week, item, onDone }: { intentId: string; week: Week; item: Item; onDone: () => void }) {
  const [fate, setFate] = useState<Fate | null>(null);
  const [reason, setReason] = useState("");
  const [ref, setRef] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [title, setTitle] = useState(item.text.length > 80 ? item.text.slice(0, 80).replace(/\s+\S*$/, "") : item.text);
  const [areas, setAreas] = useState<string[]>(week.areas ?? []);
  const makes = fate === "problem" || fate === "backlog";
  const need = fate === "handled" ? t.linkHandled : makes ? t.orLink : null;
  const save = async (create: boolean) => {
    if (!reason.trim()) return setErr(t.whyError);
    setBusy(true);
    try { await apiSend("POST", `${wk(intentId, week.week_key)}/items/${item.id}/fate`, { fate, reason, fate_ref: ref, ...(create ? { create: { title, areas } } : {}) }); setFate(null); onDone(); } catch (e) { setErr(fail(e)); } finally { setBusy(false); }
  };
  if (!fate) return (
    <div role="group" aria-label="Decision" style={row}>
      {(Object.keys(t.fates) as Fate[]).map((f) => <Chip key={f} onClick={() => { setFate(f); setReason(f === "problem" && (item.seen_weeks ?? 1) > 2 ? `Seen ${item.seen_weeks} weeks running` : ""); setRef(""); setErr(""); }}>{t.fates[f]}</Chip>)}
    </div>
  );
  return (
    <div style={{ display: "grid", gap: 8 }}>
      <strong>{t.fates[fate]}</strong>
      <label>{t.why}<input style={field} value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} aria-label={t.why} /></label>
      {makes && <>
        <label>{t.newTitle}<input style={field} value={title} maxLength={200} onChange={(e) => setTitle(e.target.value)} aria-label={t.newTitle} /></label>
        {(week.areas ?? []).length > 0 && <fieldset style={{ border: 0, padding: 0, margin: 0 }}><legend>{t.areasLabel}</legend>
          {(week.areas ?? []).map((a) => <label key={a} style={{ ...row, minHeight: 44 }}><input type="checkbox" checked={areas.includes(a)} onChange={() => setAreas(areas.includes(a) ? areas.filter((x) => x !== a) : [...areas, a])} /> {a}</label>)}</fieldset>}
        <div><Button variant="primary" disabled={busy || !title.trim()} onClick={() => save(true)}>{fate === "problem" ? t.createProblem : t.createBacklog}</Button></div></>}
      {need && <label>{need}<input style={field} value={ref} onChange={(e) => setRef(e.target.value)} aria-label={need} /></label>}
      {err && <p role="alert" className="ds-warn">{err}</p>}
      <div style={row}>{(!makes || ref.trim()) && <Button variant="primary" disabled={busy} onClick={() => save(false)}>{t.save}</Button>}<Button onClick={() => setFate(null)}>Cancel</Button></div>
    </div>
  );
}

const row: CSSProperties = { display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" };
const field: CSSProperties = { display: "block", width: "100%", boxSizing: "border-box", marginTop: 4, minHeight: 44, padding: "8px 10px", borderRadius: 8, border: "1px solid var(--ds-line-2)", background: "var(--ds-surface-2)", color: "var(--ds-ink)", font: "inherit" };
const card: CSSProperties = { padding: 14, display: "grid", gap: 8, scrollMarginTop: 80 };

function ItemCard({ intentId, week, item, onDone }: { intentId: string; week: Week; item: Item; onDone: () => void }) {
  const [editing, setEditing] = useState(false);
  const rep = week.digest?.repeats.find((r) => r.item_id === item.id);
  const split = async () => { await apiSend("POST", `${wk(intentId, week.week_key)}/digest`, { split: item.id }); onDone(); };
  return (
    <div className="ds-card" style={card} id={`item-${item.id}`}>
      <div style={row}>
        <Chip>{t.kind[item.kind]}</Chip>
        {item.ref && <Chip>{item.ref}</Chip>}
        <span className="ds-muted">{item.anonymous ? "Anonymous" : item.by_name}</span>
        {(item.seen_weeks ?? 1) > 1 && <span title={rep ? `Also in: ${rep.seen_in.map(day).join(", ")}` : undefined}><Chip tone="active">{t.seen(item.seen_weeks ?? 1)}</Chip></span>}
        {item.kind === "broke" && <Chip>{sevChip(item)}</Chip>}
      </div>
      <p style={{ margin: 0 }}>{item.text}</p>
      {rep && !rep.split && week.viewer.can_decide && <div><Button onClick={split}>{t.notSame}</Button></div>}
      {item.fate && !editing ? (
        <div style={row}>
          <Pill tone="signed">{t.fateDone[item.fate]}</Pill><span className="ds-soft">{item.fate_reason}</span>
          {item.fate_ref && (fateLink(item.fate, item.fate_ref, intentId) ? <Link to={fateLink(item.fate, item.fate_ref, intentId) ?? ""}>{item.fate === "problem" ? t.openProblem : item.fate === "backlog" ? t.openBacklog : "Open it"}</Link> : <span className="ds-muted">{item.fate_ref}</span>)}
          {week.viewer.can_decide && <Button onClick={() => setEditing(true)}>{t.change}</Button>}
        </div>
      ) : week.viewer.can_decide ? (
        <><span className={item.kind === "broke" ? "ds-warn" : "ds-muted"}>{item.kind === "broke" ? t.needs : t.none}</span>
          <Decision intentId={intentId} week={week} item={item} onDone={() => { setEditing(false); onDone(); }} /></>
      ) : <span className="ds-muted">{t.none}</span>}
    </div>
  );
}

function CloseSheet({ intentId, week, draft, onClose, onDone }: { intentId: string; week: Week; draft: string; onClose: () => void; onDone: () => void }) {
  const [summary, setSummary] = useState(draft);
  const [err, setErr] = useState("");
  const left = week.items.filter((i) => !i.fate);
  const go = async () => { try { await apiSend("POST", `${wk(intentId, week.week_key)}/close`, { summary }); onDone(); } catch (e) { setErr(fail(e)); } };
  return (
    <div className="ds-card" style={{ ...card, position: "fixed", right: 0, top: 0, bottom: 0, width: "min(480px, 100%)", overflow: "auto", zIndex: 20, borderRadius: 0 }} role="dialog" aria-label={t.close}>
      <h2 style={{ margin: 0 }}>{t.close}</h2>
      <label>Summary, from North, yours to edit<textarea style={{ ...field, minHeight: 90 }} value={summary} onChange={(e) => setSummary(e.target.value)} placeholder="North could not draft this. Write one line." /></label>
      {week.items.length ? week.items.map((i) => <p key={i.id} style={{ margin: 0 }} className="ds-soft"><strong>{i.fate ? t.fateDone[i.fate] : "No decision"}</strong>: {i.text.slice(0, 60)}{i.fate_reason ? ` (${i.fate_reason})` : ""}</p>)
        : <p>No items this week. The week closes as: nothing came in.</p>}
      {left.length > 0 && <p className="ds-warn">{t.undecided(left.length)}</p>}
      {err && <p role="alert" className="ds-warn">{err}</p>}
      <div style={row}><Button variant="primary" disabled={week.broke_open.length > 0} onClick={go}>{t.close}</Button><Button onClick={onClose}>Cancel</Button></div>
    </div>
  );
}

function useTick(clock: Clock | null): number | null {
  const [n, setN] = useState(0);
  useEffect(() => { setN(0); if (!clock) return; const h = setInterval(() => setN((x) => x + 1), 1000); return () => clearInterval(h); }, [clock?.now]);
  return clock ? clock.remaining_seconds - n : null; // the server sent the remaining time; the browser only counts seconds down
}

function Session({ intentId, week, items, reload, back }: { intentId: string; week: Week; items: Item[]; reload: () => void; back: () => void }) {
  const [params, setParams] = useSearchParams();
  const [i, setI] = useState(Math.max(0, items.findIndex((x) => x.id === params.get("item"))));
  const [ask, setAsk] = useState(false);
  const [err, setErr] = useState("");
  const left = useTick(week.clock);
  const cur = items[i];
  const proj = useRef<HTMLDivElement>(null);
  const act = async (a: string) => { try { await apiSend("POST", `${wk(intentId, week.week_key)}/session`, { act: a }); if (a === "end") back(); else reload(); } catch (e) { setErr(fail(e)); } };
  const go = (n: number) => { setAsk(false); setI(n); setParams((prev) => { const p = new URLSearchParams(prev); p.set("item", items[n]?.id ?? ""); return p; }, { replace: true }); };
  const next = () => (cur?.kind === "broke" && !cur.fate ? setAsk(true) : go(i + 1));
  const mm = left === null ? "Not started" : `${String(Math.floor(Math.max(left, 0) / 60)).padStart(2, "0")}:${String(Math.max(left, 0) % 60).padStart(2, "0")}`;
  const open = items.filter((x) => !x.fate).length;
  return (
    <div style={{ display: "grid", gap: 12 }}>
    <div ref={proj} className="ds-card" style={{ ...card, minHeight: 360, padding: 24 }} aria-label="Review session">
      <div style={{ ...row, justifyContent: "space-between" }}>
        <strong>{cur ? t.kind[cur.kind] : ""}{cur?.ref ? `, ${cur.ref}` : ""}</strong>
        <strong className={left !== null && left <= 300 ? "ds-warn" : undefined} style={{ fontSize: 28 }} aria-live="off">{mm}{left !== null && left > 0 && left <= 300 ? " (5 minutes left)" : ""}</strong>
      </div>
      {left !== null && left <= 0 && <p className="ds-warn">The 30 minutes are up. {open} items are still open. Extend by 10 minutes, or end the session. <Button onClick={() => act("extend")}>Extend 10 minutes</Button></p>}
      {!week.clock && <Button variant="primary" disabled={!week.items.length} onClick={() => act("start")}>Start session</Button>}
      {cur ? (
        <>
          <p style={{ fontSize: 24, margin: "12px 0" }}>{cur.text}</p>
          <div style={row}>{(cur.seen_weeks ?? 1) > 1 && <Chip tone="active">{t.seen(cur.seen_weeks ?? 1)}</Chip>}{cur.kind === "broke" && <Chip>{sevChip(cur)}</Chip>}
            {cur.fate && <Pill tone="signed">{t.fateDone[cur.fate]}</Pill>}</div>
        </>
      ) : <p>All items are reviewed. <Button variant="primary" onClick={back}>{t.close}</Button></p>}
      {ask && <p role="alert">This broke item has no decision. Move on and come back? <Button onClick={() => go(i + 1)}>Move on</Button> <Button onClick={() => setAsk(false)}>Stay</Button></p>}
      {err && <p role="alert" className="ds-warn">{err}</p>}
      <div style={row}>
        <Button disabled={i === 0} onClick={() => go(i - 1)}>Previous item</Button>
        <Button disabled={i >= items.length - 1} onClick={next}>Next item</Button>
        <Button onClick={() => (week.clock ? act("end") : back())} disabled={!week.clock}>End session</Button>
        <Chip onClick={() => (document.fullscreenElement ? document.exitFullscreen() : proj.current?.requestFullscreen?.())}>Projector view</Chip>
      </div>
      <p className="ds-muted">Item {items.length ? i + 1 : 0} of {items.length}, {items.filter((x) => x.fate).length} decided</p>
    </div>
    {cur && week.viewer.can_decide && (!cur.fate ? <div className="ds-card" style={card} aria-label="Your decision, not shown on the projector"><span className="ds-muted">Your decision. Not shown on the projector.</span><Decision key={cur.id} intentId={intentId} week={week} item={cur} onDone={reload} /></div> : <p className="ds-soft">{t.fateDone[cur.fate]}: {cur.fate_reason}</p>)}
    </div>
  );
}

function Review({ intentId, weekKey }: { intentId: string; weekKey: string }) {
  const [params, setParams] = useSearchParams();
  const [tick, setTick] = useState(0);
  const [closing, setClosing] = useState(window.location.hash === "#close");
  const { state, data: w, message, retry } = useLoad<Week>(() => apiGet(wk(intentId, weekKey)), `${intentId}/${weekKey}/${tick}`);
  const reload = () => setTick((n) => n + 1);
  const section = params.get("section") ?? "broke";
  const mode = params.get("mode") === "session" || params.get("view") === "session";
  const [fold, setFold] = useState<Record<string, boolean>>({});
  const [only, setOnly] = useState<Record<string, boolean>>({});
  const nav = useNavigate();
  if (state === "refused" || (state === "error" && message === "We could not find that.")) return <p role="status" className="state">{state === "refused" ? message ?? t.refused : t.notReview}</p>;
  return (
    <ScreenState state={state} message={state === "error" ? message ?? t.refused : undefined} onRetry={retry}>
      {w && (() => {
        const items = w.items;
        const decided = items.filter((i) => i.fate).length;
        const broke = items.filter((i) => i.kind === "broke");
        const repeats = items.filter((i) => (i.seen_weeks ?? 1) > 1);
        const inSection = (s: string) => (s === "repeats" ? repeats : items.filter((i) => i.kind === s));
        const order = [...items.filter((i) => i.kind === "broke"), ...items.filter((i) => i.kind === "thought"), ...items.filter((i) => i.kind === "ran")];
        const open = (id: string) => { setParams((prev) => { const p = new URLSearchParams(prev); p.set("item", id); const it = items.find((x) => x.id === id); if (it) p.set("section", it.kind); return p; }); setTimeout(() => document.getElementById(`item-${id}`)?.scrollIntoView?.({ block: "center" }), 50); };
        const lines = (w.digest?.groups ?? []).filter((g) => (section === "repeats" ? false : g.kind === section));
        const groupItems = (g: Group) => g.item_ids.map((id) => items.find((x) => x.id === id)).filter((x): x is Item => !!x);
        const head = `${w.title ?? "Weekly check-in"}, week of ${day(w.week_key)}`;
        const actions = w.viewer.is_reviewer && !w.read_only ? <>
          <Button disabled={!items.length} title={items.length ? undefined : t.noReview} onClick={() => setParams((prev) => { const p = new URLSearchParams(prev); p.set("mode", "session"); return p; })}>{t.startSession}</Button>
          <Button variant="primary" disabled={w.broke_open.length > 0} onClick={() => setClosing(true)}>{t.close}</Button></> : w.viewer.can_close ? <Button variant="primary" disabled={w.broke_open.length > 0} onClick={() => setClosing(true)}>{t.close}</Button> : null;
        const sessionBody = mode ? <Session intentId={intentId} week={w} items={order} reload={reload} back={() => { setParams((prev) => { const p = new URLSearchParams(prev); p.delete("mode"); p.delete("view"); return p; }); reload(); }} /> : null;
        return (
          <PageFrame title={head} subline={<><Pill tone={w.state === "closed" ? "ok" : "open"}>{t.state[w.state] ?? w.state}</Pill>{" "}<Link to={`/centre/intent/${intentId}/review?view=trends`}>Trends</Link></>} actions={actions}
            aside={<>
              <SideCard title="North" tone="teal" note="A suggestion. You decide.">
                {w.digest?.summary_line ? <><p>{w.digest.summary_line}</p><p className="ds-muted">{repeats.length} repeat{repeats.length === 1 ? "" : "s"} matched to earlier weeks. You may split any match.</p></> : <p>{t.northOff}</p>}
              </SideCard>
              <SideCard title="Decisions"><p>{items.length ? `${broke.filter((i) => i.fate).length} of ${broke.length} broke items decided. ${decided - broke.filter((i) => i.fate).length} of ${items.length - broke.length} other items decided.` : t.noItems}</p></SideCard></>}>
            {w.collecting ? <ScreenState state="empty" message={t.collecting} /> : sessionBody ?? (
              <>
                {w.responded_count === 0 && !items.length ? <p className="ds-muted">{t.noAnswers}</p> : (
                  <StatGrid cols={4}>
                    <StatCard label="Answered" value={`${w.responded_count} of ${w.participants_count}`} />
                    <StatCard label="Items" value={items.length} />
                    <StatCard label="Broke" value={broke.length} note={`${repeats.length} repeat`} />
                    <StatCard label="Decided" value={`${decided} of ${items.length}`} note={w.broke_open.length ? t.needsFor(w.broke_open.length) : undefined} tone="warn" />
                  </StatGrid>)}
                {w.severity_summary && broke.length > 0 && (
                  <p className="ds-soft" aria-label={t.sevHead}>{t.sevHead}: {(["stopped", "slowed", "cost", "not_marked"] as const).map((k) => `${sev(k === "not_marked" ? null : k)} ${w.severity_summary?.items[k] ?? 0}`).join(", ")}
                    {w.severity_summary.times ? `. ${w.severity_summary.times} times in all` : ""}{w.severity_summary.amounts.length ? `. ${w.severity_summary.amounts.map((a) => `${a.currency} ${a.value}`).join(", ")} in all` : ""}.</p>)}
                {w.broke_open.length > 0 && <p><a href={`#item-${w.broke_open[0]}`} onClick={(e) => { e.preventDefault(); open(w.broke_open[0] ?? ""); }} className="ds-warn">{t.needsFor(w.broke_open.length)}</a></p>}
                <div role="tablist" style={row}>
                  {t.sections.map((s) => { const n = inSection(s).length; return <span key={s} style={{ opacity: n ? 1 : 0.55 }}><Chip tone={section === s ? "active" : "default"} onClick={() => setParams((prev) => { const p = new URLSearchParams(prev); p.set("section", s); p.delete("item"); return p; })}>{`${t.sectionName[s]} ${n}`}</Chip></span>; })}
                </div>
                {!inSection(section).length && <p className="ds-muted">{t.nothingHere}</p>}
                {w.digest?.fallback && w.digest.groups.length > 0 && <p className="ds-muted">{t.draftFallback}</p>}
                {!w.digest?.groups.length && items.length > 0 && <p className="ds-muted">{t.northNoGroup}</p>}
                {section === "repeats" ? repeats.map((i) => <ItemCard key={i.id} intentId={intentId} week={w} item={i} onDone={reload} />) : lines.map((g) => {
                  const key = `${g.kind}:${g.ref ?? g.topic}`; const label = g.kind === "thought" ? g.topic ?? t.notLinked : g.ref ?? t.notLinked;
                  return (
                    <section key={key} style={{ display: "grid", gap: 10 }}>
                      <h3 style={{ margin: 0, cursor: "pointer" }} onClick={() => setFold({ ...fold, [key]: !fold[key] })}>{label}: {g.item_ids.length} item{g.item_ids.length === 1 ? "" : "s"}</h3>
                      <p className="ds-soft" style={{ margin: 0 }}><Chip>{t.draftLabel}</Chip> {g.line} <SourceChip ids={g.source_item_ids} items={items} active={!!only[key]} onToggle={() => setOnly({ ...only, [key]: !only[key] })} /></p>
                      {!fold[key] && groupItems(g).filter((x) => !only[key] || g.source_item_ids.includes(x.id)).map((i) => <ItemCard key={i.id} intentId={intentId} week={w} item={i} onDone={reload} />)}
                    </section>);
                })}
                {w.viewer.can_decide && !w.read_only && w.state === "closing" && <p className="ds-muted">This week is past its close day.</p>}
                {w.closure && <SideCard title="Closed"><p>{w.closure.summary}</p></SideCard>}
              </>)}
            {closing && <CloseSheet intentId={intentId} week={w} draft={w.digest?.summary_line ?? ""} onClose={() => setClosing(false)} onDone={() => { setClosing(false); reload(); nav(`/centre/intent/${intentId}/review?week=${weekKey}`); }} />}
          </PageFrame>);
      })()}
    </ScreenState>
  );
}

function TrendsView({ intentId }: { intentId: string }) {
  const [range, setRange] = useState(0);
  const [proc, setProc] = useState("");
  const { state, data: d, message, retry } = useLoad<Trends>(() => apiGet(`/api/intents/${intentId}/trends?${range ? `range=${range}&` : ""}${proc ? `process=${encodeURIComponent(proc)}` : ""}`), `${intentId}/${range}/${proc}`);
  return (
    <ScreenState state={state} message={message} onRetry={retry}>
      {d && (
        <PageFrame title={d.title ? `${d.title}, trends` : "Weekly check-in trends"} subline="Counts of broke items from closed weeks"
          aside={<SideCard title="North's reading" tone="teal"><p>{d.available ? d.reading || t.trendsNone : d.reason}</p></SideCard>}>
          {!d.available ? <p>{d.reason}</p> : (
            <>
              <div style={row}>
                {[[4, "Last 4 weeks"], [8, "Last 8 weeks"], [0, "All weeks in the series"]].map(([n, l]) => <span key={String(n)} style={{ opacity: n === 8 && d.closed_weeks < 8 ? 0.55 : 1 }}><Chip tone={range === n ? "active" : "default"} onClick={() => setRange(n as number)}>{l as string}</Chip></span>)}
                <label>Process <select value={proc} onChange={(e) => setProc(e.target.value)} style={field}><option value="">All</option>{(d.processes ?? []).filter(Boolean).map((p) => <option key={p}>{p}</option>)}</select></label>
                {!d.processes?.length && <span className="ds-muted">{t.noProcesses}</span>}
              </div>
              <DataTable columns={[{ key: "p", label: "Process" }, ...(d.weeks ?? []).map((k) => ({ key: k, label: day(k) })), { key: "t", label: "Total" }]}
                rows={(d.rows ?? []).map((r) => ({ p: r.process ?? t.notLinked, ...Object.fromEntries((d.weeks ?? []).map((k, i) => [k, r.counts[i]])), t: r.total }))} />
              <h3>Repeated items</h3>
              {d.repeated?.length ? d.repeated.map((r) => (
                <Link key={r.text} className="ds-card" style={{ ...card, color: "inherit" }} to={`/centre/intent/${intentId}/review?week=${r.latest_week}`}>
                  <strong>{r.text}</strong><span className="ds-muted">{r.process ?? t.notLinked}, {r.weeks.map(day).join(", ")}. {t.seen(r.seen_weeks)}{r.latest_fate ? `. Latest: ${t.fateDone[r.latest_fate]}` : ""}</span>
                </Link>)) : <p>{t.trendsNone}</p>}
            </>)}
        </PageFrame>)}
    </ScreenState>
  );
}

/** Screen E, for the week view of file 38 to mount: the reporter's own items, their fate and the reason. */
export function MineView({ intentId, weekKey }: { intentId: string; weekKey: string }) {
  const { state, data, message, retry } = useLoad<{ items: Item[]; closed: boolean; note?: string; reviewer?: string }>(() => apiGet(`${wk(intentId, weekKey)}/mine`), `${intentId}/${weekKey}/mine`);
  const body: ReactNode = data && (!data.closed ? <p>{data.note}</p> : data.items.length ? data.items.map((i) => (
    <div key={i.id} className="ds-card" style={card}><div style={row}><Chip>{t.kind[i.kind]}</Chip>{i.anonymous && <Chip>Anonymous: only you can see this is yours</Chip>}{i.fate && <Pill tone="signed">{t.fateDone[i.fate]}</Pill>}</div>
      <p style={{ margin: 0 }}>{i.text}</p><span className="ds-soft">{i.fate_reason}</span>
      {i.fate_ref && <span className="ds-muted">{i.fate_ref.startsWith("/centre/") ? <Link to={i.fate_ref}>Open it</Link> : `${i.fate === "backlog" ? "A backlog item" : i.fate === "problem" ? "A Problem" : "Another record"} you cannot open. Ask ${data.reviewer ?? "the reviewer"} for access.`}</span>}</div>)) : <p>{t.mineEmpty}</p>);
  return <ScreenState state={state} message={message} onRetry={retry}><PageFrame title={t.mineHead(day(weekKey))}>{body}{<Link to={`/centre/intent/${intentId}/review?week=${weekKey}`}>{t.seeAll}</Link>}</PageFrame></ScreenState>;
}

function WeekChooser({ intentId }: { intentId: string }) {
  const { state, data, retry } = useLoad<{ weeks: { week_key: string; state: string }[] }>(() => apiGet(`/api/intents/${intentId}/weeks`), `${intentId}/weeks`);
  if (state === "loading") return <ScreenState state="loading" />;
  if (state === "refused" || state === "error" || !data) return <p role="status" className="state">{t.notReview}</p>;
  const weeks = [...data.weeks].reverse();
  if (!weeks.length) return <ScreenState state="empty" message={t.noWeeks} onRetry={retry} />;
  return <PageFrame title={t.chooseHead}><ul>{weeks.map((x) => <li key={x.week_key}><Link to={`/centre/intent/${intentId}/review?week=${x.week_key}`}>{`Week of ${day(x.week_key)}`}</Link> <span className="ds-muted">{t.state[x.state] ?? x.state}</span></li>)}</ul></PageFrame>;
}

/** /centre/intent/:intentId/review?week=<week_key> (spec 40). `view=trends` is Screen D; `mode=session` or `view=session` is Screen B. */
export default function ReviewView() {
  const { intentId = "" } = useParams<{ intentId: string }>();
  const [params] = useSearchParams();
  const week = params.get("week");
  if (params.get("view") === "trends") return <TrendsView intentId={intentId} />;
  if (params.get("view") === "mine") return week ? <MineView intentId={intentId} weekKey={week} /> : null;
  if (!week) return <WeekChooser intentId={intentId} />;
  return <Review intentId={intentId} weekKey={week} />;
}
