import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { apiGet, apiSend } from "../../api/client";
import AgentChip from "../../components/AgentChip";
import MessageBubble from "../../components/MessageBubble";
import Panel from "../../components/Panel";
import ScreenState from "../../components/ScreenState";
import { Button, Chip } from "../../design";
import AreaPicker from "../AreaPicker";
import type { StartProps } from "../IntentNew";

// The Initiative's six start questions, "Here is what I understood" and the open with the wall hand-over (spec 22).
// Answers save through PUT /api/intents/{id}/start; the open is POST /api/intents/{id}/start/open, which prepares the wall
// draft through the existing m1 Prepare and writes the record open with the flat outcome and stages[0].ref.

export const QUESTIONS = [
  { key: "goal", label: "Goal", lead: "What are you trying to achieve?", why: "The goal and the reason are what everyone you invite reads first.", required: true },
  { key: "people", label: "People", lead: "Whom do you need to involve, and who is affected?", why: "I will draft an invitation for each person you name, and nobody else.", required: true },
  { key: "build", label: "Build", lead: "Do you think this needs a build (new data, pipelines, reports)?", why: "It tells Define whether to plan for Build or stop at a decision.", required: true },
  { key: "definitions", label: "Definitions", lead: "Do we already have a business glossary and technical definitions for this, or will we discover them along the way?", why: "Define starts from what exists and only fills the gaps.", required: true },
  { key: "areas", label: "Areas", lead: "Which areas does this touch?", why: "People in these areas will see that this intent exists.", required: true },
  { key: "deadline", label: "Deadline", lead: "When must this be decided by?", why: "The date sets the time box and the clock I keep for everyone.", required: true },
] as const;
export type Key = (typeof QUESTIONS)[number]["key"];

const c = {
  type: "Initiative", changeType: "Change type", review: "Review", soFar: "So far", nothingYet: "Nothing answered yet.", change: "Change",
  questionOf: (n: number) => `Question ${n} of 6`, whyAsk: "Why I ask:", draftTitle: "North's draft", useDraft: "Use this draft", skipDraft: "Skip draft",
  noDraft: "North has nothing to draft from yet. Answer in your own words.", right: "That is right", correct: "Let me correct it",
  back: "Back", next: "Next", saveLeave: "Save and leave", toast: "Draft kept in Your drafts", saveFailed: "Could not save this answer. Try again.",
  stated: "Stated by you", guessed: "Guessed by North", suggestion: "Suggestion",
  goalLine: "In one line", goalPlaceholder: "For example: cut the days it takes to produce the quarterly client report",
  goalWhy: "Why does it matter? Say it in as many lines as you need", goalMissing: "Say the goal in one line.", whyMissing: "A few words on why will help the people you invite.",
  of: (n: number, max: number) => `${n} of ${max}`,
  sponsor: "Sponsor", takePart: "Take part", affected: "Affected", nobody: "Nobody", searchPeople: "Search people",
  noPeople: "No people in the company profile yet. Add them in the company profile.", profileLink: "Company profile",
  justMe: "Just me for now", affectedEmpty: "Nobody named yet. Areas in question 5 also make people aware.",
  mayRead: "Affected people may read this intent", mayReadLine: "Off: affected people see that it exists, its title, purpose, stage, clock, people and the outcome once closed. On: they may also read the content.",
  notListed: "Someone is not listed", notListedLabel: "Who is missing? Your company admin gets this note.", add: "Add",
  peopleMissing: "Name the people to involve, or choose Just me for now.", seats: "The wall has ten seats. Pick at most nine people to take part and name the others as affected.",
  movedNote: (n: string, g: string) => `${n} moved to ${g}. A person sits in one group only.`,
  yes: "Yes", no: "No", notSure: "Not sure", buildLine: "New data, a pipeline, a report or a dashboard that does not exist today", whyNotSure: "Why not sure?",
  buildMissing: "Choose yes, no or not sure.", cannotSay: "North cannot say yet.",
  terms: "Terms", noTerms: "North found no terms in your goal. Add the words you use.", addTerm: "Add a term", remove: "remove",
  exists: "What already exists", business: "Business glossary", technical: "Technical definitions", catalogue: "Catalogue",
  noBaseline: "Nothing in the company glossary matches these terms yet.", lookupNa: "Not available yet. The glossary look-up could not run.",
  baseNa: "Not available yet. The technical definitions and the catalogue could not be read for you.", baseNone: "Not available yet. No baseline exists yet, so there are no technical definitions or catalogue to look in.",
  nothingMatches: "Nothing matches these terms yet.", techCount: (n: number) => `${n} ${n === 1 ? "has" : "have"} a technical definition.`,
  catCount: (n: number) => `${n} ${n === 1 ? "is" : "are"} in the catalogue.`, notIt: "That is not it", signed: "Signed", draft: "Draft",
  defYes: "Yes, we have them", defSome: "Some of them", defNo: "No, we will discover them along the way", defsMissing: "Choose yes, some or no.",
  notChecked: "Not checked", ownerIs: (o: string) => `Owner: ${o}`,
  means: { yes: "Define will start from what exists and only fill gaps.", some: "Define will keep the existing entries and draft the rest.", no: "Lens will draft definitions from the wall, the interviews and the documents." } as Record<string, string>,
  areasHelp: "Everyone tagged to these areas will see that this intent exists, its title, purpose and stage. They open the content only if they take part.",
  areasMissing: "Pick at least one area.",
  decideBy: "Decide by", thatIs: (n: number) => `That is ${n} working days.`, defaultNote: "10 working days is the default for an Initiative.",
  dateMissing: "Pick a date.", dateLate: (d: string) => `Pick a date no later than ${d}. You can ask for more time later.`,
  dateEarly: "Pick a date after today.", usual: (n: number) => `A usual Initiative takes 10 working days. Your date leaves ${n}.`,
  tight: "This leaves 1 working day for Define. Pick a later date or accept less time.",
  split: (t: number, d: number, b: number) => `Think unfiltered ${t}, Define strategically ${d}, Build-ready check ${b} working days`,
  lead: "Here is what I understood. Check it, change anything that is wrong, then open it.", editSummary: "Edit the summary", saveSummary: "Save the summary",
  summaryLabel: "Summary", summaryMissing: "Write the summary.", titleLabel: "Title", titleMissing: "Give the intent a title.",
  handover: (n: number, m: number, line: string) => `When you open this intent: the wall opens for ${n} working days, ${m ? `to ${m} ${m === 1 ? "person" : "people"}` : "for you alone"}. Purpose line: ${line}`,
  lanes: "Lanes: Tracking today, Missing, Watch, Levers.", open: "That is right, open this intent", opening: "Opening", changeSomething: "Change something",
  saveDraftLeave: "Save as draft and leave", openFailed: "Could not open this intent. Your draft is safe. Try again.", tryAgain: "Try again",
  loadFailed: "This draft could not be loaded. Try again.", answersMissing: (q: string) => `Answer this first: ${q}`,
  fromTyped: "From what you typed on the start page", fromIntent: (t: string) => `From the intent ${t}`, fromProfile: "From the profile",
  fromLookup: "From the look-up of the company glossary",
  carried: (src: string) => `${src}. North filled the answers it could from its hypothesis; each stays Guessed by North until you change it.`, fromTeams: "From the teams of the people you named",
};

