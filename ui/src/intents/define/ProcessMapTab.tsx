import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { ApiError, apiGet, apiSend } from "../../api/client";
import ScreenState from "../../components/ScreenState";
import { Button, Chip, Pill } from "../../design";
import { pm } from "./ProcessMapCopy";

// The Process map tab of Define (spec 27): list, process card, questions. Mounted by the Define view at ?tab=process-map.

interface Cell<T = unknown> { value: T | null; mark: "stated" | "guessed" | "unknown"; by: string; at: string; from: string; agent?: string; quote?: string; ref?: { kind: string; id: string } }
interface Step { id: string; order: number; name: Cell<string>; actor: Cell<string>; systems: Cell<string[]>; inputs: Cell<string[]>; outputs: Cell<string[]>; produces: string[]; uses: string[]; sources: string[] }
interface Break { id: string; card_id: string | null; sealed_card: boolean; text: Cell<string>; hidden?: string }
interface Proc {
  id: string; cluster: string; name: Cell<string>; owner: Cell<string>; trigger: Cell<string>; frequency: Cell<string>;
  inputs: Cell<string[]>; outputs: Cell<string[]>; systems: Cell<string[]>; steps: Step[]; breaks: Break[];
  status: "guessed" | "edited" | "confirmed" | "removed"; confirmed: { by: string; at: string } | null;
  history: { by: string; at: string; kind: string; field: string | null }[];
}
interface Question { id: string; process_id: string; topic: string; to_person: string; text: string; state: string }
interface Counters { processes: number; confirmed: number; guessed: number; edited: number; steps: number; steps_unknown: number; questions_open: number; questions_queued: number; without_owner: number; breaks_on_cards: number; breaks_own_words: number; measures_linked: number; sources_linked: number; state: string }
interface MapData {
  version: number; state: string; tier: string; summary?: string;
  drafted_at: string | null; drafted_from: { cards: number; interviews: number; documents: number };
  processes: Proc[]; questions: Question[]; clusters: { id: string; name: string; cards: number }[];
  people: Record<string, { name: string; role: string | null }>; systems: Record<string, string>; counters: Counters;
  me: { person: string; name: string; can_edit: boolean; can_draft: boolean; cards: Record<string, string>; owns: string[] };
  link_options: { measures: Option[] | null; sources: Option[] | null };
  draft_blocked: string | null;
}

const val = <T,>(c: Cell<T>): T | null => (c.mark === "unknown" ? null : c.value);
const day = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
const first = (name: string) => name.split(" ")[0] ?? name;

/** The source line; a click shows the passage it came from (spec 27, provenance). */
function Prov({ c }: { c: Cell }) {
  const [shown, setShown] = useState(false);
  if (c.mark === "unknown") return <p className="pmt-prov">{provenance(c)}</p>;
  return (
    <div>
      <button type="button" className="pmt-prov pmt-pop" aria-expanded={shown} onClick={() => setShown(!shown)}>{provenance(c)}</button>
      {shown && <p role="note" className="pmt-note pmt-popbox">{c.quote ? `"${c.quote}"` : pm.noPassage}</p>}
    </div>
  );
}

function SystemChip({ name, steps }: { name: string; steps: number }) {
  const [shown, setShown] = useState(false);
  return (
    <span>
      <button type="button" className="pmt-sys pmt-pop" aria-expanded={shown} onClick={() => setShown(!shown)}>{name}</button>
      {shown && <span role="note" className="pmt-note pmt-popbox">{pm.systemNote(name, steps)}</span>}
    </span>
  );
}

function provenance(c: Cell): string {
  if (c.mark === "unknown") return "Not known yet";
  if (c.mark === "guessed") return `Guessed by ${c.agent === "lens" ? "Lens" : c.by} from ${c.from}`;
  return `${c.from}, ${day(c.at)}`;
}

