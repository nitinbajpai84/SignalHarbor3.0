import { useEffect, useState } from "react";

import { ApiError } from "../../api/client";
import Panel from "../../components/Panel";
import ScreenState from "../../components/ScreenState";
import StatusPill from "../../components/StatusPill";
import { useLoad } from "../../components/useLoad";
import {
  confirmField,
  decide,
  FIELDS,
  getGoverned,
  propose,
  redraftGoverned,
  withdraw,
  type Cell,
  type Field,
  type Governed,
  type GovernedRow,
} from "./catalogueApi";
import { governedCopy as g } from "./catalogueCopy";

type Draft = Record<string, string>;
const list = (v: unknown) => (Array.isArray(v) ? v.map(String) : []);
const rec = (v: unknown) => (v && typeof v === "object" ? (v as Record<string, unknown>) : {});
const words = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

/** What a cell says, in words. */
export function shown(field: Field, cell: Cell): string {
  if (cell.mark === "unknown" || cell.value == null) return g.notSet;
  const v = cell.value;
  if (field === "owners") {
    const o = rec(v);
    const out = [o.business && `${g.business}: ${o.business}`, o.data && `${g.data}: ${o.data}`].filter(Boolean);
    return out.length ? out.join(" · ") : g.notSet;
  }
  if (field === "classification") return g.classes[String(v) as keyof typeof g.classes] ?? String(v);
  if (field === "may_see") return list(v).length ? list(v).join(", ") : g.everyoneAccess;
  if (field === "resolving") {
    const r = rec(v);
    return [r.team, r.target_week ? `by week ${r.target_week}` : ""].filter(Boolean).join(", ") || g.notSet;
  }
  if (field === "affects") return list(v).length ? list(v).join(", ") : g.notSet;
  return String(v);
}

function start(field: Field, cell: Cell): Draft {
  const v = cell.mark === "unknown" ? null : cell.value;
  if (field === "owners") return { business: String(rec(v).business ?? ""), data: String(rec(v).data ?? "") };
  if (field === "resolving") return { team: String(rec(v).team ?? ""), week: rec(v).target_week ? String(rec(v).target_week) : "" };
  if (field === "may_see" || field === "affects") return { text: list(v).join(", ") };
  return { text: v == null ? (field === "classification" ? "open" : "") : String(v) };
}

function value(field: Field, d: Draft, cell: Cell): unknown {
  if (field === "owners") return { business: d.business?.trim() || null, data: d.data?.trim() || null, process: rec(cell.value).process ?? null };
  if (field === "resolving") return { team: d.team?.trim() || null, target_week: d.week?.trim() ? Number(d.week) : null };
  if (field === "may_see" || field === "affects") return words(d.text ?? "");
  return d.text;
}

