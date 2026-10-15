import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { apiGet, apiSend, ApiError, me } from "../../api/client";
import ScreenState from "../../components/ScreenState";
import { EventsLink } from "./EventsView";
import "./Decision.css";
import { Button, Chip, CommentThread, PageFrame, Pill, SideCard, type Comment } from "../../design";
import { useWide, workingDaysBetween } from "../start/DecisionStart";

// Spec 43 screens B (open), C (sign modal) and D (record). Panels by ?view=options|notes|decide|record (ruling 18).

interface Person { account_id: string | null; name: string }
interface Source { kind: string; ref: string; label: string; at: string }
interface Note { id: string; kind: "comment" | "suggestion"; text: string; by: string; at: string; state: string; decided_by: string | null; answer: string | null; by_account?: string }
export interface Option {
  id: string; name: string; means: string; for: string[]; against: string[]; needs: string; origin: "north" | "person" | "adviser" | "anonymous";
  by: string; at: string; confirmed_by: string | null; edited_by?: string | null; sources: Source[]; notes: Note[]; fallback?: boolean; accepted?: { text: string; by: string }[]; by_account?: string;
}
interface Rec { option_id: string | null; line: string; sources: Source[]; missing?: string[]; drafted_at: string; fallback?: boolean }
interface Outcome {
  question: string; options: Option[]; recommendation: Rec | null; chosen: string | null; why: string; why_drafted: boolean; decided_by: string | null;
  decided_at: string | null; no_decision_reason: string | null; deferral: { from: string; to: string; reason: string; at: string } | null;
  writes: { node_id: string | null; intent_id?: string; version: number | null; skipped?: string }[]; considered_snapshot: Option[];
  affects?: { node_id: string; type: string }[]; north?: { drafted_at: string; records: number; notes: number; drafted: number } | null;
}
export interface Intent {
  id: string; type: string; title: string; purpose: string; state: string; tier?: string; created_at?: string; areas: string[];
  people: { organiser: Person | string | null; decider: Person | string | null; advisers: (Person | string)[] };
  time_box: { ends: string }; outcome?: Outcome; closure?: { cancel_reason: string | null; closed_at: string | null }; links?: { from: string | null; to: string[] };
}
interface Node { id: string; type: string; label: string; restricted?: boolean }

/** An older record may lack lists the screen reads: read each missing one as empty. */
export function withDefaults(r: Intent): Intent {
  const o = (r.outcome ?? {}) as Partial<Outcome>;
  // An earlier seed wrote options as {id, text, drafted_by, added_by}: read them as cards with a name and an author (decision._shape).
  const opt = (x: Option & { text?: string; drafted_by?: string | null; added_by?: string | null }): Option => {
    const origin = x.origin ?? (x.drafted_by === "north" ? "north" : x.added_by === "adviser" ? "adviser" : "person");
    return { ...x, name: x.name || x.text || "", origin, by: x.by || (origin === "north" ? "North" : ""),
      for: x.for ?? [], against: x.against ?? [], sources: x.sources ?? [], notes: x.notes ?? [] };
  };
  return {
    ...r, areas: r.areas ?? [], people: { ...r.people, advisers: r.people?.advisers ?? [] },
    outcome: { question: "", chosen: null, why: "", why_drafted: false, decided_by: null, decided_at: null, no_decision_reason: null, deferral: null,
      recommendation: null, north: null, ...o, options: (o.options ?? []).map(opt), writes: o.writes ?? [], considered_snapshot: (o.considered_snapshot ?? []).map(opt), affects: o.affects ?? [] },
  };
}

