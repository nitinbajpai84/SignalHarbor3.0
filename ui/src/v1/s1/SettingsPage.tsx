import { useEffect, useState, type ReactNode } from "react";
import { Link, Navigate, NavLink, useParams } from "react-router-dom";

import { ApiError, apiGet, apiSend } from "../../api/client";
import MemoryPage from "../../pages/MemoryPage";
import RegisterPage from "../../pages/RegisterPage";
import { day as dayOf, when as whenAt } from "../../design/dates";
import { landingFor, settingsFor } from "../../shell/roles";
import { useSession } from "../../useSession";
import AdminModel from "../e0a/AdminModel";
import AdminRules from "../e3a/AdminRules";
import AccessPage from "../k1/AccessPage";
import PeopleRoles from "../k1/PeopleRoles";
import ModeSwitch, { MODE_WORDS } from "../router/ModeSwitch";
import AdminAgents from "../t1/AdminAgents";
import ConnectorsPage from "../c5/ConnectorsPage";
import McpTokens from "./McpTokens";
import KnowledgePage from "../teach/KnowledgePage";
import CycleDateSetting from "../router/CycleDate";

// K8: agent runs and cost, from the E6a route (company administrator only; the server decides).
export interface AgentDay { agent_type: string; day: string; runs: number; failures: number; tool_calls: number; cost_usd: number | null }
export interface AgentRun { id: string; agent_type: string; status: string; started_at: string | null; tool_calls: number | null; cost_usd: number | null; exception_id: string | null; trace_id?: string | null }
const AGENTS: Record<string, string> = { north: "North, the industry expert", span: "Span, the build agent", lumen: "Lumen, the consume agent", tally: "Tally, the data analyst" };
const cost = (v: number | null) => (v === null || v === undefined ? "Not available yet" : v > 0 && v < 0.01 ? "USD 0.00 (under a cent)" : `USD ${v.toFixed(2)}`);

// W14/PF2: one date style for both lists, "9 Oct 2026, 09:12" in the company's time zone; a day alone is "9 Oct 2026" and never shifts.
export const stamp = (iso: string) => whenAt(iso, iso);
export const dayLabel = (d: string) => dayOf(d, d);
const when = (iso: string | null) => (iso ? ` on ${stamp(iso)}` : "");
const usd = (v: number) => `USD ${v.toFixed(4)}`;

// MEM2b: the steps of one run, in plain words (GET /api/v1/agent-runs/trace/{id}); no prompt, answer or figure is ever in them.
type Attempt = { tier?: string | null; model?: string | null; step?: string | null; ok?: string | boolean | null; note?: string | null };
type Step = { kind: string; n?: number; tier?: string; model?: string | null; mode?: string | null; tokens_in?: number; tokens_out?: number; ms?: number; ok?: boolean;
  cost_usd?: number | null; estimated?: boolean; tool?: string; result_chars?: number; refused?: boolean; repeat?: boolean; reason?: string | null; skipped?: string;
  final?: boolean; numbers_replaced?: number; items?: { kind: string; id: string; label?: string }[]; attempts?: Attempt[];
  masked?: number; escalation?: string; replaced?: { kind: string; counts?: string }[]; sql?: { starts_with?: string; tables?: string[] } };
const KINDS: Record<string, string> = { memory: "remembered item", summary: "earlier conversation", graph: "related topic", passage: "document passage", turns: "earlier turns" };
// RC-8/TS1-02: why a model step did not go through, in plain words
const REASONS: Record<string, string> = { vault_name: "refused by the gateway (a protected name)", raw_rows: "refused by the gateway (raw rows)",
  suppressed_figure: "refused by the gateway (a figure of a small group)", transport_failed: "the model provider did not answer",
  no_credit: "the model provider account is out of credit", rate_limited: "the model provider's rate limit was reached",
  provider_key_refused: "the model provider refused the access key", model_unknown: "the model provider does not offer that model",
  provider_bad_request: "the model provider would not take the request",
  no_credential: "no model key is set up", vault_unavailable: "the name vault could not be read", empty: "empty reply", number_guard: "a figure it could not source",
  not_json: "not the answer format asked for", no_change: "nothing to change" };
