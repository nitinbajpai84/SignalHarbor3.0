import { useEffect, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";

import { apiGet, apiSend, ApiError } from "../../api/client";
import ScreenState from "../../components/ScreenState";
import { Button, Chip, SideCard } from "../../design";
import type { StartProps } from "../IntentNew";

// Spec 43 screen A: the Decision's five start questions. The draft exists already (the chooser made it); this screen fills and opens it.

export interface Person { account_id: string; name: string }
interface PickPerson { person_id: string; name: string; role: string | null; area: string | null }
interface Draft { id: string; title?: string; links?: { from: string | null }; north_proposal?: { text?: string } | null }
type Slot = Person | string | null | undefined;
interface Source { type?: string; title?: string; outcome?: { chosen?: string | { text?: string } | null } | null;
  people?: { sponsor?: Slot; decider?: Slot; participants?: Slot[]; advisers?: Slot[] } }

export const startCopy = {
  q1: "What must be decided?",
  q1Placeholder: "For example: which valuation date do we use for the fund report?",
  q1Help: "One line. End it as a question, or start it with \"whether\".",
  q1One: "One decision only. If there are two, open two.",
  q1Rewrite: (s: string) => `North suggests: "${s}"`,
  useRewrite: "Use this",
  q2: "By when?",
  q2Help: "Working days only, Monday to Friday.",
  q2Weekend: "Pick a working day.",
  q2Long: "That is longer than a decision should take. Consider an Initiative.",
  q3: "Who decides?",
  q3Help: "One named person. The default is the sponsor.",
  q3Pick: "Pick who decides",
  q3Self: "You chose yourself. That is allowed. Advisers will still be asked.",
  q4: "Whose advice do you want?",
  q4Help: "Up to five people. They can add options and notes, anonymously if they want.",
  q4None: "No advisers. North will draft the options from the records alone.",
  q4Cap: "That is more advisers than this decision allows.",
  addAdviser: "Add adviser",
  search: "Search people",
  nobody: "Nobody found",
  q5: "Which areas does it affect?",
  q5Help: "Everyone in these areas sees that this decision exists.",
  addArea: "Add area",
  noAreas: "No areas are set up for this company yet",
  affected: "Affected people may read the options and notes.",
  northTitle: "What North will do",
  north: (d: string) => [
    "North drafts the options from the records and the advisers' notes.",
    "North drafts a recommendation and shows what it rests on.",
    `${d} decides.`],
  someone: "The decider",
  preview: "Preview",
  decideBy: "Decide by",
  decider: "Decider",
  notYet: "Not named yet",
  back: "Back",
  open: "Open this decision",
  opening: "Opening",
  needQ1: "Say what must be decided",
  needQ3: "Name who decides",
  needQ5: "Choose at least one area",
  remove: (n: string) => `Remove ${n}`,
  from: "Follows on from",
  prefilled: (t: string) => `Pre-filled from the ${t}. Change anything.`,
  failed: "That did not open. Try again.",
  loadFailed: "We could not load the start questions. Try again.",
  sponsorMark: "sponsor",
  adminMark: "company admin",
};
const c = startCopy;
const MAX_Q = 140, MAX_ADVISERS = 5, LONG_DAYS = 10;

export function addWorkingDays(from: Date, n: number): Date {
  const d = new Date(from);
  let left = n;
  while (left > 0) {
    d.setDate(d.getDate() + 1);
    if (d.getDay() !== 0 && d.getDay() !== 6) left -= 1;
  }
  return d;
}
export function workingDaysBetween(from: Date, to: Date): number {
  const d = new Date(from.getFullYear(), from.getMonth(), from.getDate());
  const end = new Date(to.getFullYear(), to.getMonth(), to.getDate());
  let n = 0;
  while (d < end) {
    d.setDate(d.getDate() + 1);
    if (d.getDay() !== 0 && d.getDay() !== 6) n += 1;
  }
  return n;
}
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const parse = (s: string) => new Date(`${s}T12:00:00`);
export const dayLabel = (d: Date) => d.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "short" });