const STOP = new Set("that this with from into they them their there what when which while about would could should have has been were will your ours our the and for are but not you all can its days weeks takes take make makes made need needs want wants produce after before each every three people hand time wait waits waiting show shows showing give gives giving get gets keep keeps help helps use uses used run runs send sends look looks know knows tell tells find finds work works within without between over under again also just more most much many some any only very than then once twice across during since until upon whether today still done being doing going come comes goes".split(" "));
const DEFAULT_DAYS = 10;
const LINK = { background: "none", border: "none", padding: "10px 4px", minHeight: 44, cursor: "pointer", font: "inherit" } as const;
const GOAL_MAX = 140, WHY_MIN = 20, WHY_MAX = 600, TITLE_MAX = 120, TERMS_MAX = 8, SEATS = 9;

interface Person { account_id: string; name: string }
interface Pick { person_id: string; name: string; role: string | null; area: string | null; is_sponsor?: boolean }
interface Found { term: string; kind: "glossary" | "technical" | "catalogue"; entry_ref: string; name: string; status: "signed" | "draft"; owner: string | null }
interface Counts { terms: number; business: number; technical: number | null; catalogue: number | null }
type CatRow = Record<string, { value?: unknown } | undefined>;
/** What the latest signed baseline (else the latest with measures) holds: the catalogue rows and each measure's technical definition (module 2, read only). */
interface Base { signed: boolean; kpis: CatRow[]; tables: CatRow[]; fields: CatRow[]; tech: Record<string, { calculation?: string; confirmed?: string }> }
const cv = (r: CatRow, h: string) => String(r[h]?.value ?? "");
const CAT_MAX = 3; // table and field hits shown per term in the catalogue group
interface Forms {
  goal: { line: string; why: string };
  people: { sponsor: Person | null; participants: Person[]; affected: Person[]; just_me: boolean; not_listed: string[]; affected_may_read: boolean };
  build: { choice: string; note: string };
  definitions: { choice: string; terms: string[]; rejected: string[] };
  areas: string[];
  deadline: string;
}
interface Cell { value: unknown; mark: "stated" | "guessed"; by?: string; from?: string; at?: string; note?: string; terms?: string[]; rejected?: string[]; found?: Found[]; counts?: Counts | null; working_days?: number }
interface Intent {
  id: string; version: number; state: string; title?: string; purpose?: string;
  start_answers?: Partial<Record<Key, Cell>>; stages?: { ref?: { kind: string; id: string } }[];
  links?: { from?: string | null }; north_proposal?: { text?: string } | null; hypothesis_ref?: { id: string; version?: number } | null;
}
interface Draft<K extends Key> { value: Forms[K]; from: string; line: string }