// SS-5: what kind of figure the number check replaced (never the value)
const FIGURE_KINDS: Record<string, string> = { number: "a number", percent: "a percentage", number_in_words: "a number in words" };
const why = (r?: string | null | boolean) => (typeof r === "string" ? REASONS[r] ?? r.replace(/_/g, " ") : "");
const MODES: Record<string, string> = { testing: "Testing", real: "Real use" };
export function stepLine(s: Step): string {
  if (s.kind === "model") {
    const tried = (s.attempts ?? []).length > 1 ? ` Tried: ${(s.attempts ?? []).map((a) => `${a.tier ?? "model"}${a.model ? ` (${a.model})` : ""}${a.ok && a.ok !== "ok" ? `: ${why(a.ok)}` : ""}`).join(", then ")}.` : "";
    // TS1c-05: how many names were masked; RC2-2: a check failed but this mode has no stronger model to ask
    const masked = s.masked != null ? ` ${s.masked} name${s.masked === 1 ? " was" : "s were"} masked before it left.` : "";
    const esc = s.escalation ? ` A check failed and was not asked again: ${s.escalation}.` : "";
    return `Model step ${s.n ?? ""}${s.final ? " (answer now)" : ""}: ${s.tier ? `${s.tier} model, ` : ""}${s.model ? `${s.model}, ` : ""}${s.mode ? `${MODES[s.mode] ?? s.mode}, ` : ""}${s.tokens_in != null ? `${s.tokens_in} tokens in, ${s.tokens_out ?? 0} out, ` : ""}${s.ms ?? 0} ms${s.cost_usd != null ? `, ${usd(s.cost_usd)}${s.estimated ? " (estimated price)" : ""}` : ""}${s.ok === false ? `, failed${s.reason ? `: ${why(s.reason)}` : ""}` : ""}.${tried}${masked}${esc}`;
  }
  if (s.kind === "tool") {
    if (s.repeat) return `Tool ${s.tool}: asked again with the same question, not run again.`;
    const sql = s.sql ? ` Ran a ${s.sql.starts_with ?? "SQL"} statement${s.sql.tables?.length ? ` on ${s.sql.tables.join(", ")}` : ""}.` : "";
    return `Tool ${s.tool}: answer of ${s.result_chars ?? 0} characters, ${s.ms ?? 0} ms${s.refused ? `, refused${s.reason ? ` (${s.reason})` : ""}` : ""}.${sql}`;
  }
  if (s.kind === "rules") return `Answer worded by fixed rules, not the model${s.reason ? ` (${why(s.reason)})` : ""}.`;
  if (s.kind === "guard") {
    const what = (s.replaced ?? []).map((r) => `${FIGURE_KINDS[r.kind] ?? r.kind}${r.counts ? ` of ${r.counts}` : ""}`);
    return s.skipped ? `Number check: nothing to check, the run ended ${s.skipped === "error" ? "with an error" : s.skipped}.` : s.numbers_replaced ? `Number check: ${s.numbers_replaced} figure${s.numbers_replaced === 1 ? "" : "s"} the agent could not source ${s.numbers_replaced === 1 ? "was" : "were"} replaced${what.length ? ` (${what.join("; ")})` : ""}.` : "Number check: no invented figure.";
  }
  if (s.kind === "context") {
    const counts: Record<string, number> = {};
    for (const i of s.items ?? []) counts[i.kind] = (counts[i.kind] ?? 0) + 1;
    const parts = Object.entries(counts).map(([k, n]) => `${n} ${KINDS[k] ?? k}${n === 1 || k === "turns" ? "" : "s"}`);
    const named = (s.items ?? []).filter((i) => i.kind === "summary" && i.label).map((i) => i.label);
    return parts.length ? `Context used: ${parts.join(", ")}${named.length ? ` (${named.join("; ")})` : ""}.` : "Context used: nothing from memory.";
  }
  return `Step: ${s.kind}.`;
}
const NO_STEPS = "No steps were recorded for this run.";
type Total = { cost_usd: number | null; tokens: number };
export const totalLine = (t: Total) => `Total for this run: ${t.cost_usd != null ? `${usd(t.cost_usd)}, ` : ""}${t.tokens} tokens${t.cost_usd == null ? " (no price recorded)" : ""}.`;
function RunSteps({ traceId }: { traceId: string | null | undefined }) {
  const [data, setData] = useState<{ rows: Step[]; total: Total | null } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!traceId) return;
    apiGet<{ steps: { run_id: string | null; steps: Step[] }[]; total?: Total }>(`/api/v1/agent-runs/trace/${encodeURIComponent(traceId)}`)
      .then((d) => setData({ rows: (d.steps ?? []).flatMap((r) => r.steps ?? []), total: d.total ?? null }))
      .catch((e) => setError(e instanceof ApiError && e.message ? e.message : "The steps could not be loaded."));
  }, [traceId]);
  if (!traceId) return <p className="ds-muted">{NO_STEPS}</p>;
  if (error) return <p role="alert">{error}</p>;
  if (data === null) return <p className="ds-muted" role="status">Loading the steps.</p>;
  if (!data.rows.length) return <p className="ds-muted">{NO_STEPS}</p>;
  return <><ol aria-label="Steps of the run">{data.rows.map((s, i) => <li key={i}>{stepLine(s)}</li>)}</ol>{data.total ? <p>{totalLine(data.total)}</p> : null}</>;
}