const CSS = `
.pmt { display: grid; grid-template-columns: 240px minmax(0,1fr) 320px; gap: 20px; align-items: start; }
.pmt-rail, .pmt-aside, .pmt-main { display: flex; flex-direction: column; gap: 12px; min-width: 0; }
.pmt-selects { display: none; gap: 8px; flex-wrap: wrap; }
.pmt-selects label { flex: 1 1 140px; }
.pmt-selects select { min-height: 44px; width: 100%; background: var(--ds-surface); color: var(--ds-ink); border: 1px solid var(--ds-line-2); border-radius: 8px; padding: 0 10px; }
.pmt-head { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; justify-content: space-between; }
.pmt-card { padding: 14px 16px; display: flex; flex-direction: column; gap: 8px; cursor: pointer; text-align: left; width: 100%; font: inherit; }
.pmt-card h3 { margin: 0; font-size: 16px; }
.pmt-row { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.pmt-strip { display: flex; gap: 6px; align-items: center; overflow-x: auto; padding-bottom: 4px; }
.pmt-step { flex: none; border: 1px solid var(--ds-line-2); border-radius: 999px; padding: 4px 12px; font-size: 13px; background: var(--ds-ground); color: var(--ds-ink); }
.pmt-step--guess { border-style: dashed; }
.pmt-arrow { flex: none; color: var(--ds-ink-muted); }
.pmt-sys { font-size: 12px; border: 1px solid var(--ds-line); border-radius: 6px; padding: 2px 8px; color: var(--ds-ink-soft); }
.pmt-dashed { border: 1px dashed var(--ds-ink-muted); border-radius: 999px; padding: 2px 10px; font-size: 12px; color: var(--ds-ink-muted); }
.pmt-sheet { position: fixed; top: 0; right: 0; bottom: 0; width: 640px; max-width: 100%; overflow: auto; z-index: 50; background: var(--ds-ground); border-left: 1px solid var(--ds-line-2); padding: 20px; display: flex; flex-direction: column; gap: 14px; box-sizing: border-box; }
.pmt-cols { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.pmt-field { display: flex; flex-direction: column; gap: 4px; }
.pmt-field label, .pmt-h { font-size: 12px; letter-spacing: 1px; text-transform: uppercase; color: var(--ds-ink-muted); margin: 0; }
.pmt-prov { font-size: 12px; color: var(--ds-ink-muted); margin: 0; }
.pmt input[type=text], .pmt textarea, .pmt select, .pmt-sheet input[type=text], .pmt-sheet textarea, .pmt-sheet select { min-height: 40px; background: var(--ds-surface); color: var(--ds-ink); border: 1px solid var(--ds-line-2); border-radius: 8px; padding: 6px 10px; font: inherit; box-sizing: border-box; max-width: 100%; }
.pmt-line { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.pmt-pop { background: none; border: 0; padding: 0; min-height: 24px; cursor: pointer; text-align: left; font: inherit; text-decoration: underline dotted; }
.pmt-sys.pmt-pop { border: 1px solid var(--ds-line); padding: 2px 8px; text-decoration: none; }
.pmt-popbox { display: block; margin-top: 4px; padding: 8px 10px; border: 1px solid var(--ds-line-2); border-radius: 8px; background: var(--ds-surface); }
.pmt-warn { color: var(--ds-amber); }
.pmt-note { font-size: 13px; color: var(--ds-ink-soft); margin: 0; }
@media (max-width: 900px) {
  .pmt { grid-template-columns: minmax(0,1fr); }
  .pmt-rail-list { display: none; }
  .pmt-selects { display: flex; }
  .pmt-cols { grid-template-columns: 1fr; }
  .pmt-sheet { width: 100%; border-left: 0; padding: 16px; }
}
`;

async function send<T>(method: "POST" | "PATCH" | "DELETE", path: string, body: unknown): Promise<T> {
  // The shared client types POST, PUT and DELETE only; it passes the method through unchanged. Shared file needed: add "PATCH".
  return apiSend<T>(method as unknown as "POST", path, body);
}

export default function ProcessMapTab({ intentId, clusterId = null }: { intentId: string; clusterId?: string | null }) {
  const base = `/api/intents/${encodeURIComponent(intentId)}`;
  const [params, setParams] = useSearchParams();
  const [data, setData] = useState<MapData | null>(null);
  const [state, setState] = useState<"loading" | "error" | "refused" | "populated">("loading");
  const [busy, setBusy] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [cluster, setCluster] = useState(clusterId ?? "all");
  const [status, setStatus] = useState<string>("All");
  const openId = params.get("process");

  const load = useCallback(async () => {
    try {
      setData(await apiGet<MapData>(`${base}/processes`));
      setState("populated");
    } catch (e) {
      setState(e instanceof ApiError && (e.status === 403 || e.status === 404) ? "refused" : "error");
    }
  }, [base]);
  useEffect(() => { void load(); }, [load]);

  const act = useCallback(async (label: string, fn: () => Promise<unknown>) => {
    setBusy(label);
    setProblem(null);
    try {
      await fn();
      await load();
    } catch (e) {
      setProblem(e instanceof ApiError ? e.message : "That did not work. Please try again.");
    } finally {
      setBusy(null);
    }
  }, [load]);

  const open = (id: string | null) => {
    const next = new URLSearchParams(params);
    if (id) next.set("process", id); else next.delete("process");
    setParams(next, { replace: false });
  };

  return (
    <ScreenState state={state} message={state === "refused" ? "We could not find that." : undefined} onRetry={load}>
      {data && <style>{CSS}</style>}
      {data && data.tier === "counts" && <p className="n-muted">{data.summary}</p>}
      {data && data.tier !== "counts" && (
        <Body data={data} base={base} busy={busy} problem={problem} act={act} open={open} openId={openId}
              cluster={cluster} setCluster={setCluster} status={status} setStatus={setStatus} />
      )}
    </ScreenState>
  );
}