export const viewCopy = {
  type: "Decision",
  states: { open: "Open", closing: "Recorded", closed: "Closed", cancelled: "Cancelled", draft: "Draft", in_session: "Open" } as Record<string, string>,
  decideBy: (d: string, left: number) => `Decide by ${d}, ${left} working ${left === 1 ? "day" : "days"} left`,
  over: (d: string) => `Decide by ${d}, the time box is over`,
  decider: "Decider",
  addOption: "Add an option",
  more: "More",
  share: "Share",
  changeDecider: "Change the decider",
  cancel: "Cancel this decision",
  keepOpen: "Keep it open",
  cancelReason: "Why is it cancelled?",
  askedBy: (n: string, d: string) => `Asked by ${n} on ${d}`,
  questionLocked: "Open a new decision to change the question",
  sourceChip: "Follows on from an earlier intent",
  options: "Options",
  noOptions: "No options yet",
  means: "What it means",
  for: "For",
  against: "Against",
  needs: "What it costs or needs",
  guessed: (n: number) => `Guessed by North, from ${n} ${n === 1 ? "record" : "records"}`,
  guessedNone: "Guessed by North, nothing recorded behind it",
  fallback: "Drafted from simple word rules: North's drafting service did not answer.",
  confirmed: (n: string) => `Confirmed by ${n}`,
  edited: (n: string) => `Edited by ${n}`,
  addedBy: (n: string) => `Added by ${n}`,
  addedAnon: "Added by an adviser",
  notesCount: (n: number) => `${n} ${n === 1 ? "note" : "notes"}`,
  counts: (f: number, a: number) => `For ${f} · Against ${a}`,
  accepted: (t: string) => `Accepted: ${t}`,
  noNotes: "No notes yet.",
  notePlaceholder: "Your view on this option",
  comment: "Comment",
  suggestion: "Suggestion",
  addNote: "Add a note",
  anonymous: "Anonymous",
  anonHelp: "Nobody will see who added this.",
  edit: "Edit",
  confirm: "Confirm",
  save: "Save",
  close: "Close",
  name: "Name",
  forLines: "For (one per line)",
  againstLines: "Against (one per line)",
  addOptionBtn: "Add option",
  cancelBtn: "Cancel",
  restsOnTitle: "Records behind this card",
  northDrafted: (o: number, r: number, n: number, at: string) => `North drafted ${o} ${o === 1 ? "option" : "options"} from ${r} ${r === 1 ? "record" : "records"} and ${n} ${n === 1 ? "note" : "notes"} at ${at}.`,
  notReplied: (n: number) => ` ${n} ${n === 1 ? "adviser has" : "advisers have"} not replied.`,
  northWaiting: "North has not drafted yet. It is waiting for the question.",
  redraft: "Redraft options",
  recTitle: "North's draft recommendation",
  recLabel: "Agent's draft. Not a decision.",
  restsOn: "Rests on:",
  noRec: "North has no recommendation. It needs at least two options and one record.",
  choiceTitle: "The decider's choice",
  pickOne: "Pick one option",
  pickHelp: "Press Choose on the option you pick.",
  later: "Decide later",
  none: "No decision",
  waitingFor: (n: string) => `Waiting for ${n}`,
  needOption: "Add at least one option first",
  choose: (n: string) => `Choose ${n}`,
  chooseShort: "Choose",
  laterDate: "New date",
  laterReason: "Why must it wait?",
  laterSave: "Move the date",
  laterDone: (d: string) => `Already extended once on ${d}. Pick or say no decision.`,
  noneReason: "Why is there no decision?",
  noneSave: "Record no decision",
  advisers: "Advisers",
  noAdvisers: "No advisers named. North drafted from records.",
  added: (n: number) => `Added ${n} ${n === 1 ? "note" : "notes"}`,
  addedOptions: (n: number) => `Added ${n} ${n === 1 ? "option" : "options"}`,
  noteTitle: "Your note",
  onOption: "On which option?",
  noteNoOptions: "No options yet. Add an option, then a note on it.",
  notRepliedYet: "Not replied yet",
  anonNotes: (n: number) => `Anonymous notes: ${n}`,
  nudge: "Nudge",
  nudged: "Nira sent a reminder.",
  nudgeNa: "Not available yet: reminders are not switched on.",
  showAll: "Show all notes",
  affects: "Affects",
  areas: "Areas",
  named: "Measures and processes named",
  noNamed: "No measure or process is named. Nothing will be written to the map.",
  nameNode: "Name a measure or process",
  noNodes: "No measures or processes on the map that you can see.",
  hiddenNode: "A measure you do not have access to",
  linked: "Linked intents",
  noLinked: "No linked intents.",
  banner: "This will not be decided inside the time box. Options: extend, close with no decision, cancel.",
  bannerWho: (n: string) => `${n} picks.`,
  signTitle: "Record your decision",
  summary: (n: string) => `You are choosing: ${n}. This will be recorded as your decision.`,
  why: "Why this option?",
  northWhy: "North's draft",
  useDraft: "Use North's draft",
  writesTitle: "What this writes",
  writesNode: (labels: string) => `A version note on: ${labels}.`,
  writesLink: "A link on the intent this follows from.",
  writesNone: "Nothing else is written. No measure or process is named.",
  record: "Record my decision",
  notYet: "Not yet",
  sayWhy: "Say why",
  decided: (o: string, n: string, d: string) => `Decided: ${o}. By ${n} on ${d}.`,
  noDecision: (r: string) => `No decision. Reason: ${r}`,
  cancelled: (r: string) => `Cancelled: ${r}`,
  waitingClose: (n: string) => `The decision is recorded. Waiting for ${n} to close this intent.`,
  closeIntent: "Close this intent",
  rate: "Rate this decision",
  whyTitle: "Why",
  considered: "Options considered",
  noConsidered: "No options were recorded.",
  chosen: "Chosen",
  recWas: (o: string) => `North's draft recommendation was ${o}`,
  noRecWas: "North made no recommendation.",
  wrote: "What it wrote",
  wroteNone: "Nothing else was written.",
  version: (l: string, v: number) => `${l}, version ${v}`,
  linkOn: "A link on the intent this follows from",
  deferral: (f: string, t: string, r: string) => `Decide-later used once: from ${f} to ${t}. Reason: ${r}`,
  gaveNote: "Gave a note",
  noNote: "Gave no note",
  existsOnly: "You can see that this decision exists. Its options and notes are for the people named on it.",
  loadFailed: "We could not load this decision. Try again.",
  failed: "That did not save. Try again.",
  panels: { options: "Options", notes: "Notes", decide: "Decide", record: "Record" } as Record<string, string>,
  notAvailable: "Not available yet",
};
const c = viewCopy;

const nameOf = (p: Person | string | null | undefined) => (typeof p === "string" ? p : p?.name ?? "");
const day = (s?: string | null) => (s ? new Date(s).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" }) : "");
const time = (s?: string | null) => (s ? new Date(s).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "UTC" }) : "");
const first = (n: string) => n.split(" ")[0] ?? n;