// INT2: chat turns of the agents (loop traces), from GET /api/v1/agent-runs/loops.
export interface LoopTrace { trace_id: string; agent: string | null; at: string | null; steps: number; tokens: number; ms: number | null; outcome: string | null;
  cost_usd?: number | null; worded_by?: string; estimated?: boolean; runs?: number; person?: string | null; tool_calls?: number }
const PAGE = 20;
const OUTCOMES: Record<string, string> = { done: "answered", could_not_finish: "could not finish", error: "failed", refused: "refused" };

export function AgentRuns() {
  const [open, setOpen] = useState("");
  const [loops, setLoops] = useState<LoopTrace[]>([]);
  const [who, setWho] = useState("");
  const [more, setMore] = useState(false);
  // RC-10: filter the chat turns by agent and page through them; each line carries its cost
  const loadLoops = (agent: string, offset: number) =>
    apiGet<{ loops: LoopTrace[]; more?: boolean }>(`/api/v1/agent-runs/loops?limit=${PAGE}&offset=${offset}${agent ? `&agent=${encodeURIComponent(agent)}` : ""}`)
      .then((d) => { setLoops((old) => (offset ? [...old, ...(d.loops ?? [])] : d.loops ?? [])); setMore(Boolean(d.more)); })
      .catch(() => { if (!offset) setLoops([]); setMore(false); });
  useEffect(() => { void loadLoops(who, 0); }, [who]);
  const [day, setDay] = useState("");
  const [data, setData] = useState<{ by_agent_day: AgentDay[]; runs: AgentRun[] } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    setData(null); setError("");
    apiGet<{ by_agent_day: AgentDay[]; runs: AgentRun[] }>(`/api/v1/agent-runs${day ? `?day=${encodeURIComponent(day)}` : ""}`).then(setData)
      .catch((e) => setError(e instanceof ApiError && e.message ? e.message : "The agent runs could not be loaded. Please try again."));
  }, [day]);
  const failed = (data?.runs ?? []).filter((r) => r.status === "failed");
  return (
    <div>
      <p className="ds-muted">What each agent did, how often it failed, how many tools it used and what it cost. Cost shows "Not available yet" when no price was recorded.</p>
      <label>Day <input className="ds-input" type="date" aria-label="Day" value={day} onChange={(e) => setDay(e.target.value)} /></label>
      {error ? <p role="alert">{error}</p> : data === null ? <p className="ds-muted" role="status">Loading the agent runs.</p>
        : !data.by_agent_day.length ? <p className="ds-muted">No agent runs {day ? "on that day" : "yet"}.</p> : (<>
          <table style={{ width: "100%", textAlign: "left" }} aria-label="Runs by agent and day">
            <thead><tr><th>Agent</th><th>Day</th><th>Runs</th><th>Failed</th><th>Tool calls</th><th>Cost</th></tr></thead>
            <tbody>{data.by_agent_day.map((r) => <tr key={`${r.agent_type}:${r.day}`}>
              <td>{AGENTS[r.agent_type] ?? r.agent_type}</td><td>{dayLabel(r.day)}</td><td>{r.runs}</td><td>{r.failures}</td><td>{r.tool_calls}</td><td>{cost(r.cost_usd)}</td></tr>)}</tbody>
          </table>
          <h2 style={{ fontSize: 16 }}>Failed runs</h2>
          {failed.length ? <ul aria-label="Failed runs">{failed.map((r) => <li key={r.id}>{(AGENTS[r.agent_type] ?? r.agent_type).split(",")[0]} could not finish a run{when(r.started_at)}.
            {r.exception_id ? <>{" "}<Link className="ds-link" to={`/centre/action/cases/${r.exception_id}`}>Open the case</Link>.</> : null}</li>)}</ul>
            : <p className="ds-muted">No run failed.</p>}
          <h2 style={{ fontSize: 16 }}>Recent runs</h2>
          <ul aria-label="Recent runs">{data.runs.slice(0, 20).map((r) => <li key={r.id}>{(AGENTS[r.agent_type] ?? r.agent_type).split(",")[0]}{when(r.started_at)}, {r.status}{r.cost_usd != null ? `, ${cost(r.cost_usd)}` : ""}.
            {" "}<button className="ds-link" aria-expanded={open === r.id} onClick={() => setOpen(open === r.id ? "" : r.id)}>{open === r.id ? "Hide steps" : "Show steps"}</button>
            {open === r.id ? <RunSteps traceId={r.trace_id} /> : null}</li>)}</ul>
        </>)}
      <h2 style={{ fontSize: 16 }}>Chat turns</h2>
      <label>Agent <select aria-label="Agent" value={who} onChange={(e) => setWho(e.target.value)}>
        <option value="">All agents</option>{Object.entries(AGENTS).map(([k, v]) => <option key={k} value={k}>{v.split(",")[0]}</option>)}</select></label>
      {loops.length ? <>
        <ul aria-label="Chat turns">{loops.map((l) => <li key={l.trace_id}>{l.agent ?? "Agent"}{l.person ? ` answering ${l.person}` : ""}{when(l.at)}, {OUTCOMES[l.outcome ?? ""] ?? l.outcome ?? "unknown"}{l.worded_by === "rules" ? " (worded by fixed rules)" : ""}: {l.steps} step{l.steps === 1 ? "" : "s"}, {l.tokens} tokens, {l.ms ?? 0} ms, {l.cost_usd != null ? `${usd(l.cost_usd)}${l.estimated ? " (estimated price)" : ""}` : "no price recorded"}.
          {" "}<button className="ds-link" aria-expanded={open === l.trace_id} onClick={() => setOpen(open === l.trace_id ? "" : l.trace_id)}>{open === l.trace_id ? "Hide steps" : "Show steps"}</button>
          {open === l.trace_id ? <RunSteps traceId={l.trace_id} /> : null}</li>)}</ul>
        {more ? <button className="ds-link" onClick={() => void loadLoops(who, loops.length)}>Show more chat turns</button> : null}</>
        : <p className="ds-muted">No chat turns {who ? "for this agent " : ""}yet.</p>}
    </div>
  );
}