function FieldEditor({ field, draft, onChange, slot }: { field: Field; draft: Draft; onChange: (d: Draft) => void; slot?: "business" | "data" | null }) {
  const set = (k: string) => (e: { target: { value: string } }) => onChange({ ...draft, [k]: e.target.value });
  const label = g.fields[field];
  if (field === "owners")
    return (
      <div className="n-flex wrap">
        {slot !== "data" ? <input className="n-input" aria-label={g.business} placeholder={g.business} value={draft.business ?? ""} onChange={set("business")} /> : null}
        {slot !== "business" ? <input className="n-input" aria-label={g.data} placeholder={g.data} value={draft.data ?? ""} onChange={set("data")} /> : null}
        <span className="n-muted">{g.source}</span>
      </div>
    );
  if (field === "classification")
    return (
      <select className="n-select" aria-label={label} value={draft.text} onChange={set("text")}>
        {Object.entries(g.classes).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
      </select>
    );
  if (field === "resolving")
    return (
      <div className="n-flex wrap">
        <input className="n-input" aria-label={g.team} placeholder={g.team} value={draft.team ?? ""} onChange={set("team")} />
        <input className="n-input" type="number" min={1} max={520} aria-label={g.week} placeholder={g.week} value={draft.week ?? ""} onChange={set("week")} />
      </div>
    );
  if (field === "review_date") return <input className="n-input" type="date" aria-label={label} value={draft.text ?? ""} onChange={set("text")} />;
  return (
    <div>
      <input className="n-input" aria-label={label} value={draft.text ?? ""} onChange={set("text")} />
      <span className="n-muted"> {g.listHelp}</span>
    </div>
  );
}

/** The ring on a cluster card: solid and "Governed" when all six are stated, otherwise what is still needed. For the Define cluster cards. */
export function GovernedRing({ row }: { row: GovernedRow | null }) {
  if (!row) return <span className="n-muted">{g.notAvailable}</span>;
  return row.complete ? <StatusPill tone="success">{g.governed}</StatusPill> : <StatusPill tone="warning">{g.needs(row.needs.slice(0, 2))}</StatusPill>;
}

function Row({ intent, baseline, m, field, reload, refusalLine, me, staff }: { intent: string; baseline: string; m: GovernedRow; field: Field; reload: () => void; refusalLine: string; me?: string | null; staff?: boolean }) {
  const cell = m.state[field];
  const [mode, setMode] = useState<"confirm" | "propose" | "decline" | null>(null);
  const [draft, setDraft] = useState<Draft>(start(field, cell));
  const [reason, setReason] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const [slot, setSlot] = useState<"business" | "data" | null>(null);
  const waiting = m.proposals[field];
  const noConfirm = field === "owners" ? !m.slots.business && !m.slots.data : !m.can_confirm[field];
  const mayPropose = !!staff || Object.values(m.can_confirm).some(Boolean) || m.slots.business || m.slots.data;
  const stated = cell.mark === "stated";
  const run = async (job: Promise<unknown>) => {
    setProblem(null);
    try {
      await job;
      setMode(null);
      setReason("");
      reload();
    } catch (e) {
      setProblem(e instanceof ApiError && e.message ? e.message : g.error);
    }
  };
  const open = (next: "confirm" | "propose", which: "business" | "data" | null = null) => {
    const d = start(field, cell);
    if (field === "owners") { d.business = d.business || m.owners.business || ""; d.data = d.data || m.owners.data || ""; }
    setDraft(d); setSlot(which); setReason(""); setProblem(null); setMode(next);
  };
  return (
    <li aria-label={g.fields[field]} style={{ display: "grid", gap: 6, borderBottom: "1px solid var(--border-hairline)", paddingBottom: 8 }}>
      <div className="n-flex wrap">
        <strong>{g.fields[field]}</strong>
        <StatusPill tone={stated ? "success" : cell.mark === "guessed" ? "warning" : "muted"}>
          {stated ? g.mark.stated(cell.by) : cell.mark === "guessed" ? g.mark.guessed(cell.from) : g.mark.unknown}
        </StatusPill>
      </div>
      <span>{shown(field, cell)}</span>
      {waiting ? (
        <div className="n-suggest-block">
          <div className="n-suggest-label">{g.waiting(waiting.by, g.fields[field].toLowerCase(), waiting.reason)}</div>
          <p>{shown(field, { ...cell, value: waiting.value, mark: "stated" })}</p>
          <div className="n-flex wrap">
            {m.can_confirm[field] ? (
              <>
                <button type="button" className="n-btn sm" onClick={() => void run(decide(intent, m.id, field, "apply"))}>{g.apply}</button>
                <button type="button" className="n-btn sm" onClick={() => { setProblem(null); setMode("decline"); }}>{g.decline}</button>
              </>
            ) : null}
            {me && waiting.by === me ? <button type="button" className="n-btn sm" onClick={() => void run(withdraw(intent, m.id, field))}>{g.withdraw}</button> : null}
          </div>
        </div>
      ) : null}
      {mode === "decline" ? (
        <div className="n-flex wrap">
          <input className="n-input" aria-label={g.declineReason} placeholder={g.declineReason} value={reason} onChange={(e) => setReason(e.target.value)} />
          <button type="button" className="n-btn sm primary" disabled={!reason.trim()} onClick={() => void run(decide(intent, m.id, field, "decline", reason))}>{g.decline}</button>
          <button type="button" className="n-btn sm" onClick={() => setMode(null)}>{g.cancel}</button>
        </div>
      ) : null}
      {mode === "confirm" || mode === "propose" ? (
        <div style={{ display: "grid", gap: 6 }} role="group" aria-label={mode === "propose" ? g.proposeTitle(m.name) : g.confirmButton[field]}>
          {mode === "propose" ? <p className="n-muted">{g.confirmedOn(cell.by, cell.at)}</p> : null}
          <FieldEditor field={field} draft={draft} onChange={setDraft} slot={mode === "confirm" ? slot : null} />
          {mode === "propose" ? <input className="n-input" aria-label={g.reason} placeholder={g.reason} value={reason} onChange={(e) => setReason(e.target.value)} /> : null}
          <div className="n-flex wrap">
            {mode === "confirm" ? (
              <button type="button" className="n-btn sm primary" onClick={() => void run(confirmField(baseline, m.id, field, value(field, draft, cell)))}>{g.save}</button>
            ) : (
              <button type="button" className="n-btn sm primary" disabled={!reason.trim()} onClick={() => void run(propose(intent, m.id, field, value(field, draft, cell), reason))}>{g.send}</button>
            )}
            <button type="button" className="n-btn sm" onClick={() => setMode(null)}>{g.cancel}</button>
          </div>
        </div>
      ) : null}
      {mode === null ? (
        <div className="n-flex wrap">
          {field === "owners" ? (
            (["business", "data"] as const).map((r) => (
              <button key={r} type="button" className="n-btn sm" disabled={!m.slots[r]} title={m.slots[r] ? undefined : refusalLine} onClick={() => open("confirm", r)}>
                {g.confirmSlot[r]}
              </button>
            ))
          ) : (
            <button type="button" className="n-btn sm" disabled={!m.can_confirm[field]} title={m.can_confirm[field] ? undefined : refusalLine} onClick={() => open("confirm")}>
              {g.confirmButton[field]}
            </button>
          )}
          {stated && !waiting ? <button type="button" className="n-btn sm" disabled={!mayPropose} title={mayPropose ? undefined : g.proposeOnly} onClick={() => open("propose")}>{g.proposeLink}</button> : null}
        </div>
      ) : null}
      {noConfirm ? <p role="status" className="n-muted">{refusalLine}</p> : stated && !waiting && !mayPropose ? <p role="status" className="n-muted">{g.proposeOnly}</p> : null}
      {problem ? <p role="alert" className="state state-error">{problem}</p> : null}
    </li>
  );
}

/** One measure's card: title, "n of 6" and six rows. */
export function GovernedCard({ intent, data, id, reload, me, onRedraft, note, staff }: { intent: string; data: Governed; id: string; reload: () => void; me?: string | null; onRedraft?: () => void; note?: string | null; staff?: boolean }) {
  const m = data.measures.find((x) => x.id === id);
  if (!m) return <p className="n-muted">{g.notAvailable}</p>;
  return (
    <Panel title={`${g.title}: ${m.name}`} actions={<StatusPill tone={m.complete ? "success" : "warning"}>{g.count(m.n)}</StatusPill>}>
      {m.n < 6 && (onRedraft || staff === false) ? <button type="button" className="n-btn sm" disabled={!onRedraft} title={onRedraft ? undefined : g.redraftOnly} onClick={onRedraft}>{g.redraft}</button> : null}
      {m.n < 6 && staff === false ? <p className="n-muted">{g.redraftOnly}</p> : null}
      {note ? <p role="status" className="n-muted">{note}</p> : null}
      <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 10 }}>
        {FIELDS.map((f) => <Row key={`${f}-${m.state[f].at}-${m.proposals[f]?.at ?? ""}`} intent={intent} baseline={data.baseline_id} m={m} field={f} reload={reload} refusalLine={data.refusal} me={me} staff={staff} />)}
      </ul>
    </Panel>
  );
}