interface BodyProps {
  data: MapData; base: string; busy: string | null; problem: string | null; openId: string | null;
  act: (label: string, fn: () => Promise<unknown>) => Promise<void>; open: (id: string | null) => void;
  cluster: string; setCluster: (c: string) => void; status: string; setStatus: (s: string) => void;
}

function Body({ data, base, busy, problem, act, open, openId, cluster, setCluster, status, setStatus }: BodyProps) {
  const procs = data.processes.filter((p) => p.status !== "removed");
  const asked = (p: Proc) => data.questions.filter((q) => q.process_id === p.id && (q.state === "open" || q.state === "queued"));
  const shown = procs.filter((p) => (cluster === "all" || p.cluster === cluster)
    && (status === "All" || (status === "Guessed" && p.status === "guessed") || (status === "Confirmed" && p.status === "confirmed")
      || (status === "Has open question" && asked(p).length > 0)));
  const count = (s: string) => procs.filter((p) => s === "All" || (s === "Guessed" && p.status === "guessed") || (s === "Confirmed" && p.status === "confirmed") || (s === "Has open question" && asked(p).length > 0)).length;
  const draftedAny = data.drafted_at !== null;
  const draft = () => act("draft", () => send("POST", `${base}/processes/draft`, { version: data.version }));
  const add = () => {
    const name = window.prompt(pm.nameIt);
    if (name && name.trim()) void act("add", () => send("POST", `${base}/processes`, { version: data.version, name: name.trim(), cluster: cluster === "all" ? null : cluster }));
  };
  const selected = procs.find((p) => p.id === openId) ?? null;
  const owner = (p: Proc) => { const o = val(p.owner); return o ? data.people[o]?.name ?? o : null; };
  const name = (id: string) => data.people[id]?.name ?? id;
  const open_q = data.questions.filter((q) => q.state === "open");
  const waitingBy = new Map<string, number>();
  data.questions.filter((q) => q.state === "queued").forEach((q) => waitingBy.set(q.to_person, (waitingBy.get(q.to_person) ?? 0) + 1));
  const c = data.counters;

  return (
    <div className="pmt">
      <nav className="pmt-rail" aria-label="Filters">
        <div className="pmt-selects">
          <label className="pmt-field"><span className="pmt-h">{pm.clusterLabel}</span>
            <select aria-label={pm.clusterLabel} value={cluster} onChange={(e) => setCluster(e.target.value)}>
              <option value="all">{pm.allClusters}</option>
              {data.clusters.map((k) => <option key={k.id} value={k.id}>{k.name}</option>)}
            </select></label>
          <label className="pmt-field"><span className="pmt-h">{pm.statusLabel}</span>
            <select aria-label={pm.statusLabel} value={status} onChange={(e) => setStatus(e.target.value)}>
              {pm.statuses.map((s) => <option key={s} value={s}>{s}</option>)}
            </select></label>
        </div>
        <div className="pmt-rail-list pmt-field">
          <p className="pmt-h">{pm.clusterLabel}</p>
          {data.clusters.length === 0 && <p className="pmt-note">{pm.noClusters}</p>}
          <div className="pmt-row" style={{ flexDirection: "column", alignItems: "stretch" }}>
            {data.clusters.length > 0 && <Chip tone={cluster === "all" ? "active" : "default"} onClick={() => setCluster("all")}>{pm.allClusters} ({procs.length})</Chip>}
            {data.clusters.map((k) => (
              <Chip key={k.id} tone={cluster === k.id ? "active" : "default"} onClick={() => setCluster(k.id)}>{k.name} ({procs.filter((p) => p.cluster === k.id).length})</Chip>
            ))}
          </div>
          <p className="pmt-h" style={{ marginTop: 12 }}>{pm.statusLabel}</p>
          <div className="pmt-row">
            {pm.statuses.map((s) => <span key={s} style={{ opacity: count(s) === 0 ? 0.5 : 1 }}><Chip tone={status === s ? "active" : "default"} onClick={() => setStatus(s)}>{s} ({count(s)})</Chip></span>)}
          </div>
        </div>
      </nav>

      <div className="pmt-main">
        <div className="pmt-head">
          <div>
            <h2 style={{ margin: 0 }}>{pm.title}</h2>
            <p className="pmt-note">
              {draftedAny
                ? `${pm.draftedFrom(data.drafted_from.cards, data.drafted_from.interviews, data.drafted_from.documents)}, ${day(data.drafted_at as string)}`
                : pm.noDraftYet}
            </p>
          </div>
          <div className="pmt-row">
            {data.me.can_draft && (
              <Button variant="primary" onClick={draft} disabled={busy !== null || data.draft_blocked !== null} title={data.draft_blocked ?? undefined}>
                {busy === "draft" ? pm.lensReading : pm.askLens}
              </Button>
            )}
            {data.me.can_edit && <Button onClick={add} disabled={busy !== null}>{pm.addProcess}</Button>}
          </div>
        </div>
        {data.draft_blocked && data.me.can_draft && <p className="pmt-note pmt-warn">{data.draft_blocked}</p>}
        {problem && <p role="alert" className="pmt-warn">{problem}</p>}

        {shown.length === 0 && <p className="ds-card" style={{ padding: 16, margin: 0 }}>{pm.noDraftYet}</p>}
        {data.clusters.concat(data.clusters.length ? [] : [{ id: "unsorted", name: "", cards: 0 }]).filter((k) => shown.some((p) => p.cluster === k.id)).map((k) => (
          <section key={k.id} className="pmt-main" aria-label={k.name || "Processes"}>
            {k.name && <h3 className="pmt-h">{k.name}</h3>}
            {shown.filter((p) => p.cluster === k.id).map((p) => (
              <button key={p.id} type="button" className="ds-card pmt-card" onClick={() => open(p.id)} aria-label={`Open ${val(p.name)}`}>
                <div className="pmt-row" style={{ justifyContent: "space-between" }}>
                  <h3>{val(p.name) ?? pm.nameIt}</h3>
                  <StatusChip p={p} />
                </div>
                <div className="pmt-row">
                  {owner(p) ? <Chip>{owner(p)}</Chip> : <span className="pmt-dashed">{pm.noOwner}</span>}
                  <span className="pmt-note">{val(p.frequency) ?? pm.freqUnknown}</span>
                  <span className="pmt-note">{val(p.trigger) ?? ""}</span>
                </div>
                <Strip p={p} />
                <div className="pmt-row">
                  {(val(p.systems) ?? []).length === 0 ? <span className="pmt-note">{pm.noSystems}</span>
                    : (val(p.systems) ?? []).map((s) => <span key={s} className="pmt-sys">{data.systems[s] ?? s}</span>)}
                </div>
                <div className="pmt-row">
                  <span className="pmt-note">{pm.breaksToday(p.breaks.length)}</span>
                  {asked(p).length > 0 && <Chip>{pm.question(asked(p).length, first(name(asked(p)[0]?.to_person ?? "")))}</Chip>}
                </div>
              </button>
            ))}
          </section>
        ))}
      </div>

      <aside className="pmt-aside" aria-label="Lens">
        <details open={typeof window === "undefined" || window.innerWidth > 900} className="ds-card" style={{ padding: 14 }}>
          <summary style={{ cursor: "pointer", minHeight: 24 }}>{pm.lensStrip(c.guessed, open_q.length + c.questions_queued)}</summary>
          <p className="pmt-h" style={{ marginTop: 10 }}>{pm.needs}</p>
          {open_q.length === 0 ? <p className="pmt-note">{pm.nothingWaiting}</p> : (
            <ul style={{ listStyle: "none", padding: 0, margin: "6px 0", display: "flex", flexDirection: "column", gap: 6, fontSize: 13 }}>
              {[...open_q].sort((a) => (a.to_person === data.me.person ? -1 : 1)).map((q) => (
                <li key={q.id}><button type="button" className="ds-link" style={{ background: "none", border: 0, padding: 0, font: "inherit", cursor: "pointer", textAlign: "left" }} onClick={() => open(q.process_id)}>
                  {first(name(q.to_person))}: {q.text}</button></li>
              ))}
            </ul>
          )}
          {[...waitingBy].map(([who, n]) => <p key={who} className="pmt-note">{pm.waiting(n, first(name(who)))}</p>)}
        </details>
        <div className="ds-card" style={{ padding: 14 }}>
          <p className="pmt-h">{pm.counters}</p>
          <ul style={{ listStyle: "none", padding: 0, margin: "8px 0 0", display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
            <li>Processes mapped: {c.processes}</li>
            <li>Confirmed by owner: {c.confirmed}</li>
            <li>Still guessed: {c.guessed}</li>
            <li>Edited since draft: {c.edited}</li>
            <li>Steps in total: {c.steps}; unknown: {c.steps_unknown}</li>
            <li>Open questions: {c.questions_open}; queued: {c.questions_queued}</li>
            <li>Processes without an owner: {c.without_owner}</li>
            <li>Breaks on a wall card: {c.breaks_on_cards}; in the owner's words: {c.breaks_own_words}</li>
            <li>Measures linked: {c.measures_linked > 0 ? c.measures_linked : pm.measuresNote}</li>
            <li>Data sources linked: {c.sources_linked > 0 ? c.sources_linked : "0, none linked yet"}</li>
          </ul>
        </div>
      </aside>

      {selected && <Sheet p={selected} data={data} base={base} act={act} busy={busy} problem={problem} close={() => open(null)} />}
    </div>
  );
}

function StatusChip({ p }: { p: Proc }) {
  if (p.status === "confirmed" && p.confirmed) return <Pill tone="ok">{`Confirmed by ${first(p.confirmed.by)}`}</Pill>;
  return <Pill tone={p.status === "edited" ? "open" : "draft"}>{p.status === "edited" ? "Edited" : "Guessed"}</Pill>;
}

function Strip({ p }: { p: Proc }) {
  if (p.steps.length === 0) return <div className="pmt-row"><span className="pmt-dashed" aria-label={pm.stepUnknown}>?</span><p className="pmt-note">{pm.noSteps}</p></div>;
  return (
    <div className="pmt-strip" aria-label="Steps">
      {p.steps.map((s, i) => (
        <span key={s.id} className="pmt-row" style={{ flex: "none", flexWrap: "nowrap" }}>
          {i > 0 && <span className="pmt-arrow" aria-hidden="true">{"→"}</span>}
          <span className={`pmt-step${s.name.mark === "guessed" ? " pmt-step--guess" : ""}`}>{i + 1}. {val(s.name)}</span>
        </span>
      ))}
    </div>
  );
}

interface SheetProps { p: Proc; data: MapData; base: string; busy: string | null; problem: string | null; close: () => void; act: BodyProps["act"] }

function Sheet({ p, data, base, act, busy, problem, close }: SheetProps) {
  const url = `${base}/processes/${p.id}`;
  const v = data.version;
  const edit = data.me.can_edit;
  const iOwn = data.me.owns.includes(p.id);
  const ownerId = val(p.owner);
  const ownerName = ownerId ? data.people[ownerId]?.name ?? ownerId : null;
  const patch = (change: Record<string, unknown>) => act("edit", () => send("PATCH", url, { version: v, change }));
  const setField = (field: string, value: unknown) => patch({ op: "set", field, value });
  const mine = data.questions.filter((q) => q.process_id === p.id);
  const live = mine.find((q) => q.topic === "trigger" && q.state !== "dropped");
  const asked = live !== undefined;
  const askedName = live ? data.people[live.to_person]?.name ?? "the owner" : "";
  const [draftName, setDraftName] = useState(val(p.name) ?? "");
  const [stepName, setStepName] = useState("");
  const [words, setWords] = useState("");
  const [answers, setAnswers] = useState<Record<string, string>>({});

  return (
    <div className="pmt-sheet" role="dialog" aria-label={val(p.name) ?? pm.nameIt}>
      <div className="pmt-line" style={{ justifyContent: "space-between" }}>
        <StatusChip p={p} />
        <Button onClick={close}>{pm.close}</Button>
      </div>
      {problem && <p role="alert" className="pmt-warn">{problem}</p>}

      <div className="pmt-field">
        <label htmlFor="pm-name">Name</label>
        {edit ? (
          <div className="pmt-line">
            <input id="pm-name" type="text" value={draftName} placeholder={pm.nameIt} onChange={(e) => setDraftName(e.target.value)} />
            <Button disabled={busy !== null || !draftName.trim() || draftName === val(p.name)} onClick={() => setField("name", draftName)}>{pm.save}</Button>
          </div>
        ) : <strong>{val(p.name) ?? pm.nameIt}</strong>}
        <Prov c={p.name} />
      </div>

      <div className="pmt-field">
        <label htmlFor="pm-owner">Owner</label>
        {edit ? (
          <select id="pm-owner" value={ownerId ?? ""} onChange={(e) => setField("owner", e.target.value)}>
            <option value="">{pm.noOwner}</option>
            {Object.entries(data.people).map(([id, x]) => <option key={id} value={id}>{x.name}</option>)}
          </select>
        ) : <span>{ownerName ?? pm.noOwner}</span>}
        <Prov c={p.owner} />
      </div>

      <div>
        <p className="pmt-h">{pm.steps}</p>
        <Strip p={p} />
        <ol style={{ paddingLeft: 20, margin: "8px 0", display: "flex", flexDirection: "column", gap: 6 }}>
          {p.steps.map((s, i) => (
            <li key={s.id}>
              <div className="pmt-line">
                <span>{val(s.name)}</span>
                <span className="pmt-note">{val(s.actor) ?? ""}</span>
                {edit && (<>
                  <Button disabled={i === 0} aria-label={`Move step ${i + 1} up`} onClick={() => patch({ op: "reorder", order: swap(p.steps.map((x) => x.id), i, i - 1) })}>Up</Button>
                  <Button disabled={i === p.steps.length - 1} aria-label={`Move step ${i + 1} down`} onClick={() => patch({ op: "reorder", order: swap(p.steps.map((x) => x.id), i, i + 1) })}>Down</Button>
                  <Button aria-label={`Remove step ${i + 1}`} onClick={() => patch({ op: "remove_step", step_id: s.id })}>Remove step</Button>
                </>)}
              </div>
              <Prov c={s.name} />
            </li>
          ))}
        </ol>
        {edit && (
          <div className="pmt-line">
            <input type="text" aria-label="Step name" value={stepName} placeholder="Short name of the step" onChange={(e) => setStepName(e.target.value)} />
            <Button disabled={!stepName.trim() || busy !== null} onClick={() => { patch({ op: "add_step", name: stepName }); setStepName(""); }}>{pm.addStep}</Button>
          </div>
        )}
        {edit && p.steps.length >= 2 && (
          <div className="pmt-line" style={{ marginTop: 8 }}>
            <select aria-label={pm.splitAfter} defaultValue="" onChange={(e) => e.target.value && patch({ op: "split", after_step: e.target.value })}>
              <option value="">{pm.split}</option>
              {p.steps.slice(0, -1).map((s, i) => <option key={s.id} value={s.id}>{`Split after step ${i + 1}`}</option>)}
            </select>
          </div>
        )}
        {edit && (
          <div className="pmt-line" style={{ marginTop: 8 }}>
            <select aria-label={pm.merge} defaultValue="" disabled={data.processes.filter((x) => x.cluster === p.cluster && x.status !== "removed").length < 2}
                    onChange={(e) => e.target.value && patch({ op: "merge", with: e.target.value })}>
              <option value="">{pm.merge}</option>
              {data.processes.filter((x) => x.id !== p.id && x.cluster === p.cluster && x.status !== "removed").map((x) => <option key={x.id} value={x.id}>{val(x.name)}</option>)}
            </select>
          </div>
        )}
      </div>

      <div className="pmt-cols">
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div className="pmt-field">
            <label htmlFor="pm-trigger">{pm.trigger}</label>
            {edit ? <TextSave id="pm-trigger" value={val(p.trigger) ?? ""} onSave={(t) => setField("trigger", t)} busy={busy !== null} /> : <span>{val(p.trigger) ?? ""}</span>}
            {val(p.trigger) === null && (
              <div className="pmt-line">
                <p className="pmt-note">{pm.triggerUnknown(ownerName ?? "")}{asked ? ` Lens has asked ${first(askedName)}.` : "."}</p>
                {edit && ownerName && !asked && <Button disabled={busy !== null} onClick={() => patch({ op: "ask", topic: "trigger" })}>{pm.askOwner(first(ownerName))}</Button>}
              </div>
            )}
            <Prov c={p.trigger} />
          </div>
          <div className="pmt-field">
            <label htmlFor="pm-freq">{pm.frequency}</label>
            {edit ? <TextSave id="pm-freq" value={val(p.frequency) ?? ""} onSave={(t) => setField("frequency", t)} busy={busy !== null} /> : <span>{val(p.frequency) ?? pm.freqUnknown}</span>}
            {edit && <div className="pmt-row">{pm.quick.map((q) => <Chip key={q} onClick={() => setField("frequency", q)}>{q}</Chip>)}</div>}
            {val(p.frequency) === null && <p className="pmt-note">{pm.freqUnknown}</p>}
            <Prov c={p.frequency} />
          </div>
          <div className="pmt-field">
            <span className="pmt-h">{pm.systems}</span>
            <div className="pmt-row">
              {(val(p.systems) ?? []).length === 0 ? <span className="pmt-note">{pm.noSystems}</span>
                : (val(p.systems) ?? []).map((sid) => <SystemChip key={sid} name={data.systems[sid] ?? sid} steps={p.steps.filter((x) => (val(x.systems) ?? []).includes(sid)).length} />)}
            </div>
            <Prov c={p.systems} />
          </div>
          <ChipList label={pm.inputs} cell={p.inputs} edit={edit} onSet={(l) => setField("inputs", l)} />
          <ChipList label={pm.outputs} cell={p.outputs} edit={edit} onSet={(l) => setField("outputs", l)} />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div>
            <p className="pmt-h">{pm.breaks}</p>
            {p.breaks.length === 0 && <p className="pmt-note">{pm.noBreak(0)}</p>}
            <ul style={{ paddingLeft: 18, margin: "6px 0" }}>
              {p.breaks.map((b) => (
                <li key={b.id}>{b.hidden ?? val(b.text)}
                  {b.hidden ? <p className="pmt-prov">A sealed card</p> : <Prov c={b.text} />}
                  {edit && <Button aria-label="Remove this line" onClick={() => patch({ op: "remove_break", break_id: b.id })}>Remove</Button>}</li>
              ))}
            </ul>
            {edit && (<>
              <select aria-label={pm.linkCard} defaultValue="" onChange={(e) => e.target.value && patch({ op: "add_break", card_id: e.target.value })}>
                <option value="">{pm.linkCard}</option>
                {Object.entries(data.me.cards).map(([id, t]) => <option key={id} value={id}>{t || id}</option>)}
              </select>
              <div className="pmt-line" style={{ marginTop: 6 }}>
                <input type="text" aria-label={pm.addWords} value={words} placeholder={pm.addWords} onChange={(e) => setWords(e.target.value)} />
                <Button disabled={!words.trim() || busy !== null} onClick={() => { patch({ op: "add_break", text: words }); setWords(""); }}>{pm.addWords}</Button>
              </div>
            </>)}
          </div>
          <div>
            <p className="pmt-h">{pm.links}</p>
            <LinkPicker p={p} options={data.link_options ?? { measures: null, sources: null }} edit={edit} patch={patch} />
          </div>
        </div>
      </div>

      <div className="pmt-line">
        {iOwn ? (<>
          <Button variant="primary" disabled={busy !== null || p.status === "confirmed"} onClick={() => act("confirm", () => send("POST", `${url}/confirm`, { version: v }))}>{pm.confirm}</Button>
          <select aria-label={pm.notMine} defaultValue="" onChange={(e) => e.target.value && act("handover", () => send("POST", `${url}/handover`, { version: v, to_person: e.target.value }))}>
            <option value="">{pm.notMine}</option>
            {Object.entries(data.people).filter(([id]) => id !== data.me.person).map(([id, x]) => <option key={id} value={id}>{x.name}</option>)}
          </select>
        </>) : (
          <>
            <Button disabled>{pm.confirm}</Button>
            <span className="pmt-note">{ownerName ? pm.onlyOwner(first(ownerName)) : pm.noOwnerToConfirm}</span>
          </>
        )}
        {edit && <Button onClick={() => { const why = window.prompt(pm.removeWhy); if (why && why.trim()) void act("remove", () => send("DELETE", url, { version: v, reason: why.trim() })); }}>{pm.remove}</Button>}
      </div>

      <div>
        <p className="pmt-h">{pm.questions}</p>
        {mine.length === 0 && <p className="pmt-note">{pm.noQuestions}</p>}
        {mine.map((q) => {
          const mineQ = q.state === "open" && q.to_person === data.me.person;
          return (
            <div key={q.id} className="ds-card" style={{ padding: 10, marginTop: 6 }}>
              <p style={{ margin: 0 }}>{q.text}</p>
              <p className="pmt-prov">{`To ${data.people[q.to_person]?.name ?? q.to_person}. ${q.state === "queued" ? "Waiting its turn." : q.state === "open" ? "Waiting for an answer." : q.state === "answered" ? "Answered." : "Dropped."}`}</p>
              {mineQ && (
                <div className="pmt-line">
                  <textarea aria-label="Your answer" rows={2} value={answers[q.id] ?? ""} onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })} />
                  <Button variant="primary" disabled={!(answers[q.id] ?? "").trim() || busy !== null}
                          onClick={() => act("answer", () => send("POST", `${base}/process-questions/${q.id}/answer`, { version: v, answer: answers[q.id] }))}>{pm.send}</Button>
                  <Button onClick={() => { const why = window.prompt("Why can you not answer?"); if (why && why.trim()) void act("drop", () => send("POST", `${base}/process-questions/${q.id}/answer`, { version: v, dropped_reason: why.trim() })); }}>{pm.dontKnow}</Button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div>
        <p className="pmt-h">{pm.history}</p>
        {p.history.length === 0 ? <p className="pmt-note">{pm.noHistory}</p> : (
          <ul style={{ paddingLeft: 18, margin: "6px 0", fontSize: 13 }}>
            {[...p.history].reverse().map((h, i) => <li key={i}>{`${h.by}, ${day(h.at)}: ${h.kind.replace(/_/g, " ")}${h.field ? ` (${h.field})` : ""}`}</li>)}
          </ul>
        )}
      </div>
    </div>
  );
}

interface Option { id: string; label: string }

// Links (spec 27): measures from the intent's catalogue, data sources from its data sources list. A step holds ids; the screen shows names.
function LinkPicker({ p, options, edit, patch }: { p: Proc; options: MapData["link_options"]; edit: boolean; patch: (c: Record<string, unknown>) => void }) {
  const measures = options.measures, sources = options.sources;
  const [stepId, setStepId] = useState(p.steps[0]?.id ?? "");
  const [role, setRole] = useState<"produces" | "uses">("uses");
  const mName = (id: string) => measures?.find((m) => m.id === id)?.label ?? id;
  const sName = (id: string) => sources?.find((m) => m.id === id)?.label ?? id;
  const rows = p.steps.flatMap((s, i) => [
    ...s.produces.map((id) => ({ key: `p${s.id}${id}`, text: `${mName(id)}: produced at step ${i + 1}`, step: s.id, kind: "produces", id })),
    ...s.uses.map((id) => ({ key: `u${s.id}${id}`, text: `${mName(id)}: used at step ${i + 1}`, step: s.id, kind: "uses", id })),
    ...s.sources.map((id) => ({ key: `s${s.id}${id}`, text: `${sName(id)}: used at step ${i + 1}`, step: s.id, kind: "sources", id })),
  ]);
  const link = (kind: string, id: string) => stepId && id && patch({ op: "link", step_id: stepId, kind, id });
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {rows.length === 0 && <p className="pmt-note">{measures && measures.length ? pm.noMeasureYet(measures.length) : pm.noMeasure}</p>}
      <ul style={{ paddingLeft: 18, margin: 0 }}>
        {rows.map((r) => (
          <li key={r.key}>{r.text} {edit && <Button aria-label={`Remove link ${r.text}`} onClick={() => patch({ op: "link", step_id: r.step, kind: r.kind, id: r.id, remove: true })}>Remove</Button>}</li>
        ))}
      </ul>
      {edit && p.steps.length > 0 && (<>
        <div className="pmt-line">
          <select aria-label="Step to link" value={stepId} onChange={(e) => setStepId(e.target.value)}>
            {p.steps.map((s, i) => <option key={s.id} value={s.id}>{`Step ${i + 1}`}</option>)}
          </select>
          <select aria-label="Measure role" value={role} onChange={(e) => setRole(e.target.value as "produces" | "uses")}>
            <option value="uses">Used at this step</option>
            <option value="produces">Produced at this step</option>
          </select>
        </div>
        {measures && measures.length > 0 ? (
          <select aria-label={pm.linkMeasure} value="" onChange={(e) => link(role, e.target.value)}>
            <option value="">{pm.linkMeasure}</option>
            {measures.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
          </select>
        ) : <p className="pmt-note">{pm.noCatalogue}</p>}
        {sources && sources.length > 0 ? (
          <select aria-label={pm.linkSource} value="" onChange={(e) => link("sources", e.target.value)}>
            <option value="">{pm.linkSource}</option>
            {sources.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
          </select>
        ) : <p className="pmt-note">{pm.noSource}</p>}
      </>)}
    </div>
  );
}

function swap(ids: string[], a: number, b: number): string[] {
  const out = [...ids];
  const t = out[a] as string;
  out[a] = out[b] as string;
  out[b] = t;
  return out;
}

function TextSave({ id, value, onSave, busy }: { id: string; value: string; onSave: (t: string) => void; busy: boolean }) {
  const [t, setT] = useState(value);
  return (
    <div className="pmt-line">
      <input id={id} type="text" value={t} onChange={(e) => setT(e.target.value)} />
      <Button disabled={busy || t === value} onClick={() => onSave(t)}>{pm.save}</Button>
    </div>
  );
}

function ChipList({ label, cell, edit, onSet }: { label: string; cell: Cell<string[]>; edit: boolean; onSet: (l: string[]) => void }) {
  const list = val(cell) ?? [];
  const [t, setT] = useState("");
  return (
    <div className="pmt-field">
      <p className="pmt-h">{label}</p>
      <div className="pmt-row">
        {list.length === 0 && <span className="pmt-note">{pm.freqUnknown}</span>}
        {list.map((x) => <Chip key={x} onClick={edit ? () => onSet(list.filter((y) => y !== x)) : undefined}>{x}{edit ? " ×" : ""}</Chip>)}
      </div>
      {edit && (
        <div className="pmt-line">
          <input type="text" aria-label={`Add to ${label}`} value={t} onChange={(e) => setT(e.target.value)} />
          <Button disabled={!t.trim()} onClick={() => { onSet([...list, t.trim()]); setT(""); }}>Add</Button>
        </div>
      )}
      <Prov c={cell} />
    </div>
  );
}