// Settings > identifiers and Settings > instruments (GET /api/v1/instruments, e2c_routes): each instrument's other names and codes, and its class.
interface Ident { value: string; kind: string; source: string | null }
export interface Instrument { instrument_id: string; name: string; instrument_type: string | null; asset_class: string | null; currency: string | null; names: Ident[]; codes: Ident[]; contacts?: Ident[] }
const words = (v: string | null | undefined) => (v ? v.replace(/_/g, " ") : "");
function useInstruments() {
  const [data, setData] = useState<{ instruments: Instrument[]; asset_classes: string[] } | null>(null);
  const [error, setError] = useState("");
  const load = () => apiGet<{ instruments: Instrument[]; asset_classes: string[] }>("/api/v1/instruments").then(setData)
    .catch((e) => setError(e instanceof ApiError && e.message ? e.message : "The instruments could not be loaded. Please try again."));
  useEffect(() => { void load(); }, []);
  return { data, error, load };
}
const said = (xs: Ident[]) => xs.map((x) => `${x.value} (${x.kind}${x.source ? `, ${x.source}` : ""})`).join("; ");

export function Identifiers() {
  const { data, error, load } = useInstruments();
  const [said2, setSaid2] = useState("");
  const exact = async () => {  // UC5: names identical to an instrument's own name, approved by this person in one click
    try {
      const r = await apiSend<{ approved: string[]; left: number }>("POST", "/api/v1/evidence/aliases/approve-exact", {});
      setSaid2(r.approved.length ? `Approved ${r.approved.length} exact name${r.approved.length === 1 ? "" : "s"}.` + (r.left ? ` ${r.left} other match${r.left === 1 ? "" : "es"} still need a look in Evidence.` : "")
        : r.left ? `No exact names are waiting. ${r.left} other match${r.left === 1 ? "" : "es"} need a look in Evidence.` : "No matches are waiting.");
      await load();
    } catch (e) { setSaid2(e instanceof ApiError && e.message ? e.message : "That did not go through. Please try again."); }
  };
  if (error) return <p role="alert">{error}</p>;
  if (data === null) return <p className="ds-muted" role="status">Loading the identifiers.</p>;
  const known = data.instruments.filter((i) => i.names.length || i.codes.length || i.contacts?.length);
  const withContacts = data.instruments.some((i) => i.contacts !== undefined);  // AUC3-07: shown once the route sends the approved manager contacts
  return (
    <div>
      <p className="ds-muted">The other names and codes each source uses for an instrument. A file that uses any of them is read as that instrument. New matches wait in Evidence until a person approves them.</p>
      <p><button type="button" className="ds-button" onClick={() => void exact()}>Approve all exact name matches</button></p>
      {said2 ? <p role="status">{said2}</p> : null}
      {!known.length ? <p className="ds-muted">No other names or codes yet.</p> : (
        <table style={{ width: "100%", textAlign: "left" }} aria-label="Identifiers">
          <thead><tr><th>Instrument</th><th>Other names</th><th>Codes</th>{withContacts ? <th>Follow-ups go to</th> : null}</tr></thead>
          <tbody>{known.map((i) => <tr key={i.instrument_id}><td>{i.name}</td><td>{said(i.names) || "None"}</td><td>{said(i.codes) || "None"}</td>
            {withContacts ? <td>{said(i.contacts ?? []) || "Nobody named"}</td> : null}</tr>)}</tbody>
        </table>)}
    </div>
  );
}