// ---- dates (Monday to Friday; ruling 22) ----
const iso = (d: Date) => d.toISOString().slice(0, 10);
const todayIso = () => iso(new Date());
function addWorkingDays(start: string, n: number): string {
  const d = new Date(`${start}T00:00:00Z`);
  while (n > 0) { d.setUTCDate(d.getUTCDate() + 1); if (d.getUTCDay() % 6 !== 0) n -= 1; }
  return iso(d);
}
function workingDays(start: string, end: string): number {
  const d = new Date(`${start}T00:00:00Z`), e = new Date(`${end}T00:00:00Z`);
  let n = 0;
  while (d < e) { d.setUTCDate(d.getUTCDate() + 1); if (d.getUTCDay() % 6 !== 0) n += 1; }
  return n;
}
/** The stage split: 3/6/1 for the default ten days; otherwise a proposal (spec 22 Open questions 4). */
export function split(n: number): [number, number, number] {
  if (n === DEFAULT_DAYS) return [3, 6, 1];
  const t = Math.max(1, Math.round(n * 0.3));
  return [t, Math.max(1, n - t - 1), 1];
}
const nice = (d: string) => (d ? new Date(`${d}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }) : "");
const names = (xs: string[]) => (xs.length < 2 ? xs.join("") : `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`);
const stem = (w: string) => w.toLowerCase().slice(0, 6);

export function termsOf(text: string): string[] {
  const words = (text.toLowerCase().match(/[a-z][a-z-]{3,}/g) ?? []).filter((w) => !STOP.has(w));
  return [...new Set(words)].slice(0, TERMS_MAX);
}

function blank(): Forms {
  return { goal: { line: "", why: "" }, people: { sponsor: null, participants: [], affected: [], just_me: false, not_listed: [], affected_may_read: false },
    build: { choice: "", note: "" }, definitions: { choice: "", terms: [], rejected: [] }, areas: [], deadline: addWorkingDays(todayIso(), DEFAULT_DAYS) };
}
function fromCells(a: Partial<Record<Key, Cell>>): Forms {
  const f = blank();
  if (a.goal) f.goal = a.goal.value as Forms["goal"];
  if (a.people) f.people = { ...f.people, ...(a.people.value as Forms["people"]) };
  if (a.build) f.build = { choice: String(a.build.value ?? ""), note: a.build.note ?? "" };
  if (a.definitions) f.definitions = { choice: String(a.definitions.value ?? ""), terms: a.definitions.terms ?? [], rejected: a.definitions.rejected ?? [] };
  if (a.areas) f.areas = (a.areas.value as string[]) ?? [];
  if (a.deadline) f.deadline = String(a.deadline.value ?? f.deadline);
  return f;
}

/** The line naming the first missing required item, or "" when the answer may be sent. */
export function missing(key: Key, f: Forms): string {
  const max = addWorkingDays(todayIso(), DEFAULT_DAYS);
  switch (key) {
    case "goal": return !f.goal.line.trim() || f.goal.line.length > GOAL_MAX ? c.goalMissing : f.goal.why.trim().length < WHY_MIN || f.goal.why.length > WHY_MAX ? c.whyMissing : "";
    case "people": return f.people.participants.length > SEATS ? c.seats : f.people.sponsor || f.people.participants.length || f.people.just_me ? "" : c.peopleMissing;
    case "build": return f.build.choice ? "" : c.buildMissing;
    case "definitions": return f.definitions.choice ? "" : c.defsMissing;
    case "areas": return f.areas.length ? "" : c.areasMissing;
    case "deadline": return !/^\d{4}-\d{2}-\d{2}$/.test(f.deadline) ? c.dateMissing : f.deadline <= todayIso() ? c.dateEarly : f.deadline > max ? c.dateLate(nice(max)) : "";
  }
}

const BUILD: Record<string, string> = { yes: c.yes, no: c.no, not_sure: c.notSure };
const DEFS: Record<string, string> = { yes: c.defYes, some: c.defSome, no: c.defNo };

function answerText(key: Key, f: Forms, areaName: (id: string) => string): string {
  const p = f.people;
  switch (key) {
    case "goal": return f.goal.line;
    case "people": return p.just_me && !p.participants.length && !p.sponsor ? c.justMe
      : [p.sponsor ? `${c.sponsor}: ${p.sponsor.name}` : "", p.participants.length ? `${c.takePart}: ${names(p.participants.map((x) => x.name))}` : "",
        p.affected.length ? `${c.affected}: ${names(p.affected.map((x) => x.name))}` : ""].filter(Boolean).join(". ");
    case "build": return BUILD[f.build.choice] ?? "";
    case "definitions": return DEFS[f.definitions.choice] ?? "";
    case "areas": return names(f.areas.map(areaName));
    case "deadline": return nice(f.deadline);
  }
}

function readBack(key: Key, f: Forms, areaName: (id: string) => string): string {
  const p = f.people;
  const body: Record<Key, string> = {
    goal: `So the goal is: ${f.goal.line.trim()}`,
    people: p.just_me && !p.participants.length && !p.sponsor ? "So it is just you for now"
      : `So ${p.participants.length ? `${names(p.participants.map((x) => x.name))} will take part` : "nobody else takes part yet"}${p.sponsor ? `, with ${p.sponsor.name} as sponsor` : ""}${p.affected.length ? `, and ${p.affected.length} affected` : ""}`,
    build: `So you think this ${f.build.choice === "yes" ? "needs a build" : f.build.choice === "no" ? "does not need a build" : "may need a build, and you are not sure yet"}`,
    definitions: `So ${f.definitions.choice === "yes" ? "we have the definitions" : f.definitions.choice === "some" ? "some of the definitions exist" : "we will discover the definitions along the way"}`,
    areas: `So this touches ${names(f.areas.map(areaName))}`,
    deadline: `So this must be decided by ${nice(f.deadline)}, ${workingDays(todayIso(), f.deadline)} working days from today`,
  };
  return `${body[key]}. Is that right?`;
}

function useNarrow(): boolean {
  const q = typeof window !== "undefined" && typeof window.matchMedia === "function" ? window.matchMedia("(max-width: 720px)") : null;
  const [narrow, setNarrow] = useState(q?.matches ?? false);
  useEffect(() => {
    if (!q) return;
    const on = () => setNarrow(q.matches);
    q.addEventListener?.("change", on);
    return () => q.removeEventListener?.("change", on);
  }, [q]);
  return narrow;
}

function Radios({ name, options, value, onChange }: { name: string; options: [string, string][]; value: string; onChange: (v: string) => void }) {
  return (
    <div role="radiogroup" aria-label={name} style={{ display: "flex", flexDirection: "column", gap: 8, margin: "8px 0" }}>
      {options.map(([v, label]) => (
        <label key={v} style={{ display: "flex", gap: 8, alignItems: "center", minHeight: 44 }}>
          <input type="radio" name={name} value={v} checked={value === v} onChange={() => onChange(v)} /> {label}
        </label>
      ))}
    </div>
  );
}

function MarkChip({ mark }: { mark: "stated" | "guessed" }) {
  return <Chip tone={mark === "guessed" ? "default" : "active"}>{mark === "guessed" ? c.guessed : c.stated}</Chip>;
}

export function InitiativeStart({ draftId }: StartProps) {
  const [params, setParams] = useSearchParams();
  const nav = useNavigate();
  const narrow = useNarrow();
  const [rec, setRec] = useState<Intent | null | "failed">(null);
  const [forms, setForms] = useState<Forms>(blank);
  const [drafted, setDrafted] = useState<{ key: Key; from: string } | null>(null); // the current answer came from North's draft, unedited
  const [confirmed, setConfirmed] = useState(false);
  const [skipped, setSkipped] = useState<Key[]>([]);
  const [error, setError] = useState("");
  const [people, setPeople] = useState<Pick[] | "failed" | null>(null);
  const [areas, setAreas] = useState<{ id: string; name: string }[]>([]);
  const [glossary, setGlossary] = useState<{ term_id?: string; term: string; aliases?: string[]; owner?: string | null; confirmed_at?: string | null; restricted?: boolean }[] | "failed" | null>(null);
  const [base, setBase] = useState<Base | "failed" | "none" | null>(null);
  const [source, setSource] = useState<{ title: string; summary: string } | null>(null);
  const [query, setQuery] = useState("");
  const [moved, setMoved] = useState("");
  const [notListed, setNotListed] = useState<string | null>(null);
  const [newTerm, setNewTerm] = useState("");
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState<{ text: string; mark: "stated" | "guessed" } | null>(null);
  const [editing, setEditing] = useState(false);
  const [opening, setOpening] = useState(false);
  const [openFailed, setOpenFailed] = useState("");
  const changeRef = useRef<HTMLDivElement>(null);
  const control = useRef<HTMLDivElement>(null);
  const summaryBox = useRef<HTMLTextAreaElement>(null);

  const answers: Partial<Record<Key, Cell>> = rec && rec !== "failed" ? rec.start_answers ?? {} : {};
  const firstOpen = QUESTIONS.find((q) => !answers[q.key])?.key ?? "review";
  const raw = params.get("step");
  const step: Key | "review" = raw === "review" ? (firstOpen === "review" ? "review" : firstOpen)
    : QUESTIONS.some((q) => q.key === raw) && (answers[raw as Key] || raw === firstOpen) ? (raw as Key) : firstOpen;
  const index = QUESTIONS.findIndex((q) => q.key === step);
  const areaName = useCallback((id: string) => areas.find((a) => a.id === id)?.name ?? id, [areas]);

  const load = useCallback(() => {
    setRec(null);
    apiGet<Intent>(`/api/intents/${draftId}`).then((r) => {
      setRec(r); setForms(fromCells(r.start_answers ?? {})); setTitle(r.title ?? "");
      if (r.links?.from) apiGet<{ title?: string; closure?: { summary?: string } }>(`/api/intents/${r.links.from}`)
        .then((s) => setSource({ title: s.title ?? "", summary: s.closure?.summary ?? "" }), () => undefined);
    }, () => setRec("failed"));
    apiGet<{ people: Pick[] }>("/api/intents/people").then((r) => setPeople(r.people), () => setPeople("failed"));
    apiGet<{ areas: { id: string; name: string }[] }>("/api/intents/areas").then((r) => setAreas(r.areas ?? []), () => setAreas([]));
  }, [draftId]);
  useEffect(load, [load]);

  const lookup = useCallback(() => {
    apiGet<{ terms: NonNullable<typeof glossary> }>(`/api/intents/${draftId}/glossary-start`).then((r) => setGlossary(Array.isArray(r.terms) ? r.terms : "failed"), () => setGlossary("failed"));
  }, [draftId]);
  useEffect(() => { if (answers.goal && glossary === null) lookup(); }, [answers.goal, glossary, lookup]);
  useEffect(() => { // technical definitions and catalogue: the existing module 2 reads, in the viewer's own permissions
    if (!answers.goal || base !== null) return;
    const M2 = "/api/modules/m2_baseline/baselines";
    const M2_ROLES = ["company_admin", "sponsor", "analyst"]; // who may read module 2 (route permissions); others get the "could not be read for you" line, not a refused call
    apiGet<{ roles?: string[] }>("/api/auth/me").then((me) => {
      if (Array.isArray(me.roles) && !me.roles.some((x) => M2_ROLES.includes(x))) throw new Error("not for this role");
      return apiGet<{ baselines: { id: string; state: string; kpi_count: number }[] }>(M2);
    }).then(async (r) => {
      const b = r.baselines.find((x) => x.state === "signed") ?? r.baselines.find((x) => x.kpi_count > 0);
      if (!b) return setBase("none");
      const k = await apiGet<{ signed: boolean; kpis: CatRow[]; tables: CatRow[]; fields: CatRow[]; technical?: { kpis?: Base["tech"] } }>(`${M2}/${b.id}/catalogue`);
      setBase({ signed: k.signed, kpis: k.kpis ?? [], tables: k.tables ?? [], fields: k.fields ?? [], tech: k.technical?.kpis ?? {} });
    }).catch(() => setBase("failed"));
  }, [answers.goal, base]);

  useEffect(() => { setConfirmed(false); setDrafted(null); setError(""); setMoved(""); }, [step]);
  // Pin the step in the route (spec 22: the tile lands on step=goal); without it, saving an answer would jump to the next question.
  useEffect(() => {
    if (rec && rec !== "failed" && !raw) setParams((p) => { const n = new URLSearchParams(p); n.set("step", firstOpen); return n; }, { replace: true });
  }, [rec, raw, firstOpen, setParams]);
  useEffect(() => { // the terms strip starts from the goal and why; North runs the look-up before question 3 so its leaning has counts
    if ((step === "build" || step === "definitions") && forms.definitions.terms.length === 0 && !answers.definitions && forms.goal.line)
      setForms((f) => ({ ...f, definitions: { ...f.definitions, terms: termsOf(`${f.goal.line} ${f.goal.why}`) } }));
  }, [step, forms.definitions.terms.length, forms.goal, answers.definitions]);

  // ---- the look-up against the terms strip ----
  const hits = (term: string, name: string) => name.toLowerCase().split(/[^a-z0-9]+/).some((w) => w.length > 2 && stem(w) === stem(term));
  const found: Found[] = useMemo(() => {
    const out: Found[] = [];
    for (const t of forms.definitions.terms) {
      if (Array.isArray(glossary)) {
        for (const g of glossary) {
          if (g.restricted || !g.term_id) continue;
          if ([g.term, ...(g.aliases ?? [])].some((n) => hits(t, n)))
            out.push({ term: t, kind: "glossary", entry_ref: g.term_id, name: g.term, status: g.confirmed_at ? "signed" : "draft", owner: g.owner ?? null });
        }
      }
      if (base && base !== "failed" && base !== "none") {
        const state = base.signed ? "signed" : "draft";
        for (const k of base.kpis) {
          const id = cv(k, "KPI ID"), name = cv(k, "KPI name");
          if (!id || !hits(t, name)) continue;
          const tech = base.tech[id];
          if (tech?.calculation) out.push({ term: t, kind: "technical", entry_ref: `tech:${id}`, name, status: tech.confirmed ? "signed" : "draft", owner: cv(k, "Data owner") || null });
          out.push({ term: t, kind: "catalogue", entry_ref: `cat:${id}`, name, status: state, owner: cv(k, "Business owner") || null });
        }
        const more: [string, string][] = [...base.tables.map((r): [string, string] => [cv(r, "Item ID"), cv(r, "Name of table, file or document type")]), ...base.fields.map((r): [string, string] => [cv(r, "Field ID"), cv(r, "Field name as in the source")])];
        more.filter(([id, name]) => id && hits(t, name)).slice(0, CAT_MAX)
          .forEach(([id, name]) => out.push({ term: t, kind: "catalogue", entry_ref: `cat:${id}`, name, status: state, owner: null }));
      }
    }
    return out;
  }, [glossary, base, forms.definitions.terms]);
  const kept = found.filter((h) => !forms.definitions.rejected.includes(`${h.term}|${h.entry_ref}`));
  const baseReady = !!base && base !== "failed" && base !== "none";
  const termsWith = (kind: Found["kind"]) => new Set(kept.filter((h) => h.kind === kind).map((h) => h.term)).size;
  const counts: Counts | null = Array.isArray(glossary)
    ? { terms: forms.definitions.terms.length, business: termsWith("glossary"), technical: baseReady ? termsWith("technical") : null, catalogue: baseReady ? termsWith("catalogue") : null } : null;

  // ---- North's drafts, per question ----
  const draftFor = (key: Key): Draft<Key> | null => {
    if (skipped.includes(key)) return null;
    const p = rec && rec !== "failed" ? rec : null;
    switch (key) {
      case "goal":
        if (source?.title) return { value: { line: source.title.slice(0, GOAL_MAX), why: source.summary.slice(0, WHY_MAX) }, from: c.fromIntent(source.title), line: source.title };
        if (p?.north_proposal?.text) return { value: { line: p.north_proposal.text.slice(0, GOAL_MAX), why: "" }, from: c.fromTyped, line: p.north_proposal.text };
        return null;
      case "people": { // the company list carries the roster's sponsor flag; a guess until the starter keeps it
        if (forms.people.sponsor || !Array.isArray(people)) return null;
        const hit = people.find((x) => x.is_sponsor);
        return hit ? { value: { ...forms.people, sponsor: { account_id: hit.person_id, name: hit.name }, just_me: false }, from: c.fromProfile, line: `${c.sponsor}: ${hit.name}. Named as the sponsor in the company profile.` } : null;
      }
      case "build": {
        if (!counts || !counts.terms) return null;
        const inCat = counts.catalogue !== null;
        const gap = counts.terms - (inCat ? counts.catalogue! : counts.business);
        return gap > 0 ? { value: { choice: "yes", note: "" }, from: c.fromLookup, line: inCat ? `Likely yes: ${gap} of the ${counts.terms} terms you named are not in the catalogue yet.` : `Likely yes: ${gap} of the ${counts.terms} terms you named have no business definition yet.` }
          : { value: { choice: "not_sure", note: "" }, from: c.fromLookup, line: "Not sure: every term you named has a business definition, but nothing in the profile says where the data lives." };
      }
      case "definitions": {
        if (!counts || !counts.terms) return null;
        const allSigned = counts.business === counts.terms && kept.every((h) => h.status === "signed");
        const choice = allSigned ? "yes" : counts.business > 0 ? "some" : "no";
        return { value: { ...forms.definitions, choice }, from: c.fromLookup, line: `${DEFS[choice]}: ${counts.business} of ${counts.terms} terms have a business definition.` };
      }
      default: return null; // areas: the picker carries North's suggestion; deadline: only the default, no other source yet
    }
  };

  const edit = <K extends Key>(key: K, value: Forms[K]) => { setForms((f) => ({ ...f, [key]: value })); setDrafted(null); setConfirmed(false); };

  // ---- saving ----
  const cellFor = (key: Key): Cell => {
    const f = forms;
    const mark: Cell["mark"] = drafted?.key === key || (key === "build" && f.build.choice === "not_sure") ? "guessed" : "stated";
    const from = drafted?.key === key ? drafted.from : "";
    switch (key) {
      case "build": return { value: f.build.choice, note: f.build.note.trim(), mark, from };
      case "definitions": return { value: f.definitions.choice, terms: f.definitions.terms, rejected: f.definitions.rejected, found: kept, counts, mark, from };
      case "deadline": return { value: f.deadline, working_days: workingDays(todayIso(), f.deadline), mark, from };
      default: return { value: f[key], mark, from };
    }
  };
  const save = async (key: Key): Promise<boolean> => {
    if (!rec || rec === "failed") return false;
    setError("");
    try {
      const r = await apiSend<Intent>("PUT", `/api/intents/${rec.id}/start`, { version: rec.version, key, cell: cellFor(key) });
      setRec(r);
      if (key === "goal") { setTitle(r.title ?? ""); lookup(); }
      return true;
    } catch {
      setError(c.saveFailed);
      return false;
    }
  };
  const go = (to: Key | "review") => setParams((p) => { const n = new URLSearchParams(p); n.set("step", to); return n; });
  const leave = () => nav("/centre/intent", { state: { toast: c.toast } });

  if (rec === null) return <ScreenState state="loading" />;
  if (rec === "failed") return <ScreenState state="error" message={c.loadFailed} onRetry={load} />;

  // ---- frame pieces ----
  const stepper = (
    <ol aria-label="Steps" style={{ display: "flex", flexWrap: "wrap", gap: 6, listStyle: "none", padding: 0, margin: "8px 0 16px" }}>
      {QUESTIONS.map((q, i) => {
        const done = !!answers[q.key];
        return (
          <li key={q.key}>
            <button type="button" className={`ds-chip${step === q.key ? " ds-chip--active" : ""}`} aria-current={step === q.key ? "step" : undefined}
              disabled={!done && q.key !== firstOpen} onClick={() => go(q.key)}>
              {i + 1} {q.label}{done ? " ✓" : ""}
            </button>
          </li>
        );
      })}
      <li><button type="button" className={`ds-chip${step === "review" ? " ds-chip--active" : ""}`} disabled={firstOpen !== "review"} onClick={() => go("review")}>{c.review}</button></li>
    </ol>
  );
  const rows = QUESTIONS.filter((q) => answers[q.key]);
  const carriedFrom = rec.hypothesis_ref ? Object.values(answers).find((x) => x?.from?.startsWith("The opportunity"))?.from ?? "" : "";
  const soFarBody = rows.length === 0 ? <p className="n-muted">{c.nothingYet}</p> : (
    <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
      {rows.map((q) => (
        <li key={q.key} style={{ marginBottom: 10 }}>
          <strong>{q.label}</strong>: {answerText(q.key, fromCells(answers), areaName)} <MarkChip mark={answers[q.key]!.mark} />{" "}
          <button type="button" className="ds-link" style={LINK} onClick={() => go(q.key)}>{c.change}</button>
        </li>
      ))}
    </ul>
  );
  const top = (
    <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
      <Chip>{c.type}</Chip> <Link className="ds-link" to="/centre/intent/new">{c.changeType}</Link>
      {carriedFrom && <p className="n-muted" style={{ flexBasis: "100%", margin: 0 }}>{c.carried(carriedFrom)}</p>}
    </div>
  );

  if (step === "review") return review();

  const q = QUESTIONS[index]!;
  const d = draftFor(q.key);
  const why = missing(q.key, forms);

  const use = () => {
    if (!d) return;
    setForms((f) => ({ ...f, [q.key]: d.value }));
    setDrafted({ key: q.key, from: d.from });
    setConfirmed(false);
  };
  const right = async () => { if (await save(q.key)) setConfirmed(true); };
  const next = () => go(QUESTIONS.find((x) => !answers[x.key])?.key ?? "review");

  return (
    <div>
      {top}
      {stepper}
      <div style={{ display: "flex", gap: 24, flexWrap: "wrap", alignItems: "flex-start" }}>
        <div style={{ flex: "2 1 420px", minWidth: 0 }}>
          {narrow && (
            <details className="ds-card" style={{ padding: 12, marginBottom: 12 }}>
              <summary style={{ minHeight: 44, display: "flex", alignItems: "center" }}>{c.questionOf(index + 1)}</summary>
              {soFarBody}
            </details>
          )}
          <AgentChip name="North" status="waiting" />
          <div aria-live="polite">
            <MessageBubble from="agent" who="North" text={q.lead}>
              <p className="n-muted">{c.whyAsk} {q.why}</p>
            </MessageBubble>
          </div>
          <div ref={control} style={{ margin: "12px 0" }}>{controlFor(q.key)}</div>
          {q.key !== "areas" && (d ? (
            <Panel title={c.draftTitle} eyebrow={c.suggestion}>
              {narrow ? <details><summary>{d.line}</summary><p className="n-muted">{d.from}</p></details> : <><p>{d.line}</p><p className="n-muted">{d.from}</p></>}
              <Chip>{c.guessed}</Chip>{" "}
              <Button onClick={use}>{c.useDraft}</Button> <Button onClick={() => setSkipped((s) => [...s, q.key])}>{c.skipDraft}</Button>
            </Panel>
          ) : q.key === "build" ? <Panel title={c.draftTitle}><p>{c.cannotSay}</p></Panel>
            : q.key === "deadline" ? null : <Panel title={c.draftTitle}><p>{c.noDraft}</p></Panel>)}
          {!why && !confirmed && (
            <MessageBubble from="agent" who="North" text={readBack(q.key, forms, areaName)}>
              <Button variant="primary" onClick={() => void right()}>{c.right}</Button>{" "}
              <Button onClick={() => control.current?.querySelector<HTMLElement>("input, textarea, select, button")?.focus()}>{c.correct}</Button>
            </MessageBubble>
          )}
          {why && <p className="n-muted" role="status">{why}</p>}
          {error && <p role="alert" className="state state-error">{error}</p>}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 16, padding: "8px 0" }}>
            {index > 0 && <Button onClick={() => go(QUESTIONS[index - 1]!.key)}>{c.back}</Button>}
            <Button variant="primary" disabled={!!why || !confirmed} onClick={next} style={narrow ? { width: "100%", order: -1 } : undefined}>{c.next}</Button>
            <Button onClick={leave}>{c.saveLeave}</Button>
          </div>
        </div>
        {!narrow && <div style={{ flex: "1 1 260px" }}><Panel title={c.soFar}>{soFarBody}</Panel></div>}
      </div>
    </div>
  );

  // ---- the answer controls ----
  function controlFor(key: Key): ReactNode {
    const f = forms;
    if (key === "goal") return (
      <>
        <label className="ds-label" style={{ display: "block" }}>{c.goalLine}
          <input type="text" className="ds-input" maxLength={GOAL_MAX} placeholder={c.goalPlaceholder} value={f.goal.line} style={{ width: "100%" }}
            onChange={(e) => edit("goal", { ...f.goal, line: e.target.value })} />
        </label>
        {f.goal.line && <p className="n-muted">{c.of(f.goal.line.length, GOAL_MAX)}</p>}
        <label className="ds-label" style={{ display: "block", marginTop: 12 }}>{c.goalWhy}
          <textarea className="ds-input" maxLength={WHY_MAX} rows={4} value={f.goal.why} style={{ width: "100%" }}
            onChange={(e) => edit("goal", { ...f.goal, why: e.target.value })} />
        </label>
        {f.goal.why && <p className="n-muted">{c.of(f.goal.why.length, WHY_MAX)}</p>}
      </>
    );
    if (key === "people") {
      const p = f.people;
      if (people === null) return <ScreenState state="loading" />;
      const list = Array.isArray(people) ? people : [];
      const groupOf = (id: string) => (p.sponsor?.account_id === id ? "sponsor" : p.participants.some((x) => x.account_id === id) ? "take" : p.affected.some((x) => x.account_id === id) ? "affected" : "");
      const setGroup = (x: Pick, g: string) => {
        const me: Person = { account_id: x.person_id, name: x.name };
        const was = groupOf(x.person_id);
        const out = (xs: Person[]) => xs.filter((y) => y.account_id !== x.person_id);
        const np = { ...p, sponsor: p.sponsor?.account_id === x.person_id ? null : p.sponsor, participants: out(p.participants), affected: out(p.affected) };
        if (g === "sponsor") np.sponsor = me;
        if (g === "take") np.participants = [...np.participants, me];
        if (g === "affected") np.affected = [...np.affected, me];
        if (g === "sponsor" || g === "take") np.just_me = false;
        edit("people", np);
        setMoved(was && g && was !== g ? c.movedNote(x.name, { sponsor: c.sponsor, take: c.takePart, affected: c.affected }[g] ?? g) : "");
      };
      const shown = list.filter((x) => `${x.name} ${x.role ?? ""} ${x.area ?? ""}`.toLowerCase().includes(query.trim().toLowerCase()));
      return (
        <>
          {list.length === 0 ? <p className="n-muted">{c.noPeople} <Link to="/company/profile">{c.profileLink}</Link></p> : (
            <>
              <input type="search" aria-label={c.searchPeople} placeholder={c.searchPeople} value={query} onChange={(e) => setQuery(e.target.value)} />
              <ul style={{ listStyle: "none", padding: 0, maxHeight: 320, overflowY: "auto" }}>
                {shown.map((x) => (
                  <li key={x.person_id} style={{ display: "flex", gap: 8, alignItems: "center", justifyContent: "space-between", minHeight: 44, flexWrap: "wrap" }}>
                    <span><strong>{x.name}</strong>{x.role ? `, ${x.role}` : ""}{x.area ? `, ${x.area}` : ""}</span>
                    <select aria-label={x.name} style={{ width: "auto", minWidth: 150 }} value={groupOf(x.person_id)} onChange={(e) => setGroup(x, e.target.value)}>
                      <option value="">{c.nobody}</option><option value="sponsor">{c.sponsor}</option><option value="take">{c.takePart}</option><option value="affected">{c.affected}</option>
                    </select>
                  </li>
                ))}
              </ul>
            </>
          )}
          {moved && <p className="n-muted" role="status">{moved}</p>}
          <p><strong>{c.sponsor}</strong>: {p.sponsor?.name ?? c.nobody}. <strong>{c.takePart}</strong>: {p.participants.length ? names(p.participants.map((x) => x.name)) : c.nobody}.</p>
          <p><strong>{c.affected}</strong>: {p.affected.length ? names(p.affected.map((x) => x.name)) : c.affectedEmpty}</p>
          {!p.participants.length && !p.sponsor && (
            <label style={{ display: "flex", gap: 8, alignItems: "center", minHeight: 44 }}>
              <input type="checkbox" checked={p.just_me} onChange={(e) => edit("people", { ...p, just_me: e.target.checked })} /> {c.justMe}
            </label>
          )}
          {p.affected.length > 0 && (
            <label style={{ display: "block", minHeight: 44 }}>
              <input type="checkbox" role="switch" checked={p.affected_may_read} onChange={(e) => edit("people", { ...p, affected_may_read: e.target.checked })} /> {c.mayRead}
              <span className="n-muted" style={{ display: "block" }}>{c.mayReadLine}</span>
            </label>
          )}
          {notListed === null ? <button type="button" className="ds-link" style={LINK} onClick={() => setNotListed("")}>{c.notListed}</button> : (
            <div>
              <label className="ds-label">{c.notListedLabel} <input type="text" maxLength={120} value={notListed} onChange={(e) => setNotListed(e.target.value)} /></label>{" "}
              <Button disabled={!notListed.trim()} onClick={() => { edit("people", { ...p, not_listed: [...p.not_listed, notListed.trim()] }); setNotListed(null); }}>{c.add}</Button>
            </div>
          )}
          {p.not_listed.length > 0 && <p className="n-muted">{p.not_listed.join("; ")}</p>}
        </>
      );
    }
    if (key === "build") return (
      <>
        <p className="n-muted">{c.buildLine}</p>
        <Radios name={q.lead} value={f.build.choice} options={[["yes", c.yes], ["no", c.no], ["not_sure", c.notSure]]} onChange={(v) => edit("build", { ...f.build, choice: v })} />
        {f.build.choice === "not_sure" && (
          <label className="ds-label">{c.whyNotSure} <input type="text" maxLength={140} value={f.build.note} onChange={(e) => edit("build", { ...f.build, note: e.target.value })} /></label>
        )}
      </>
    );
    if (key === "definitions") {
      const df = f.definitions;
      const setTerms = (terms: string[]) => edit("definitions", { ...df, terms });
      return (
        <>
          <p><strong>{c.terms}</strong></p>
          {df.terms.length === 0 ? <p className="n-muted">{c.noTerms}</p> : (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {df.terms.map((t) => <Chip key={t} tone="active" onClick={() => setTerms(df.terms.filter((x) => x !== t))}>{t} ({c.remove})</Chip>)}
            </div>
          )}
          <div style={{ display: "flex", gap: 8, margin: "8px 0", flexWrap: "wrap" }}>
            <input type="text" aria-label={c.addTerm} placeholder={c.addTerm} maxLength={60} value={newTerm} onChange={(e) => setNewTerm(e.target.value)} />
            <Button disabled={!newTerm.trim() || df.terms.length >= TERMS_MAX} onClick={() => { setTerms([...new Set([...df.terms, newTerm.trim().toLowerCase()])]); setNewTerm(""); }}>{c.addTerm}</Button>
          </div>
          <Panel title={c.exists}>
            {([["glossary", c.business], ["technical", c.technical], ["catalogue", c.catalogue]] as const).map(([kind, label]) => {
              const na = kind === "glossary" ? (glossary === "failed" ? c.lookupNa : glossary && glossary.length === 0 ? c.noBaseline : null)
                : base === "failed" ? c.baseNa : base === "none" ? c.baseNone : null;
              const wait = kind === "glossary" ? glossary === null : base === null;
              const rows = found.filter((h) => h.kind === kind);
              return (
                <div key={kind}>
                  <p><strong>{label}</strong></p>
                  {wait ? <ScreenState state="loading" /> : na ? <p>{na}</p> : rows.length === 0 ? <p>{c.nothingMatches}</p> : (
                    <ul>
                      {rows.map((h) => {
                        const id = `${h.term}|${h.entry_ref}`;
                        const no = df.rejected.includes(id);
                        return (
                          <li key={id} style={no ? { textDecoration: "line-through" } : undefined}>
                            {h.term}: {h.name}, {h.status === "signed" ? c.signed : c.draft}{h.owner ? `. ${c.ownerIs(h.owner)}` : ""}{" "}
                            {!no && <button type="button" className="ds-link" style={LINK} onClick={() => edit("definitions", { ...df, rejected: [...df.rejected, id] })}>{c.notIt}</button>}
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </div>
              );
            })}
            {counts && (
              <p>
                {counts.business} of {counts.terms} terms have a business definition.
                {counts.technical !== null && ` ${c.techCount(counts.technical)}`}
                {counts.catalogue !== null && ` ${c.catCount(counts.catalogue)}`}
              </p>
            )}
          </Panel>
          <Radios name={q.lead} value={df.choice} options={[["yes", c.defYes], ["some", c.defSome], ["no", c.defNo]]} onChange={(v) => edit("definitions", { ...df, choice: v })} />
          {df.choice && <p>{c.means[df.choice]}</p>}
        </>
      );
    }
    if (key === "areas") {
      const chosen = new Set([f.people.sponsor, ...f.people.participants].filter(Boolean).map((x) => x!.account_id));
      const picked = Array.isArray(people) ? people.filter((x) => chosen.has(x.person_id) && x.area) : [];
      const ids = picked.map((x) => areas.find((a) => a.name.toLowerCase() === x.area!.toLowerCase())?.id).filter((x): x is string => !!x);
      return (
        <>
          <p className="n-muted">{c.areasHelp}</p>
          <AreaPicker value={f.areas} onChange={(v) => edit("areas", v)} affectedMayRead={f.people.affected_may_read}
            suggestion={ids.length ? { names: picked.filter((x) => ids.includes(areas.find((a) => a.name.toLowerCase() === x.area!.toLowerCase())?.id ?? "")).map((x) => x.name), areaIds: [...new Set(ids)] } : undefined} />
        </>
      );
    }
    const n = /^\d{4}-\d{2}-\d{2}$/.test(f.deadline) ? workingDays(todayIso(), f.deadline) : 0;
    const [t, dd, b] = split(n);
    const max = addWorkingDays(todayIso(), DEFAULT_DAYS);
    return (
      <>
        <label className="ds-label" style={{ display: "block" }}>{c.decideBy}{" "}
          <input type="date" value={f.deadline} min={addWorkingDays(todayIso(), 1)} max={max} onChange={(e) => edit("deadline", e.target.value)} />
        </label>
        {n > 0 && <p>{c.thatIs(n)}</p>}
        {n > 0 && <p>{c.split(t, dd, b)}</p>}
        {n > 0 && n !== DEFAULT_DAYS && (
          <Panel title={c.draftTitle} eyebrow={c.suggestion}><p>{c.usual(n)}</p>{dd <= 1 && <p className="ds-warn">{c.tight}</p>}</Panel>
        )}
        <p className="n-muted">{c.defaultNote}</p>
      </>
    );
  }

  // ---- Screen B: "Here is what I understood" ----
  function review(): ReactNode {
    const me = rec as Intent;
    const f = fromCells(answers);
    const p = f.people;
    const n = workingDays(todayIso(), f.deadline);
    const think = split(n)[0];
    const invited = p.participants.length + (p.sponsor ? 1 : 0);
    const ac = answers.definitions?.counts;
    const firstDraft = [
      `The goal: ${f.goal.line.trim().replace(/\.$/, "")}.`,
      `Why it matters: ${f.goal.why.trim()}`,
      p.participants.length || p.sponsor ? `${p.sponsor ? `${p.sponsor.name} sponsors it. ` : ""}${p.participants.length ? `${names(p.participants.map((x) => x.name))} take part.` : ""}${p.affected.length ? ` ${p.affected.length} more ${p.affected.length === 1 ? "is" : "are"} affected.` : ""}` : "It is just you for now.",
      `You think it ${f.build.choice === "yes" ? "needs a build" : f.build.choice === "no" ? "does not need a build" : "may need a build"}.`,
      `Definitions: ${DEFS[f.definitions.choice] ?? ""}${ac && ac.terms ? ` (${ac.business} of ${ac.terms} terms have a business definition)` : ""}.`,
      `It touches ${names(f.areas.map(areaName))} and must be decided by ${nice(f.deadline)}.`,
    ].join(" ");
    const s = summary ?? { text: firstDraft, mark: "guessed" as const };
    const block = !s.text.trim() ? c.summaryMissing : !title.trim() ? c.titleMissing : "";
    const saveTitle = async () => {
      if (!title.trim() || title === me.title) return;
      try { setRec(await apiSend<Intent>("PUT", `/api/intents/${me.id}`, { version: me.version, title: title.trim() })); } catch { setError(c.saveFailed); }
    };
    const open = async () => {
      setOpening(true); setOpenFailed("");
      try {
        const r = await apiSend<Intent>("POST", `/api/intents/${me.id}/start/open`, { version: me.version, title: title.trim(), summary: s });
        nav(`/centre/intent/${r.id}`);
      } catch (e) {
        setOpenFailed(e instanceof Error ? e.message : "");
        apiGet<Intent>(`/api/intents/${draftId}`).then(setRec, () => undefined); // a wall prepared on this try is reused on the next (stages[0].ref)
      }
      setOpening(false);
    };
    return (
      <div>
        {top}
        {stepper}
        <div className="ds-card" style={{ maxWidth: 720, margin: "0 auto", padding: narrow ? 12 : 20 }}>
          <AgentChip name="North" status="waiting" />
          <MessageBubble from="agent" who="North" text={c.lead} />
          <Panel title={c.summaryLabel} eyebrow={s.mark === "guessed" ? c.suggestion : undefined}
            actions={<MarkChip mark={s.mark} />}>
            {editing ? (
              <>
                <textarea aria-label={c.summaryLabel} className="ds-input" rows={6} style={{ width: "100%" }} maxLength={2000} defaultValue={s.text} ref={summaryBox} />
                <Button onClick={() => { const v = summaryBox.current?.value ?? s.text; setSummary({ text: v, mark: "stated" }); setEditing(false); }}>{c.saveSummary}</Button>
              </>
            ) : <><p>{s.text}</p><button type="button" className="ds-link" style={LINK} onClick={() => setEditing(true)}>{c.editSummary}</button></>}
          </Panel>
          <div ref={changeRef}>
            <ul style={{ listStyle: "none", padding: 0 }}>
              {QUESTIONS.map((x) => (
                <li key={x.key} style={{ padding: "8px 0", borderBottom: "1px solid var(--ds-line)" }}>
                  <p className="n-muted" style={{ margin: 0 }}>{x.lead}</p>
                  <p style={{ margin: "4px 0" }}>{answerText(x.key, f, areaName)}</p>
                  <MarkChip mark={answers[x.key]!.mark} /> <button type="button" className="ds-link" style={LINK} onClick={() => go(x.key)}>{c.change}</button>
                </li>
              ))}
            </ul>
          </div>
          <label className="ds-label" style={{ display: "block" }}>{c.titleLabel}
            <input type="text" className="ds-input" maxLength={TITLE_MAX} value={title} style={{ width: "100%" }} onChange={(e) => setTitle(e.target.value)} onBlur={() => void saveTitle()} />
          </label>
          <Panel label="Hand-over">
            <p>{c.handover(think, invited, f.goal.line.trim())}</p>
            <p>{c.lanes}</p>
          </Panel>
          {openFailed !== "" || opening ? null : block ? <p className="n-muted" role="status">{block}</p> : null}
          {openFailed !== "" && (
            <div role="alert" className="state state-error">
              <p>{c.openFailed}</p>{openFailed && openFailed !== c.openFailed && <p className="n-muted">{openFailed}</p>}
              <Button onClick={() => void open()}>{c.tryAgain}</Button>
            </div>
          )}
          {error && <p role="alert" className="state state-error">{error}</p>}
          <div style={{ display: "flex", flexDirection: narrow ? "column" : "row", gap: 8, marginTop: 16 }}>
            <Button variant="primary" disabled={!!block || opening} onClick={() => void open()} style={narrow ? { minHeight: 56 } : undefined}>{opening ? c.opening : c.open}</Button>
            <Button onClick={() => changeRef.current?.querySelector<HTMLButtonElement>("button")?.focus()} style={narrow ? { minHeight: 56 } : undefined}>{c.changeSomething}</Button>
            <Button onClick={leave} style={narrow ? { minHeight: 56 } : undefined}>{c.saveDraftLeave}</Button>
          </div>
        </div>
      </div>
    );
  }
}

export default InitiativeStart;