/** The mark on a card (spec 43 "Guessed mark"). */
export function markOf(o: Option): string {
  if (o.origin === "north") {
    if (o.confirmed_by) return c.confirmed(o.confirmed_by);
    if (o.edited_by) return c.edited(o.edited_by);
    const mark = o.sources.length ? c.guessed(o.sources.length) : c.guessedNone;
    return o.fallback ? `${mark}. ${c.fallback}` : mark;
  }
  return o.origin === "anonymous" || !o.by || o.by === "an adviser" ? c.addedAnon : c.addedBy(o.by);
}

/** Cards by creation time, newest last; a North card with no record behind it is shown last (never by North's lean). A card with no
 * name is never shown. */
export function ordered(all: Option[]): Option[] {
  const opts = all.filter((o) => o.name.trim());
  const bare = (o: Option) => o.origin === "north" && o.sources.length === 0;
  return [...opts.filter((o) => !bare(o)), ...opts.filter(bare)];
}

function Dialog({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.35)", display: "flex", alignItems: "flex-end", justifyContent: "center", zIndex: 50 }}>
      <div role="dialog" aria-modal="true" aria-label={title} className="ds-card" style={{ width: "min(520px, 100%)", padding: 20, margin: "auto auto", maxHeight: "90vh", overflow: "auto" }}>
        <h2 style={{ marginTop: 0 }}>{title}</h2>
        {children}
      </div>
    </div>
  );
}

function OptionForm({ onSave, onCancel, start, anonOk }: { onSave: (b: Record<string, unknown>) => void; onCancel: () => void; start?: Option; anonOk: boolean }) {
  const [name, setName] = useState(start?.name ?? "");
  const [means, setMeans] = useState(start?.means ?? "");
  const [fr, setFor] = useState((start?.for ?? []).join("\n"));
  const [ag, setAg] = useState((start?.against ?? []).join("\n"));
  const [needs, setNeeds] = useState(start?.needs ?? "");
  const [anon, setAnon] = useState(false);
  const lines = (s: string) => s.split("\n").map((x) => x.trim()).filter(Boolean);
  return (
    <div style={{ display: "grid", gap: 8 }}>
      <label>{c.name}<input value={name} maxLength={60} onChange={(e) => setName(e.target.value)} style={{ width: "100%" }} /></label>
      <label>{c.means}<textarea value={means} maxLength={400} rows={2} onChange={(e) => setMeans(e.target.value)} style={{ width: "100%" }} /></label>
      <label>{c.forLines}<textarea value={fr} rows={2} onChange={(e) => setFor(e.target.value)} style={{ width: "100%" }} /></label>
      <label>{c.againstLines}<textarea value={ag} rows={2} onChange={(e) => setAg(e.target.value)} style={{ width: "100%" }} /></label>
      <label>{c.needs}<input value={needs} maxLength={400} onChange={(e) => setNeeds(e.target.value)} style={{ width: "100%" }} /></label>
      {anonOk && (
        <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input type="checkbox" role="switch" checked={anon} onChange={(e) => setAnon(e.target.checked)} />{c.anonymous}
        </label>
      )}
      {anon && <p className="n-muted">{c.anonHelp}</p>}
      <div style={{ display: "flex", gap: 8 }}>
        <Button variant="primary" disabled={!name.trim()} onClick={() => onSave({ name, means, for: lines(fr), against: lines(ag), needs, anonymous: anon })}>{start ? c.save : c.addOptionBtn}</Button>
        <Button onClick={onCancel}>{c.cancelBtn}</Button>
      </div>
    </div>
  );
}

function NoteForm({ onSave }: { onSave: (b: Record<string, unknown>) => Promise<boolean> }) {
  const [text, setText] = useState("");
  const [kind, setKind] = useState<"comment" | "suggestion">("comment");
  const [anon, setAnon] = useState(false);
  return (
    <div style={{ display: "grid", gap: 6, marginTop: 8 }}>
      <input aria-label={c.addNote} placeholder={c.notePlaceholder} maxLength={300} value={text} onChange={(e) => setText(e.target.value)} />
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <select aria-label="Kind of note" value={kind} onChange={(e) => setKind(e.target.value as "comment" | "suggestion")}>
          <option value="comment">{c.comment}</option><option value="suggestion">{c.suggestion}</option>
        </select>
        <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <input type="checkbox" role="switch" checked={anon} onChange={(e) => setAnon(e.target.checked)} />{c.anonymous}
        </label>
        <Button disabled={!text.trim()} onClick={() => void onSave({ text, kind, anonymous: anon }).then((ok) => ok && setText(""))}>{c.addNote}</Button>
      </div>
      {anon && <p className="n-muted">{c.anonHelp}</p>}
    </div>
  );
}