export function Instruments() {
  const { data, error, load } = useInstruments();
  const [pick, setPick] = useState<Record<string, string>>({});
  const [note, setNote] = useState("");
  if (error) return <p role="alert">{error}</p>;
  if (data === null) return <p className="ds-muted" role="status">Loading the instruments.</p>;
  const give = async (i: Instrument) => {
    setNote("");
    try { await apiSend("POST", `/api/v1/instruments/${encodeURIComponent(i.instrument_id)}/asset-class`, { asset_class: pick[i.instrument_id] });
      setNote(`${i.name} is now ${words(pick[i.instrument_id])}. The next limits check counts it there.`); await load();
    } catch (e) { setNote(e instanceof ApiError && e.message ? e.message : "That did not go through. Please try again."); }
  };
  return (
    <div>
      <p className="ds-muted">Each instrument and its asset class. An instrument without a class is counted in no class and the limits check asks about it; give it one here.</p>
      {note ? <p role="status">{note}</p> : null}
      {!data.instruments.length ? <p className="ds-muted">No instruments yet.</p> : (
        <table style={{ width: "100%", textAlign: "left" }} aria-label="Instruments">
          <thead><tr><th>Instrument</th><th>Kind</th><th>Asset class</th></tr></thead>
          <tbody>{data.instruments.map((i) => <tr key={i.instrument_id}><td>{i.name}</td><td>{words(i.instrument_type)}</td>
            <td>{i.asset_class ? words(i.asset_class) : <>Needs a class{" "}
              <select aria-label={`Asset class for ${i.name}`} value={pick[i.instrument_id] ?? ""} onChange={(e) => setPick({ ...pick, [i.instrument_id]: e.target.value })}>
                <option value="">Choose</option>{data.asset_classes.map((c) => <option key={c} value={c}>{words(c)}</option>)}</select>{" "}
              <button className="ds-link" disabled={!pick[i.instrument_id]} onClick={() => void give(i)}>Save</button></>}</td></tr>)}</tbody>
        </table>)}
    </div>
  );
}