/** The percentage strip: four bars, each `n of m measures` and a rounded percentage; a click names the field to filter by. */
export function GovernedStrip({ data, onFilter, active }: { data: Governed; onFilter?: (key: string | null) => void; active?: string | null }) {
  if (!data.strip) return <p className="n-muted">{data.empty ?? g.notAvailable}</p>;
  return (
    <div style={{ display: "grid", gap: 8 }}>
      {(Object.keys(g.strip) as (keyof typeof g.strip)[]).map((k) => {
        const s = data.strip![k];
        return (
          <button key={k} type="button" className="n-btn sm" aria-pressed={active === k} onClick={() => onFilter?.(active === k ? null : k)} style={{ display: "grid", gap: 4, textAlign: "left" }}>
            <span>{g.strip[k]}: {g.of(s.n, s.of)}, {s.pct}%</span>
            <span aria-hidden="true" style={{ display: "block", height: 6, borderRadius: 3, background: "var(--border-hairline)" }}>
              <span style={{ display: "block", height: 6, borderRadius: 3, width: `${s.pct}%`, background: "var(--teal, #1fb5a5)" }} />
            </span>
          </button>
        );
      })}
    </div>
  );
}

/** The Governed state panel of Define: the strip, the Must and Should lines, the owners still to confirm, and the card of the selected measure.
 * Reads the intent's view; confirms through module 2's route, so the six cells live in one file. */