/** The Notes view's own box: pick the option, then the same note field the cards carry (spec 43 "Add a note"). */
function NoteBox({ options, onSave }: { options: Option[]; onSave: (optionId: string, b: Record<string, unknown>) => Promise<boolean> }) {
  const [sel, setSel] = useState(options[0]?.id ?? "");
  const target = options.some((x) => x.id === sel) ? sel : options[0]?.id ?? "";
  return (
    <>
      <label>{c.onOption}
        <select value={target} onChange={(e) => setSel(e.target.value)} style={{ width: "100%", minHeight: 44 }}>
          {options.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
        </select>
      </label>
      <NoteForm onSave={(b) => onSave(target, b)} />
    </>
  );
}

/** An adviser named on an open decision who has added no note and no option yet. */
function owesView(r: Intent, myName: string): boolean {
  const opts = r.outcome?.options ?? [];
  return Boolean(myName) && (r.people.advisers ?? []).some((a) => nameOf(a) === myName)
    && !opts.some((x) => x.by === myName || x.notes.some((n) => n.by === myName));
}

export default function DecisionView({ intentId }: { intentId?: string }) {
  const params = useParams<{ intentId: string }>();
  const id = intentId ?? params.intentId ?? "";
  const [search] = useSearchParams();
  const view = search.get("view");
  const wide = useWide();
  const [rec, setRec] = useState<Intent | null>(null);
  const [state, setState] = useState<"loading" | "error" | "refused" | "ready">("loading");
  const [loadMsg, setLoadMsg] = useState<string | undefined>();
  const [myName, setMyName] = useState("");
  const [nodes, setNodes] = useState<Node[] | null>(null);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [form, setForm] = useState<"" | "add" | "later" | "none" | "cancel" | "decider" | "affects" | `edit:${string}`>("");
  const [sources, setSources] = useState<Option | null>(null);
  const [signing, setSigning] = useState<Option | null>(null);
  const [why, setWhy] = useState("");
  const [whyDrafted, setWhyDrafted] = useState(false);
  const [reason, setReason] = useState("");
  const [laterTo, setLaterTo] = useState("");
  const [filter, setFilter] = useState<string | null>(null);
  const [newDecider, setNewDecider] = useState("");
  const [people, setPeople] = useState<{ person_id: string; name: string }[]>([]);
  const [attempt, setAttempt] = useState(0);
  const busy = useRef(false);

  useEffect(() => {
    let live = true;
    setState("loading");
    Promise.all([apiGet<Intent>(`/api/intents/${id}`), me().catch(() => null)]).then(([r, m]) => {
      if (!live) return;
      setRec(withDefaults(r)); setMyName(m?.display_name ?? ""); setState("ready");
    }, (e: unknown) => {
      if (!live) return;
      setLoadMsg(e instanceof ApiError && e.status < 500 ? e.message : undefined);
      setState(e instanceof ApiError && (e.status === 403 || e.status === 404) ? "refused" : "error");
    });
    return () => { live = false; };
  }, [id, attempt]);

  const affects = rec?.outcome?.affects ?? [];
  const wrote = rec?.outcome?.writes ?? [];
  useEffect(() => {
    if (nodes === null && (affects.length > 0 || wrote.some((w) => w.node_id) || form === "affects")) {
      apiGet<{ nodes: Node[] }>("/api/company/graph?view=map").then((g) => setNodes(g.nodes ?? []), () => setNodes([]));
    }
  }, [affects.length, wrote.length, form, nodes]);
  useEffect(() => {
    if (state !== "ready" || !rec) return;
    const target = view ?? (rec.state === "open" && owesView(rec, myName) ? "notes" : null);  // home's "Give your view" lands on the note box
    if (target) document.getElementById(`decision-${target}`)?.scrollIntoView?.({ block: "start" });
  }, [view, state]);  // eslint-disable-line react-hooks/exhaustive-deps

  if (state === "loading") return <ScreenState state="loading" />;
  if (state === "refused") return <ScreenState state="refused" message={loadMsg} />;
  if (state === "error" || !rec) return <ScreenState state="error" message={c.loadFailed} onRetry={() => setAttempt((a) => a + 1)} />;

  const o = rec.outcome;
  const p = rec.people;
  const organiser = nameOf(p.organiser), deciderName = nameOf(p.decider);
  const isOrg = Boolean(myName) && organiser === myName, isDecider = Boolean(myName) && deciderName === myName;
  const isAdviser = (p.advisers ?? []).some((a) => nameOf(a) === myName);
  const writer = rec.state === "open" && (isOrg || isDecider || isAdviser);
  const live = rec.state === "open";
  const left = workingDaysBetween(new Date(), new Date(rec.time_box.ends));
  const late = live && new Date(rec.time_box.ends).getTime() < Date.now();
  const nodeLabel = (nid: string) => nodes?.find((n) => n.id === nid && !n.restricted)?.label ?? (nodes === null ? c.notAvailable : c.hiddenNode);

  const act = async (path: string, body: Record<string, unknown>): Promise<boolean> => {
    if (busy.current) return false;  // a second press while North redrafts would post the same option or note twice
    busy.current = true;
    setError(""); setInfo("");
    try {
      const r = await apiSend<Intent>("POST", `/api/intents/${id}/${path}`, body);
      setRec(withDefaults(r));
      return true;
    } catch (e) {
      setError(e instanceof ApiError && e.message ? e.message : c.failed);
      return false;
    } finally {
      busy.current = false;
    }
  };
  const decide = async (body: Record<string, unknown>) => { if (await act("decide", body)) { setForm(""); setReason(""); setSigning(null); } };

  const header = (
    <span style={{ display: "inline-flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
      <Chip>{c.type}</Chip>
      <Pill tone={live ? "open" : rec.state === "cancelled" ? "late" : "signed"}>{c.states[rec.state] ?? rec.state}</Pill>
      {live && <Chip>{late ? c.over(day(rec.time_box.ends)) : c.decideBy(day(rec.time_box.ends), left)}</Chip>}
      {deciderName && <span>{c.decider}: {deciderName}</span>}
    </span>
  );

  if (rec.tier && rec.tier !== "content") {
    return (
      <PageFrame title={rec.title} subline={header}>
        {o && rec.state === "closed" && <p className="ds-card" style={{ padding: 16 }}>{strip(rec)}</p>}
        <p className="n-muted">{c.existsOnly}</p>
      </PageFrame>
    );
  }
  if (!o) return <ScreenState state="error" message={c.loadFailed} />;

  const notes = o.options.flatMap((x) => x.notes);
  const advisers = (p.advisers ?? []).map((a) => {
    const n = nameOf(a);
    return { n, aid: typeof a === "string" ? null : a.account_id, count: notes.filter((x) => x.by === n).length, opts: o.options.filter((x) => x.by === n).length };
  });
  const anonCount = notes.filter((x) => x.by === "Anonymous").length + o.options.filter((x) => x.origin === "anonymous").length;
  const silent = advisers.filter((a) => a.count === 0 && !o.options.some((x) => x.by === a.n)).length;
  const panels = live ? ["options", "notes", "decide"] : ["record", "notes"];

  const more = live && (isOrg || isDecider) && (
    <details style={{ position: "relative" }}>
      <summary className="ds-btn">{c.more}</summary>
      <div className="ds-card" style={{ position: "absolute", right: 0, zIndex: 5, padding: 8, display: "grid", gap: 6, minWidth: 220 }}>
        {isOrg && <Link className="ds-btn" to={`/centre/intent/${id}/share`}>{c.share}</Link>}
        {isOrg && !o.chosen && <Button onClick={() => { setForm("decider"); apiGet<{ people: { person_id: string; name: string }[] }>("/api/intents/people").then((r) => setPeople(r.people), () => setPeople([])); }}>{c.changeDecider}</Button>}
        <Button onClick={() => setForm("cancel")}>{c.cancel}</Button>
      </div>
    </details>
  );
  const actions = (
    <>
      {writer && <Button variant="primary" onClick={() => setForm("add")}>{c.addOption}</Button>}
      {more}
      {!live && isOrg && <Link className="ds-btn" to={`/centre/intent/${id}/share`}>{c.share}</Link>}
    </>
  );

  const card = (x: Option, snapshot = false) => {
    const expanded = open[x.id] ?? (wide || snapshot);
    const mine = Boolean(x.by_account) ? x.by === myName : isOrg;
    const canDecideNote = live && (mine || isDecider);
    const shown = filter ? x.notes.filter((n) => n.by === filter) : x.notes;
    return (
      <div key={x.id} className="ds-card" style={{ padding: 16, outline: snapshot && x.id === o.chosen ? "2px solid currentColor" : undefined }}>
        <button type="button" className="dv-hit dv-hit--block" aria-expanded={expanded} onClick={() => setOpen({ ...open, [x.id]: !expanded })}>
          <strong>{x.name}</strong>{snapshot && x.id === o.chosen && <> <Pill tone="signed">{c.chosen}</Pill></>}
          {!expanded && <span className="n-muted" style={{ display: "block" }}>{c.counts(x.for.length, x.against.length)} · {c.notesCount(x.notes.length)}</span>}
        </button>
        <p style={{ margin: "6px 0" }}>
          {x.origin === "north" ? <Chip onClick={() => setSources(x)}>{markOf(x)}</Chip> : <Chip>{markOf(x)}</Chip>}
        </p>
        {expanded && (
          <>
            <p><span className="n-muted">{c.means}:</span> {x.means || c.notAvailable}</p>
            <p className="n-muted" style={{ marginBottom: 2 }}>{c.for}</p>
            <ul style={{ marginTop: 0 }}>{x.for.length ? x.for.map((l) => <li key={l}>{l}</li>) : <li>{c.notAvailable}</li>}</ul>
            <p className="n-muted" style={{ marginBottom: 2 }}>{c.against}</p>
            <ul style={{ marginTop: 0 }}>{x.against.length ? x.against.map((l) => <li key={l}>{l}</li>) : <li>{c.notAvailable}</li>}</ul>
            <p><span className="n-muted">{c.needs}:</span> {x.needs || c.notAvailable}</p>
            {(x.accepted ?? []).map((a) => <p key={a.text} className="n-muted">{c.accepted(a.text)}</p>)}
            <p className="n-muted">{c.notesCount(x.notes.length)}</p>
            {shown.length === 0 ? <p className="n-muted">{c.noNotes}</p> : (
              <CommentThread comments={shown.map((n): Comment => ({ ...n, at: `${day(n.at)} ${time(n.at)}`, line: live && n.state === "open" ? `Open · ${first(x.by_account ? x.by : organiser)} or ${first(deciderName)} to decide` : null }))}
                canDecide={canDecideNote}
                onDecide={(nid, st, answer) => void act(`notes/${nid}/decide`, { state: st, answer })} />
            )}
            {writer && !snapshot && <NoteForm onSave={(b) => act(`options/${x.id}/notes`, b)} />}
            {!snapshot && live && (
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
                {writer && (mine || isOrg) && <Button onClick={() => setForm(`edit:${x.id}`)}>{c.edit}</Button>}
                {x.origin === "north" && !x.confirmed_by && (isOrg || isAdviser) && <Button onClick={() => void act("options", { action: "confirm", option_id: x.id })}>{c.confirm}</Button>}
                {isDecider && <Button variant="primary" onClick={() => { setSigning(x); setWhy(""); setWhyDrafted(false); }}>{c.choose(x.name)}</Button>}
              </div>
            )}
          </>
        )}
      </div>
    );
  };

  const recLine = (r: Rec | null, empty: string, was = false) => (
    r ? (
      <>
        <p>
          <Chip>{c.recLabel}</Chip>{" "}
          {was ? c.recWas(o.options.concat(o.considered_snapshot).find((x) => x.id === r.option_id)?.name ?? c.notAvailable) : r.line}
        </p>
        <p className="n-muted">{c.restsOn} {r.sources.map((s) => <Chip key={s.ref} href={s.kind === "intent" || s.kind === "decision" ? `/centre/intent/${s.ref}` : undefined}>{s.label}{s.at ? `, ${day(s.at)}` : ""}</Chip>)}</p>
        {!was && r.fallback && <p className="n-muted">{c.fallback}</p>}
        {!was && (r.missing ?? []).map((m) => <p key={m} className="n-muted">{m}</p>)}
      </>
    ) : <p className="n-muted">{empty}</p>
  );

  const linked = (
    <SideCard title={c.linked}>
      {!rec.links?.from && !(rec.links?.to ?? []).length ? <p className="n-muted">{c.noLinked}</p> : (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {rec.links?.from && <Chip href={`/centre/intent/${rec.links.from}`}>{c.sourceChip}</Chip>}
          {(rec.links?.to ?? []).map((t) => <Chip key={t} href={`/centre/intent/${t}`}>{c.linked}</Chip>)}
        </div>
      )}
    </SideCard>
  );

  const adviserPanel = (
    <div id="decision-notes">{writer && (
      <SideCard title={c.noteTitle}>
        {ordered(o.options).length === 0
          ? <><p className="n-muted">{c.noteNoOptions}</p><Button onClick={() => setForm("add")}>{c.addOption}</Button></>
          : <NoteBox options={ordered(o.options)} onSave={(oid, b) => act(`options/${oid}/notes`, b)} />}
      </SideCard>
    )}<SideCard title={c.advisers}>
      {advisers.length === 0 ? <p className="n-muted">{rec.state === "open" ? c.noAdvisers : "No advisers were named."}</p> : advisers.map((a) => (
        <div key={a.n} style={{ display: "flex", gap: 8, alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
          <button type="button" className="dv-hit" aria-pressed={filter === a.n} onClick={() => setFilter(filter === a.n ? null : a.n)}>
            <strong>{a.n}</strong> <span className="n-muted">{live ? (a.count ? c.added(a.count) : a.opts ? c.addedOptions(a.opts) : c.notRepliedYet) : a.count || a.opts ? c.gaveNote : c.noNote}</span>
          </button>
          {live && isOrg && a.count === 0 && a.opts === 0 && a.aid && (
            <Button onClick={() => void apiSend("POST", `/api/intents/${id}/nudge/${a.aid}`, {}).then(() => setInfo(c.nudged), () => setInfo(c.nudgeNa))}>{c.nudge}</Button>
          )}
        </div>
      ))}
      <p className="n-muted">{c.anonNotes(anonCount)}</p>
      {filter && <Button onClick={() => setFilter(null)}>{c.showAll}</Button>}
    </SideCard></div>
  );

  const affectsPanel = (
    <SideCard title={c.affects}>
      <p className="n-muted" style={{ marginBottom: 4 }}>{c.areas}</p>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>{rec.areas.map((a) => <Chip key={a}>{a}</Chip>)}</div>
      <p className="n-muted" style={{ marginBottom: 4 }}>{c.named}</p>
      {affects.length === 0 ? <p className="n-muted">{c.noNamed}</p> : (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {affects.map((a) => (
            <span key={a.node_id} className="ds-chip">{nodeLabel(a.node_id)}
              {live && (isOrg || isDecider) && <button type="button" aria-label={`Remove ${nodeLabel(a.node_id)}`} onClick={() => void act("decide", { kind: "affects", nodes: affects.filter((x) => x.node_id !== a.node_id).map((x) => x.node_id) })}>x</button>}
            </span>
          ))}
        </div>
      )}
      {live && (isOrg || isDecider) && (form === "affects" ? (
        nodes === null ? <ScreenState state="loading" /> : (
          <div style={{ maxHeight: 220, overflow: "auto" }}>
            {nodes.filter((n) => !n.restricted && (n.type === "Measure" || n.type === "Process") && !affects.some((a) => a.node_id === n.id)).map((n) => (
              <div key={n.id}><Button onClick={() => { void act("decide", { kind: "affects", nodes: [...affects.map((a) => a.node_id), n.id] }); setForm(""); }}>{n.label}</Button></div>
            ))}
            {nodes.filter((n) => !n.restricted && (n.type === "Measure" || n.type === "Process")).length === 0 && <p className="n-muted">{c.noNodes}</p>}
            <Button onClick={() => setForm("")}>{c.close}</Button>
          </div>
        )
      ) : <Button onClick={() => setForm("affects")}>{c.nameNode}</Button>)}
    </SideCard>
  );

  const aside = <>{adviserPanel}{affectsPanel}{linked}</>;
  const panelNav = (
    <div style={{ display: "flex", gap: 6, flexWrap: "wrap", margin: "0 0 12px" }}>
      {panels.map((k) => <Chip key={k} href={`/centre/intent/${id}?view=${k}`} tone={view === k ? "active" : "default"}>{c.panels[k]}</Chip>)}
    </div>
  );
  const messages = (
    <>
      {error && <p role="alert" className="state state-error">{error}</p>}
      {info && <p role="status" className="n-muted">{info}</p>}
    </>
  );
  const editing = form.startsWith("edit:") ? o.options.find((x) => x.id === form.slice(5)) : undefined;

  // ---- Screen D: the record (closing, closed, cancelled) --------------------------------------------------------------------
  if (!live) {
    const snap = o.considered_snapshot.length ? o.considered_snapshot : o.options;
    return (
      <PageFrame title={rec.title} subline={header} actions={actions} aside={wide ? aside : undefined}>
        {panelNav}
        <div id="decision-record" className="ds-card" style={{ padding: 16, marginBottom: 12 }}>
          <strong>{strip(rec)}</strong>
          {rec.state === "closing" && <p>{c.waitingClose(organiser)} {isOrg && <Link className="ds-btn ds-btn--primary" to={`/centre/intent/${id}/close`}>{c.closeIntent}</Link>}</p>}
          {o.deferral && <p className="n-muted">{c.deferral(day(o.deferral.from), day(o.deferral.to), o.deferral.reason)}</p>}
        </div>
        {o.chosen && <SideCard title={c.whyTitle}><p>{o.why} {o.why_drafted && <Chip>{c.northWhy}</Chip>}</p></SideCard>}
        <h2>{c.considered}</h2>
        {ordered(snap).length === 0 ? <p className="n-muted">{c.noConsidered}</p> : (
          <div style={{ display: "grid", gap: 12, gridTemplateColumns: wide ? "1fr 1fr" : "1fr" }}>{ordered(snap).map((x) => card(x, true))}</div>
        )}
        <SideCard title={c.recTitle}>{recLine(o.recommendation, c.noRecWas, true)}</SideCard>
        <SideCard title={c.wrote}>
          {wrote.length === 0 ? <p className="n-muted">{c.wroteNone}</p> : wrote.map((w, i) => (
            <p key={i}>{w.node_id ? (w.version ? c.version(nodeLabel(w.node_id), w.version) : `${w.skipped ?? ""}`) : w.intent_id && <Link to={`/centre/intent/${w.intent_id}`}>{c.linkOn}</Link>}</p>
          ))}
        </SideCard>
        {rec.state !== "cancelled" && <p><Link className="ds-btn" to={`/centre/intent/${id}/close`}>{c.rate}</Link></p>}
        {!wide && aside}
        {messages}
        <EventsLink intentId={id} />
      </PageFrame>
    );
  }

  // ---- Screen B: the decision screen (open) ---------------------------------------------------------------------------------
  const north = o.north;
  const redraftable = o.options.some((x) => x.origin === "north" && !x.edited_by && !x.confirmed_by);
  const choice = (
    <div id="decision-decide" className="ds-card" style={{ padding: 16, marginTop: 12 }}>
      <strong>{c.choiceTitle}</strong>
      <p className="n-muted">{deciderName} · {late ? c.over(day(rec.time_box.ends)) : c.decideBy(day(rec.time_box.ends), left)}</p>
      {!isDecider ? <p>{c.waitingFor(first(deciderName))}</p> : o.options.length === 0 ? <p className="n-muted">{c.needOption}</p> : (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <Button variant="primary" onClick={() => { setInfo(c.pickHelp); document.getElementById("decision-options")?.scrollIntoView?.(); }}>{c.pickOne}</Button>
          {o.deferral ? <span className="n-muted">{c.laterDone(day(o.deferral.at))}</span> : <Button onClick={() => setForm("later")}>{c.later}</Button>}
          <Button onClick={() => setForm("none")}>{c.none}</Button>
        </div>
      )}
    </div>
  );

  const writesNodes = affects.map((a) => nodeLabel(a.node_id));
  return (
    <PageFrame title={rec.title} subline={header} actions={actions} aside={wide ? aside : undefined}>
      {panelNav}
      {late && (isOrg || isDecider) && (
        <div className="ds-card" role="status" style={{ padding: 12, marginBottom: 12 }}>
          <p><strong>North:</strong> {c.banner} {c.bannerWho(first(deciderName))}</p>
          {isDecider && <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {!o.deferral && <Button onClick={() => setForm("later")}>{c.later}</Button>}
            <Button onClick={() => setForm("none")}>{c.none}</Button>
            <Button onClick={() => setForm("cancel")}>{c.cancel}</Button>
          </div>}
        </div>
      )}
      <div className="ds-card" style={{ padding: 16, marginBottom: 12 }}>
        {rec.purpose && <p>{rec.purpose}</p>}
        <p className="n-muted">{c.askedBy(organiser, day(rec.created_at))} {rec.links?.from && <Chip href={`/centre/intent/${rec.links.from}`}>{c.sourceChip}</Chip>}</p>
        {isOrg && o.options.length > 0 && <p className="n-muted">{c.questionLocked}</p>}
      </div>
      <p className="n-muted">
        <strong>North:</strong> {north ? c.northDrafted(north.drafted, north.records, north.notes, time(north.drafted_at)) + (silent ? c.notReplied(silent) : "") : c.northWaiting}
        {" "}{isOrg && redraftable && <Button onClick={() => void act("options", { action: "redraft" })}>{c.redraft}</Button>}
      </p>
      {messages}
      <h2 id="decision-options">{c.options}</h2>
      {ordered(o.options).length === 0 ? <p className="n-muted">{c.noOptions}</p> : (
        <div style={{ display: "grid", gap: 12, gridTemplateColumns: wide ? "1fr 1fr" : "1fr" }}>{ordered(o.options).map((x) => card(x))}</div>
      )}
      <div style={{ marginTop: 12 }}><SideCard title={c.recTitle}>{recLine(o.recommendation, c.noRec)}</SideCard></div>
      {!wide && aside}
      {choice}

      {sources && (
        <Dialog title={c.restsOnTitle}>
          {sources.sources.length === 0 ? <p>{c.guessedNone}</p> : <ul>{sources.sources.map((s) => <li key={s.ref}>{s.label}{s.at ? `, ${day(s.at)}` : ""}</li>)}</ul>}
          <Button onClick={() => setSources(null)}>{c.close}</Button>
        </Dialog>
      )}
      {(form === "add" || editing) && (
        <Dialog title={editing ? c.edit : c.addOption}>
          <OptionForm start={editing} anonOk={!editing} onCancel={() => setForm("")}
            onSave={(b) => void act("options", editing ? { action: "edit", option_id: editing.id, ...b } : { action: "add", ...b }).then((ok) => ok && setForm(""))} />
          {messages}
        </Dialog>
      )}
      {form === "later" && (
        <Dialog title={c.later}>
          <label>{c.laterDate}<input type="date" value={laterTo} onChange={(e) => setLaterTo(e.target.value)} style={{ width: "100%" }} /></label>
          <label>{c.laterReason}<input value={reason} maxLength={400} onChange={(e) => setReason(e.target.value)} style={{ width: "100%" }} /></label>
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <Button variant="primary" disabled={!laterTo || !reason.trim()} onClick={() => void decide({ kind: "later", to: laterTo, reason })}>{c.laterSave}</Button>
            <Button onClick={() => setForm("")}>{c.cancelBtn}</Button>
          </div>
          {messages}
        </Dialog>
      )}
      {(form === "none" || form === "cancel") && (
        <Dialog title={form === "none" ? c.none : c.cancel}>
          <label>{form === "none" ? c.noneReason : c.cancelReason}<input value={reason} maxLength={400} onChange={(e) => setReason(e.target.value)} style={{ width: "100%" }} /></label>
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <Button variant="primary" disabled={!reason.trim()} onClick={() => void decide({ kind: form, reason })}>{form === "none" ? c.noneSave : c.cancel}</Button>
            <Button onClick={() => setForm("")}>{form === "none" ? c.cancelBtn : c.keepOpen}</Button>
          </div>
          {messages}
        </Dialog>
      )}
      {form === "decider" && (
        <Dialog title={c.changeDecider}>
          <p>{c.decider}: {deciderName}</p>
          <select aria-label={c.changeDecider} value={newDecider} onChange={(e) => setNewDecider(e.target.value)} style={{ width: "100%", minHeight: 44 }}>
            <option value="" />
            {people.map((x) => <option key={x.person_id} value={x.person_id}>{x.name}</option>)}
          </select>
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <Button variant="primary" disabled={!newDecider} onClick={() => { const x = people.find((y) => y.person_id === newDecider); if (x) void decide({ kind: "decider", decider: { account_id: x.person_id, name: x.name } }); }}>{c.save}</Button>
            <Button onClick={() => setForm("")}>{c.cancelBtn}</Button>
          </div>
          {messages}
        </Dialog>
      )}
      {signing && (
        <Dialog title={c.signTitle}>
          <p>{c.summary(signing.name)}</p>
          <label>{c.why}<textarea placeholder={c.why} maxLength={400} rows={3} value={why} onChange={(e) => { setWhy(e.target.value); setWhyDrafted(false); }} style={{ width: "100%" }} /></label>
          <p className="n-muted"><Chip>{c.northWhy}</Chip> {draftWhy(signing)} <Button onClick={() => { setWhy(draftWhy(signing)); setWhyDrafted(true); }}>{c.useDraft}</Button></p>
          <p><strong>{c.writesTitle}</strong></p>
          {writesNodes.length === 0 && !rec.links?.from ? <p className="n-muted">{c.writesNone}</p> : (
            <ul>
              {writesNodes.length > 0 && <li>{c.writesNode(writesNodes.join(", "))}</li>}
              {rec.links?.from && <li>{c.writesLink}</li>}
            </ul>
          )}
          {!why.trim() && <p className="n-muted">{c.sayWhy}</p>}
          <div style={{ display: "flex", gap: 8 }}>
            <Button variant="primary" disabled={!why.trim()} onClick={() => void decide({ kind: "choose", option_id: signing.id, why, why_drafted: whyDrafted })}>{c.record}</Button>
            <Button onClick={() => setSigning(null)}>{c.notYet}</Button>
          </div>
          {messages}
        </Dialog>
      )}
      <EventsLink intentId={id} />
    </PageFrame>
  );
}

/** North's suggested Why, the same words the server checks for `why_drafted` (decision.why_draft). */
export const draftWhy = (x: Option) => `${x.name} weighed best against the other options and the advisers' notes.`;

/** The decision strip (screen D). */
export function strip(rec: Intent): string {
  const o = rec.outcome;
  if (rec.state === "cancelled") return c.cancelled(rec.closure?.cancel_reason ?? "");
  if (!o) return "";
  if (o.chosen) {
    const opt = (o.considered_snapshot.length ? o.considered_snapshot : o.options).find((x) => x.id === o.chosen);
    return c.decided(opt?.name ?? c.notAvailable, o.decided_by ?? "", day(o.decided_at));
  }
  return o.no_decision_reason ? c.noDecision(o.no_decision_reason) : "";
}