// Billing message: the latest call to a model provider ended out of credit (or key refused, model unknown), provider named. Admin only.
export interface Trouble { code: string; providers: string[]; words: string; at?: string | null }
export function ModelTrouble() {
  const [t, setT] = useState<Trouble | null>(null);
  useEffect(() => { apiGet<{ trouble: Trouble | null }>("/api/v1/agent-runs/model-trouble").then((d) => setT(d.trouble ?? null)).catch(() => setT(null)); }, []);
  if (!t) return null;
  return <p role="alert" className="state state-error">{t.words}</p>;
}

// S1: Settings, behind the person's name. Which items a person sees comes from settingsFor in shell/roles.ts (ROLE1): everyone has their own three
// (memory, Testing or Real use, Activity trail); the head of data, the data engineer and the administrator add theirs; the approver also reads Rules (P15).
const SECTIONS: { key: string; label: string; page: ReactNode }[] = [
  { key: "memory", label: "What the agents remember about you", page: <MemoryPage /> },
  { key: "mode", label: "Testing or Real use", page: <div><p>{MODE_WORDS}</p><p>Real use sends the minimum needed to the model, with names replaced.</p><ModeSwitch /></div> },
  { key: "register", label: "Activity trail", page: <RegisterPage /> },
  { key: "teach", label: "Teach the agents", page: <KnowledgePage /> }, // TEACH1: each person sees only the agents they may teach
  { key: "people", label: "People and access", page: <>
    <p className="ds-muted">Who can open which centre. The administrator sees everything.</p>
    <PeopleRoles />
    <AccessPage /></> },
  { key: "rules", label: "Rules", page: <AdminRules /> },
  { key: "identifiers", label: "Identifiers and other names", page: <Identifiers /> },
  { key: "instruments", label: "Instruments and asset classes", page: <Instruments /> },
  { key: "model", label: "Sources and data model", page: <AdminModel /> },
  { key: "templates", label: "Templates and skills", page: <AdminAgents /> },
  { key: "intent", label: "Intent admin", page: <p><Link className="ds-link" to="/centre/intent/admin">Open Intent admin</Link>: all intents, counters, defaults, areas and people.</p> },
  { key: "delivery", label: "Delivery channels", page: <p><Link className="ds-link" to="/centre/build/delivery-settings">Set up Slack, Teams and email</Link>: the secret names and hosts that approved dashboards are sent through.</p> },
  { key: "cycle", label: "Cycle date", page: <CycleDateSetting /> },
  { key: "connectors", label: "Connectors", page: <ConnectorsPage /> },
  { key: "mcp", label: "Outside assistants", page: <McpTokens /> },
  { key: "demo", label: "Demo", page: <p><Link className="ds-link" to="/centre/demo/painpoints">Pain-point demo</Link>: walk a customer's pain points and show where each is covered.</p> },
  { key: "jobs-events", label: "Jobs and events", page: <p><Link className="ds-link" to="/centre/settings/jobs">Open Jobs and events</Link>: the mode, failed jobs to send again, recent jobs and the latest events.</p> },
  { key: "runs", label: "Agent runs and cost", page: <AgentRuns /> },
];

export default function SettingsPage() {
  const { section } = useParams();
  const { user } = useSession();
  const roles = user?.roles ?? [];
  const allowed = settingsFor(roles);
  const mine = SECTIONS.filter((s) => allowed.has(s.key));
  const current = section ? SECTIONS.find((s) => s.key === section) : mine[0];
  if (!user) return <p className="ds-muted" role="status">Loading.</p>; // never refuse before the roles are known
  if (!current || !mine.includes(current)) return <Navigate to={landingFor(roles)} replace state={{ refused: true }} />;
  return (
    <div className="st-grid">
      <style>{".st-grid{display:grid;grid-template-columns:minmax(180px,240px) 1fr;gap:24px}@media (max-width:720px){.st-grid{grid-template-columns:1fr}}"}</style>
      <nav aria-label="Settings" style={{ display: "grid", gap: 8, alignContent: "start" }}>
        <h1 style={{ fontSize: 18 }}>Settings</h1>
        {mine.map((s) => <NavLink key={s.key} to={`/centre/settings/${s.key}`}>{s.label}</NavLink>)}
      </nav>
      <section aria-label={current.label}>{roles.includes("company_admin") ? <ModelTrouble /> : null}{current.page}</section>
    </div>
  );
}