export function GovernedPanel({ intentId, measureId, onFilter, me, roles }: { intentId: string; measureId?: string | null; onFilter?: (key: string | null) => void; me?: string | null; roles?: string[] }) {
  const loaded = useLoad(() => getGoverned(intentId), `gov-${intentId}`);
  const [fresh, setFresh] = useState<Governed | null>(null);
  const [filter, setFilter] = useState<string | null>(null);
  useEffect(() => setFresh(null), [loaded.data]);
  const data = fresh ?? loaded.data;
  const [note, setNote] = useState<string | null>(null);
  const reload = () => void getGoverned(intentId).then(setFresh).catch(() => undefined);
  const redraft = () => {
    if (!measureId) return;
    setNote(null);
    redraftGoverned(intentId, measureId).then((d) => { setFresh(d); setNote(d.redrafted ? g.redrafted(d.redrafted.n) : null); }).catch((e) => setNote(e instanceof ApiError && e.message ? e.message : g.error));
  };
  const canDraft = !!roles && (roles.includes("company_admin") || roles.includes("analyst"));
  return (
    <ScreenState state={loaded.state} message={loaded.state === "loading" ? g.loading : loaded.state === "error" ? g.failed : loaded.message} onRetry={loaded.retry}>
      {data ? (
        <div style={{ display: "grid", gap: 12 }}>
          <Panel title={g.title}>
            <GovernedStrip data={data} active={filter} onFilter={(k) => { setFilter(k); onFilter?.(k); }} />
            <p>{data.must.of ? g.must(data.must.n, data.must.of) : g.noMust}</p>
            {data.should.of ? <p className="n-muted">{g.should(data.should.n, data.should.of)}</p> : null}
            {data.waiting_on.map((w) => <StatusPill key={w} tone="warning">{g.ownerNotConfirmed(w)}</StatusPill>)}
            {data.not_governed.length ? (
              <>
                <strong>{g.notGovernedYet}</strong>
                <ul>{data.not_governed.map((x) => <li key={x.id}>{x.name}: {x.needs.join(", ")} not stated yet</li>)}</ul>
                <p className="n-muted">{data.refusal}</p>
              </>
            ) : null}
          </Panel>
          {measureId ? <GovernedCard intent={intentId} data={data} id={measureId} reload={reload} me={me} onRedraft={canDraft ? redraft : undefined} note={note} staff={roles ? canDraft : undefined} /> : null}
        </div>
      ) : null}
    </ScreenState>
  );
}

export default GovernedPanel;