/** North's question check: offer a rewrite ending with a question mark, never forced. */
export function rewriteOf(q: string): string | null {
  const s = q.trim();
  if (!s || s.endsWith("?") || /^whether\b/i.test(s)) return null;
  return `${s.replace(/[.!]+$/, "")}?`;
}

export function useWide(): boolean {
  const q = typeof window !== "undefined" && window.matchMedia ? window.matchMedia("(min-width: 900px)") : null;
  const [wide, setWide] = useState(q ? q.matches : true);
  useEffect(() => {
    if (!q) return;
    const on = () => setWide(q.matches);
    q.addEventListener?.("change", on);
    return () => q.removeEventListener?.("change", on);
  }, [q]);
  return wide;
}

function Question({ label, help, children }: { label: string; help?: string; children: ReactNode }) {
  return (
    <div className="ds-card" style={{ padding: 16, marginBottom: 12 }}>
      <label style={{ display: "block" }}><strong>{label}</strong></label>
      {help && <p className="n-muted" style={{ margin: "4px 0 8px" }}>{help}</p>}
      {children}
    </div>
  );
}

export default function DecisionStart({ draftId }: StartProps) {
  const nav = useNavigate();
  const wide = useWide();
  const [state, setState] = useState<"loading" | "error" | "ready">("loading");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [people, setPeople] = useState<PickPerson[]>([]);
  const [areaList, setAreaList] = useState<string[]>([]);
  const [marks, setMarks] = useState<Record<string, string[]>>({});
  const [meName, setMeName] = useState("");
  const [question, setQuestion] = useState("");
  const [ends, setEnds] = useState(iso(addWorkingDays(new Date(), 2)));
  const [decider, setDecider] = useState<Person | null>(null);
  const [advisers, setAdvisers] = useState<Person[]>([]);
  const [areas, setAreas] = useState<string[]>([]);
  const [mayRead, setMayRead] = useState(false);
  const [picking, setPicking] = useState<"" | "adviser" | "area">("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [prefilled, setPrefilled] = useState("");

  useEffect(() => {
    let live = true;
    setState("loading");
    Promise.all([
      apiGet<Draft & { people?: { organiser?: Person } }>(`/api/intents/${draftId}`),
      apiSend<{ marks: Record<string, string[]>; sponsor: Person | null }>("POST", `/api/intents/${draftId}/decide`, { kind: "start" }),
      apiGet<{ people: PickPerson[]; areas: { name: string }[] }>("/api/intents/people").catch(() => ({ people: [], areas: [] })),
      apiGet<{ areas: { name: string }[] }>("/api/intents/areas").catch(() => ({ areas: [] })),
    ]).then(async ([d, m, ppl, ar]) => {
      // Journey 54 step 1: a follow-on is pre-filled from the source intent (its chosen idea, sponsor and participants); a draft to change.
      const src = d.links?.from ? await apiGet<Source>(`/api/intents/${d.links.from}`).catch(() => null) : null;
      if (!live) return;
      const asPerson = (x: Slot): Person | null => (x && typeof x === "object" && x.account_id ? { account_id: x.account_id, name: x.name } : null);
      const chosen = src?.outcome?.chosen;
      const fromSrc = (typeof chosen === "string" ? chosen : chosen?.text) || src?.title || "";
      const lead = asPerson(src?.people?.decider) ?? asPerson(src?.people?.sponsor);
      setDraft(d);
      setMeName(d.people?.organiser?.name ?? "");
      setQuestion((d.title || fromSrc || d.north_proposal?.text || "").slice(0, MAX_Q));
      setMarks(m.marks);
      setDecider((cur) => cur ?? lead ?? m.sponsor);
      if (src) {
        const dec = lead ?? m.sponsor;
        const seen = new Set<string>();
        setAdvisers([...(src.people?.participants ?? []), ...(src.people?.advisers ?? [])].map(asPerson)
          .filter((x): x is Person => !!x && x.account_id !== dec?.account_id && !seen.has(x.account_id) && !!seen.add(x.account_id)).slice(0, MAX_ADVISERS));
        setPrefilled(c.prefilled(src.type ?? "earlier intent"));
      }
      setPeople(ppl.people);
      const names = ar.areas.map((a) => a.name);
      setAreaList(names.length ? names : ppl.areas.map((a) => a.name));
      setState("ready");
    }, () => live && setState("error"));
    return () => { live = false; };
  }, [draftId, attempt]);

  if (state === "loading") return <ScreenState state="loading" />;
  if (state === "error") return <ScreenState state="error" message={c.loadFailed} onRetry={() => setAttempt((a) => a + 1)} />;

  const end = parse(ends);
  const days = workingDaysBetween(new Date(), end);
  const weekend = end.getDay() === 0 || end.getDay() === 6;
  const long = days > LONG_DAYS;
  const rewrite = rewriteOf(question);
  const missing = !question.trim() ? c.needQ1 : !decider ? c.needQ3 : areas.length === 0 ? c.needQ5 : "";
  const mark = (pid: string) => (marks[pid] ?? []).map((r) => (r === "sponsor" ? c.sponsorMark : c.adminMark)).join(", ");
  const label = (p: Person) => (mark(p.account_id) ? `${p.name} (${mark(p.account_id)})` : p.name);
  const deciderFirst = decider?.name.split(" ")[0] ?? c.someone;
  const found = people.filter((p) => p.name.toLowerCase().includes(search.toLowerCase()) && !advisers.some((a) => a.account_id === p.person_id));

  const addAdviser = (p: PickPerson) => {
    if (advisers.length >= MAX_ADVISERS) { setError(c.q4Cap); return; }
    setAdvisers([...advisers, { account_id: p.person_id, name: p.name }]);
    setPicking(""); setSearch(""); setError("");
  };

  const open = async () => {
    if (missing || busy) return;
    setBusy(true); setError("");
    try {
      await apiSend("POST", `/api/intents/${draftId}/decide`, {
        kind: "open", answers: { question: question.trim(), ends, decider, advisers, areas, affected_may_read: mayRead },
      });
      nav(`/centre/intent/${draftId}`);
    } catch (e) {
      setError(e instanceof ApiError && e.message ? e.message : c.failed);
      setBusy(false);
    }
  };

  const preview = (
    <>
      <p><strong>{question.trim() || c.q1}</strong></p>
      <p>{c.decideBy} {dayLabel(end)}</p>
      <p>{c.decider}: {decider ? label(decider) : c.notYet}</p>
    </>
  );

  return (
    <div>
      {draft?.links?.from && <p><Chip href={`/centre/intent/${draft.links.from}`}>{c.from}</Chip> {prefilled && <span className="n-muted">{prefilled}</span>}</p>}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 16, alignItems: "flex-start" }}>
        <div style={{ flex: "7 1 360px", minWidth: 0 }}>
          <Question label={c.q1} help={c.q1Help}>
            <input aria-label={c.q1} placeholder={c.q1Placeholder} maxLength={MAX_Q} value={question} style={{ width: "100%" }}
              onChange={(e) => setQuestion(e.target.value)} />
            <p className="n-muted" style={{ textAlign: "right", margin: "4px 0 0" }}>{question.length} / {MAX_Q}</p>
            {/\sand\s/i.test(question) && <p className="n-muted"><strong>North:</strong> {c.q1One}</p>}
            {rewrite && (
              <p className="n-muted"><strong>North:</strong> {c.q1Rewrite(rewrite)}{" "}
                <Button onClick={() => setQuestion(rewrite.slice(0, MAX_Q))}>{c.useRewrite}</Button></p>
            )}
          </Question>
          <Question label={c.q2} help={c.q2Help}>
            <input type="date" aria-label={c.q2} value={ends} min={iso(addWorkingDays(new Date(), 1))} onChange={(e) => e.target.value && setEnds(e.target.value)} />
            <p>{dayLabel(end)} ({days} working {days === 1 ? "day" : "days"})</p>
            {weekend && <p role="alert" className="state state-error">{c.q2Weekend}</p>}
            {long && <p className="n-muted">{c.q2Long}</p>}
          </Question>
          <Question label={c.q3} help={c.q3Help}>
            <select aria-label={c.q3} value={decider?.account_id ?? ""} style={{ width: "100%", minHeight: 44 }}
              onChange={(e) => { const p = people.find((x) => x.person_id === e.target.value); setDecider(p ? { account_id: p.person_id, name: p.name } : null); }}>
              <option value="">{c.q3Pick}</option>
              {people.map((p) => <option key={p.person_id} value={p.person_id}>{label({ account_id: p.person_id, name: p.name })}</option>)}
            </select>
            {decider && meName && decider.name === meName && <p className="n-muted"><strong>North:</strong> {c.q3Self}</p>}
          </Question>
          <Question label={c.q4} help={c.q4Help}>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {advisers.map((a) => {
                const p = people.find((x) => x.person_id === a.account_id);
                return (
                  <span key={a.account_id} className="ds-chip">{a.name}{p?.role ? `, ${p.role}` : ""}{" "}
                    <button type="button" aria-label={c.remove(a.name)} onClick={() => setAdvisers(advisers.filter((x) => x.account_id !== a.account_id))}>x</button>
                  </span>
                );
              })}
            </div>
            {advisers.length === 0 && <p className="n-muted">{c.q4None}</p>}
            {picking === "adviser" ? (
              <div style={{ marginTop: 8 }}>
                <input aria-label={c.search} placeholder={c.search} value={search} autoFocus onChange={(e) => setSearch(e.target.value)} style={{ width: "100%" }} />
                {found.length === 0 ? <p className="n-muted">{c.nobody}</p> : (
                  <ul style={{ listStyle: "none", padding: 0, maxHeight: 220, overflow: "auto" }}>
                    {found.map((p) => (
                      <li key={p.person_id}><Button onClick={() => addAdviser(p)}>{p.name}{p.role ? `, ${p.role}` : ""}</Button></li>
                    ))}
                  </ul>
                )}
              </div>
            ) : <Button onClick={() => (advisers.length >= MAX_ADVISERS ? setError(c.q4Cap) : setPicking("adviser"))}>{c.addAdviser}</Button>}
          </Question>
          <Question label={c.q5} help={c.q5Help}>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {areas.map((a) => (
                <span key={a} className="ds-chip">{a}{" "}
                  <button type="button" aria-label={c.remove(a)} onClick={() => setAreas(areas.filter((x) => x !== a))}>x</button>
                </span>
              ))}
            </div>
            {picking === "area" ? (
              areaList.length === 0 ? <p className="n-muted">{c.noAreas}</p> : (
                <ul style={{ listStyle: "none", padding: 0 }}>
                  {areaList.filter((a) => !areas.includes(a)).map((a) => (
                    <li key={a}><Button onClick={() => { setAreas([...areas, a]); setPicking(""); }}>{a}</Button></li>
                  ))}
                </ul>
              )
            ) : <Button onClick={() => setPicking("area")}>{c.addArea}</Button>}
            <label style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 12 }}>
              <input type="checkbox" role="switch" checked={mayRead} onChange={(e) => setMayRead(e.target.checked)} />
              {c.affected}
            </label>
          </Question>
        </div>
        <div style={{ flex: "5 1 280px", minWidth: 0 }}>
          <SideCard title={c.northTitle}>{c.north(deciderFirst).map((l) => <p key={l}>{l}</p>)}</SideCard>
          {wide ? <SideCard title={c.preview}>{preview}</SideCard>
            : <details className="ds-card" style={{ padding: 12, marginTop: 12 }}><summary>{c.preview}</summary>{preview}</details>}
        </div>
      </div>
      {error && <p role="alert" className="state state-error">{error}</p>}
      <div className="ds-card" style={{ position: "sticky", bottom: 0, display: "flex", gap: 12, alignItems: "center", justifyContent: "space-between", padding: 12, marginTop: 12, flexWrap: "wrap" }}>
        <Link to="/centre/intent/new" className="ds-btn">{c.back}</Link>
        {missing && <span className="n-muted">{missing}</span>}
        <Button variant="primary" disabled={Boolean(missing) || busy || weekend} onClick={() => void open()}>{busy ? c.opening : c.open}</Button>
      </div>
    </div>
  );
}
