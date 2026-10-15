import { useState } from "react";

import { ApiError, apiGet, apiSend } from "../../api/client";
import ScreenState from "../../components/ScreenState";
import { useLoad } from "../../components/useLoad";
import { Button, Chip, Pill } from "../../design";
import { dsCopy as t } from "./DataSourcesCopy";
import "./DataSourcesTab.css";

// B15 (spec 28): the Data sources tab in Define (?tab=data-sources) and its technical areas strip. A view and editor over the baseline's
// catalogue sources tab plus the extras file; everything shown comes from the server at this person's tier.

interface Cell { value: string | null; mark: "stated" | "guessed" | "unknown"; by: string | null; from: string | null }
type Kind = "business" | "data" | "source";
interface Source {
  id: string; name: string; system: { ref: string | null; name: string | null };
  format: Cell; structure: Cell; lands: Cell; connection: Cell; frequency: Cell; sla: Cell; personal: Cell; who_may_see: Cell; undecided: boolean;
  owners: Record<Kind, Cell>; state: string; confirmed_by: string | null; waiting_for: string | null;
  proposals: Record<string, { value: string; by: string; waiting_for: string }>;
  fields: { id: string; name: string; meaning: string | null; class: string | null }[];
  used_in: { measures: { id: string; name: string }[]; steps: string[]; clusters: string[] };
  problems: { id: string; text: string; by: string; at: string }[]; left_out: { by: string; reason: string } | null;
  history: { by: string; at: string; what: string }[];
  can: { edit: boolean; set_class: boolean; confirm: boolean; reassign: boolean; remove: boolean; restore: boolean; problem: boolean };
}
interface Chip_ {
  id: string; kind: "system" | "team"; name: string; restricted?: boolean; count: number; confirmed: boolean; source_ids: string[]; linked: string[];
  who_can_say: { name: string; mark: string; from?: string }[]; hidden: { by: string; reason: string } | null;
}
interface Data {
  sources: Source[]; left_out: Source[]; restricted: number; counters: Record<string, number>; areas: { chips: Chip_[]; hidden: Chip_[]; nobody_named: number };
  data_sources: { state: string; done_by: string | null; done_at: string | null }; systems: { ref: string; name: string }[]; people: string[];
  schema: { formats: string[]; frequencies: string[]; connections: string[]; structures: string[]; classes: string[] };
  can: { draft: boolean; add: boolean; done: boolean; area: boolean }; days_to_done?: number | null;
}

const url = (id: string, tail = "") => `/api/intents/${encodeURIComponent(id)}/data-sources${tail}`;
const plain = (e: unknown) => (e instanceof ApiError && e.status !== 0 && e.status < 500 ? e.message : t.failed);
const label = (r: Source) => (r.state !== "confirmed" && r.owners.source.mark === "guessed" && r.owners.source.from === "old catalogue owner" ? t.needsConfirm : t.states[r.state]);
const tone = (s: string) => (s === "confirmed" ? "signed" : s === "needs_owner" ? "late" : s === "left_out" ? "restricted" : s === "edited" ? "ok" : "draft") as "signed" | "late" | "restricted" | "ok" | "draft";

function Owner({ kind, cell }: { kind: Kind; cell: Cell }) {
  return (
    <span className={`dsrc-owner dsrc-owner--${kind}`}>
      <span className="dsrc-owner__k">{t.owners[kind]}</span>
      <span className={cell.value ? "" : "dsrc-owner__none"}>{cell.value ?? t.notNamed}</span>
      {cell.value && cell.mark === "guessed" ? <em className="n-muted"> {t.guess}</em> : null}
    </span>
  );
}

function Field({ label: l, children }: { label: string; children: React.ReactNode }) {
  return <label className="dsrc-field"><span>{l}</span>{children}</label>;
}

function Choice({ value, options, onChange, blank = t.notNamed }: { value: string; options: string[]; onChange: (v: string) => void; blank?: string }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">{blank}</option>
      {options.map((o) => <option key={o} value={o}>{o}</option>)}
    </select>
  );
}

function Drawer({ intentId, data, row, onClose, onChanged }: {
  intentId: string; data: Data; row: Source | null; onClose: () => void; onChanged: (keep?: string) => void;
}) {
  const v = (c?: Cell) => c?.value ?? "";
  const start = () => ({
    name: row?.name ?? "", system_ref: row?.system.ref ?? "", format: v(row?.format), frequency: v(row?.frequency), connection: v(row?.connection), lands: v(row?.lands),
    sla: v(row?.sla), personal: v(row?.personal), who_may_see: v(row?.who_may_see), data_owner: v(row?.owners.data), source_owner: row?.owners.source.mark === "guessed" ? "" : v(row?.owners.source),
    business_owner: v(row?.owners.business),
  });
  const [form, setForm] = useState<Record<string, string>>(start);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState({ text: "", anonymous: false });
  const [hand, setHand] = useState("");
  const [reason, setReason] = useState("");
  const g = (k: string) => form[k] ?? "";
  const set = (k: string) => (val: string) => setForm((f) => ({ ...f, [k]: val }));
  const can = row?.can ?? { edit: true, set_class: false, confirm: false, reassign: false, remove: false, restore: false, problem: false };
  const editable = row ? can.edit : true;
  const run = async (fn: () => Promise<unknown>, keep?: string) => {
    setBusy(true); setError("");
    try { await fn(); onChanged(keep); } catch (e) { setError(plain(e)); } finally { setBusy(false); }
  };
  const save = async () => {
    if (!g("name").trim()) return setError(t.drawer.needName);
    const was = start();
    const changed = Object.fromEntries(Object.entries(form).filter(([k, val]) => (row ? val !== was[k as keyof typeof was] : val.trim())));
    if (row && !Object.keys(changed).length) return onClose();
    await run(async () => {
      if (row) await apiSend("PUT", url(intentId, `/${row.id}`), { cells: changed });
      else { const out = await apiSend<{ id: string }>("POST", url(intentId), { cells: changed }); return out; }
    });
  };
  const used = row?.used_in;
  const bare = row?.fields.filter((f) => !f.meaning).length ?? 0;
  return (
    <aside className="dsrc-drawer ds-card" aria-label={row?.name ?? t.add}>
      <div className="dsrc-drawer__head">
        <Button onClick={onClose}>{t.back}</Button>
        <h3>{row?.name ?? t.add}</h3>
      </div>
      {row ? <p><Pill tone={tone(row.state)}>{label(row)}</Pill>{row.state !== "confirmed" && row.waiting_for ? <span className="n-muted"> {t.drawer.waiting(row.waiting_for)}</span> : null}</p> : null}
      <Field label={t.drawer.name}><input value={g("name")} disabled={!editable} onChange={(e) => set("name")(e.target.value)} aria-required="true" /></Field>
      <datalist id="dsrc-people">{data.people.map((p) => <option key={p} value={p} />)}</datalist>
      <fieldset className="dsrc-owners"><legend>{t.drawer.owners}</legend>
        {(["business", "data", "source"] as Kind[]).map((k) => (
          <Field key={k} label={t.owners[k]}>
            <input list="dsrc-people" value={form[`${k}_owner`] ?? ""} disabled={!editable} placeholder={t.notNamed} onChange={(e) => set(`${k}_owner`)(e.target.value)} />
          </Field>
        ))}
        <p className="n-muted">{t.drawer.people}</p>
      </fieldset>
      <Field label={t.drawer.system}>
        <select value={g("system_ref")} disabled={!editable} onChange={(e) => set("system_ref")(e.target.value)}>
          <option value="">{row ? t.drawer.notInList : t.notNamed}</option>
          {data.systems.map((s) => <option key={s.ref} value={s.ref}>{s.name}</option>)}
        </select>
      </Field>
      <Field label={t.drawer.format}><Choice value={g("format")} options={data.schema.formats} onChange={set("format")} /></Field>
      <fieldset><legend>{t.drawer.arrival}</legend>
        <Field label={t.drawer.often}><Choice value={g("frequency")} options={data.schema.frequencies} onChange={set("frequency")} /></Field>
        <Field label={t.drawer.how}><Choice value={g("connection")} options={data.schema.connections} onChange={set("connection")} /></Field>
        <Field label={t.drawer.lands}><input value={g("lands")} onChange={(e) => set("lands")(e.target.value)} /></Field>
        <Field label={t.drawer.time}><input value={g("sla")} onChange={(e) => set("sla")(e.target.value)} /></Field>
      </fieldset>
      <Field label={t.drawer.cls}>
        <Choice value={g("personal")} options={data.schema.classes} onChange={set("personal")} blank={t.drawer.undecided} />
      </Field>
      <p className="n-muted">{t.drawer.clsHelp}</p>
      {row ? Object.entries(row.proposals).map(([k, p]) => <p key={k} className="ds-warn">{t.drawer.proposed(p.by, p.waiting_for)}: {p.value || t.drawer.undecided}</p>) : null}
      <Field label={t.drawer.seen}><input value={g("who_may_see")} onChange={(e) => set("who_may_see")(e.target.value)} /></Field>
      {row && !row.who_may_see.value ? <p className="n-muted">{t.drawer.seenEmpty}</p> : null}
      {error ? <p role="alert" className="ds-warn">{error}</p> : null}
      {editable || can.set_class ? <Button variant="primary" disabled={busy} onClick={() => void save()}>{busy ? t.saving : t.save}</Button> : null}
      {row ? (
        <>
          <section><h4>{t.drawer.fields}</h4>
            {row.fields.length ? <><p className="n-muted">{t.drawer.fieldCount(row.fields.length, bare)}</p>
              <ul>{row.fields.map((f) => <li key={f.id}>{f.name}: {f.meaning ?? t.drawer.noMeaning}{f.class ? <span className="n-muted"> ({f.class})</span> : null}</li>)}</ul></>
              : <p className="n-muted">{t.drawer.noFields}</p>}
          </section>
          <section><h4>{t.drawer.used}</h4>
            {used && (used.measures.length || used.steps.length || used.clusters.length)
              ? <ul>{[...used.measures.map((m) => m.name), ...used.steps, ...used.clusters].map((x) => <li key={x}>{x}</li>)}</ul>
              : <p className="n-muted">{t.drawer.unused}</p>}
          </section>
          <section><h4>{t.drawer.problems}</h4>
            {row.problems.length ? <ul>{row.problems.map((p) => <li key={p.id}>{p.text} <span className="n-muted">{p.by}, {p.at.slice(0, 10)}</span></li>)}</ul> : <p className="n-muted">{t.drawer.noProblems}</p>}
            {can.problem ? (
              <div className="dsrc-inline">
                <input aria-label={t.drawer.problemText} placeholder={t.drawer.problemText} value={problem.text} onChange={(e) => setProblem({ ...problem, text: e.target.value })} />
                <label><input type="checkbox" checked={problem.anonymous} onChange={(e) => setProblem({ ...problem, anonymous: e.target.checked })} /> {t.drawer.anonymous}</label>
                <Button disabled={busy || !problem.text.trim()} onClick={() => void run(() => apiSend("POST", url(intentId, `/${row.id}/problems`), problem), row.id)}>{t.drawer.addProblem}</Button>
              </div>
            ) : null}
          </section>
          {can.confirm ? (
            <section className="dsrc-inline">
              <Button variant="primary" disabled={busy} onClick={() => void run(() => apiSend("POST", url(intentId, `/${row.id}/confirm`), {}), row.id)}>{t.drawer.confirm(row.owners.source.value ?? row.name)}</Button>
              <input list="dsrc-people" aria-label={t.drawer.handTo} placeholder={t.drawer.handTo} value={hand} onChange={(e) => setHand(e.target.value)} />
              <Button disabled={busy || !hand.trim()} onClick={() => void run(() => apiSend("POST", url(intentId, `/${row.id}/reassign`), { to: hand }))}>{t.drawer.notMine}</Button>
            </section>
          ) : null}
          {can.remove ? (
            <section className="dsrc-inline">
              <input aria-label={t.drawer.removeReason} placeholder={t.drawer.removeReason} value={reason} onChange={(e) => setReason(e.target.value)} />
              <Button disabled={busy || !reason.trim()} onClick={() => void run(() => apiSend("PUT", url(intentId, `/${row.id}`), { left_out: { reason } }))}>{t.drawer.remove}</Button>
            </section>
          ) : null}
          {can.restore ? <Button disabled={busy} onClick={() => void run(() => apiSend("PUT", url(intentId, `/${row.id}`), { restore: true }))}>{t.drawer.restore}</Button> : null}
          {row.history.length ? <section><h4>{t.drawer.history}</h4><ul className="n-muted">{row.history.map((h, i) => <li key={i}>{h.by}, {h.at.slice(0, 10)}: {h.what}</li>)}</ul></section> : null}
        </>
      ) : null}
    </aside>
  );
}

function AreaDrawer({ intentId, data, chip, onClose, onChanged, onOpen }: {
  intentId: string; data: Data; chip: Chip_; onClose: () => void; onChanged: () => void; onOpen: (kind: "area" | "source", id: string) => void;
}) {
  const [person, setPerson] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const names = new Map(data.areas.chips.map((c) => [c.id, c.name]));
  const send = async (body: object) => {
    setError("");
    try { await apiSend("PUT", url(intentId, `/areas/${encodeURIComponent(chip.id)}`), body); setPerson(""); setReason(""); onChanged(); } catch (e) { setError(plain(e)); }
  };
  const rows = data.sources.filter((s) => chip.source_ids.includes(s.id));
  return (
    <aside className="dsrc-drawer ds-card" aria-label={chip.name}>
      <div className="dsrc-drawer__head"><Button onClick={onClose}>{t.back}</Button><h3>{chip.name}</h3></div>
      <section><h4>{t.areas.sources}</h4>
        {rows.length ? <ul>{rows.map((r) => <li key={r.id}><button type="button" className="dsrc-link" onClick={() => onOpen("source", r.id)}>{r.name}</button></li>)}</ul> : <p className="n-muted">{t.areas.noSources}</p>}
      </section>
      <section><h4>{t.areas.people}</h4>
        {chip.who_can_say.length ? <ul>{chip.who_can_say.map((w) => <li key={w.name}>{w.name} <span className="n-muted">{w.from ?? ""}{w.mark === "guessed" ? ` (${t.guess})` : ""}</span></li>)}</ul> : <p className="n-muted">{t.areas.nobody}</p>}
        {data.can.area ? (
          <div className="dsrc-inline">
            <input list="dsrc-people-a" aria-label={t.areas.addPerson} placeholder={t.areas.addPerson} value={person} onChange={(e) => setPerson(e.target.value)} />
            <datalist id="dsrc-people-a">{data.people.map((p) => <option key={p} value={p} />)}</datalist>
            <Button disabled={!person.trim()} onClick={() => void send({ add_person: person })}>{t.areas.addPerson}</Button>
          </div>
        ) : null}
        <p className="n-muted">{t.areas.invite}</p>
      </section>
      <section><h4>{t.areas.linked}</h4>
        {chip.linked.length ? <div className="dsrc-chips">{chip.linked.map((l) => <Chip key={l} onClick={() => onOpen("area", l)}>{names.get(l) ?? l}</Chip>)}</div> : <p className="n-muted">{t.areas.noLinked}</p>}
      </section>
      {data.can.done ? (
        <section className="dsrc-inline">
          <input aria-label={t.areas.hideReason} placeholder={t.areas.hideReason} value={reason} onChange={(e) => setReason(e.target.value)} />
          <Button disabled={!reason.trim()} onClick={() => void send({ hidden_reason: reason, name: chip.name })}>{t.areas.hide}</Button>
        </section>
      ) : null}
      {error ? <p role="alert" className="ds-warn">{error}</p> : null}
    </aside>
  );
}

function Strip({ intentId, data, onOpen, onChanged }: { intentId: string; data: Data; onOpen: (id: string) => void; onChanged: () => void }) {
  const [adding, setAdding] = useState(false);
  const [f, setF] = useState({ name: "", kind: "system" });
  const [error, setError] = useState("");
  const chips = data.areas.chips;
  const add = async () => {
    try { await apiSend("POST", url(intentId, "/areas"), f); setAdding(false); setF({ name: "", kind: "system" }); onChanged(); } catch (e) { setError(plain(e)); }
  };
  return (
    <section aria-label={t.areas.title} className="dsrc-strip">
      <div className="dsrc-chips">
        {chips.length ? chips.map((c) => (
          <Chip key={c.id} onClick={c.restricted ? undefined : () => onOpen(c.id)}>
            {c.restricted ? t.restrictedArea : <>{c.name} <span className="n-muted">{t.areas.count(c.kind, c.count)}</span>{c.kind === "system" ? <span className={`dsrc-dot${c.confirmed ? " dsrc-dot--on" : ""}`} role="img" aria-label={c.confirmed ? t.areas.confirmed : t.areas.notConfirmed} /> : null}</>}
          </Chip>
        )) : <p className="n-muted">{t.areas.empty}</p>}
        {data.can.area ? <Button onClick={() => setAdding(!adding)}>{t.areas.add}</Button> : null}
      </div>
      {adding ? (
        <div className="dsrc-inline">
          <input aria-label={t.areas.name} placeholder={t.areas.name} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
          <select aria-label={t.areas.kind} value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}><option value="system">{t.areas.system}</option><option value="team">{t.areas.team}</option></select>
          <Button variant="primary" disabled={!f.name.trim()} onClick={() => void add()}>{t.save}</Button>
        </div>
      ) : null}
      {error ? <p role="alert" className="ds-warn">{error}</p> : null}
      {data.areas.hidden.length ? (
        <p className="n-muted">{t.areas.hidden}: {data.areas.hidden.map((h) => (
          <button key={h.id} type="button" className="dsrc-link" onClick={() => void apiSend("PUT", url(intentId, `/areas/${encodeURIComponent(h.id)}`), { restore: true }).then(onChanged)}>{h.name}: {t.areas.restore}</button>
        ))}</p>
      ) : null}
    </section>
  );
}

function Table({ rows, onOpen }: { rows: Source[]; onOpen: (id: string) => void }) {
  const place = (r: Source) => r.system.name ?? t.notNamed;
  return (
    <>
      <div className="ds-table-wrap dsrc-table">
        <table>
          <thead><tr>
            <th>{t.table.name}</th><th>{t.table.system}</th><th>{t.table.format}</th><th>{t.table.arrival}</th>
            <th>{t.owners.source}</th><th>{t.owners.data}</th><th>{t.owners.business}</th><th>{t.table.personal}</th><th>{t.table.state}</th>
          </tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} data-source={r.id} tabIndex={0} onClick={() => onOpen(r.id)} onKeyDown={(e) => (e.key === "Enter" ? onOpen(r.id) : undefined)}>
                <td><strong>{r.name}</strong></td><td>{place(r)}</td><td>{r.format.value ?? t.notNamed}</td>
                <td>{[r.frequency.value, r.lands.value].filter(Boolean).join(", ") || t.notNamed}</td>
                {(["source", "data", "business"] as Kind[]).map((k) => (
                  <td key={k} className={`dsrc-owner dsrc-owner--${k}`}><span className={r.owners[k].value ? "" : "dsrc-owner__none"}>{r.owners[k].value ?? t.notNamed}</span>{r.owners[k].value && r.owners[k].mark === "guessed" ? <em className="n-muted"> {t.guess}</em> : null}</td>
                ))}
                <td>{r.undecided ? t.drawer.undecided : r.personal.value}</td>
                <td><Pill tone={tone(r.state)}>{label(r)}</Pill></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="dsrc-cards">
        {rows.map((r) => (
          <li key={r.id} className="ds-card" data-source={r.id}>
            <button type="button" className="dsrc-card__open" onClick={() => onOpen(r.id)}>
              <strong>{r.name}</strong>
              <span className="n-muted">{place(r)}</span>
              {(["source", "data", "business"] as Kind[]).map((k) => <Owner key={k} kind={k} cell={r.owners[k]} />)}
              <Pill tone={tone(r.state)}>{label(r)}</Pill>
            </button>
          </li>
        ))}
      </ul>
    </>
  );
}

export function DataSourcesTab({ intentId, clusterId }: { intentId: string; sessionId?: string | null; clusterId?: string | null }) {
  const [round, setRound] = useState(0);
  const load = useLoad<Data>(() => apiGet<Data>(url(intentId)), `${intentId}:${round}`, (d) => !d);
  const [open, setOpen] = useState<{ kind: "source" | "area" | "new"; id: string } | null>(null);
  const [filter, setFilter] = useState({ state: "", cluster: clusterId ?? "", step: "" });
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const d = load.data;
  const refresh = (keep?: string) => { setRound((n) => n + 1); setOpen(keep ? { kind: "source", id: keep } : null); };
  const ask = async () => {
    setBusy(true); setNote("");
    try { setNote((await apiSend<{ message: string }>("POST", url(intentId, "/draft"), {})).message); setRound((n) => n + 1); } catch (e) { setNote(plain(e)); } finally { setBusy(false); }
  };
  const finish = async () => {
    try { await apiSend("POST", url(intentId, "/done"), {}); setRound((n) => n + 1); } catch (e) { setNote(plain(e)); }
  };
  const all = d?.sources ?? [];
  const clusters = [...new Set(all.flatMap((s) => s.used_in.clusters))];
  const steps = [...new Set(all.flatMap((s) => s.used_in.steps))];
  const shown = all.filter((s) => (!filter.state || s.state === filter.state) && (!filter.cluster || s.used_in.clusters.includes(filter.cluster)) && (!filter.step || s.used_in.steps.includes(filter.step)));
  const opened = open?.kind === "source" ? [...all, ...(d?.left_out ?? [])].find((s) => s.id === open.id) ?? null : null;
  const chip = open?.kind === "area" ? d?.areas.chips.find((c) => c.id === open.id) : undefined;
  const states = [...new Set(all.map((s) => s.state))];
  const done = d?.data_sources.state === "done";
  const empty = !!d && !all.length && !d.restricted;
  return (
    <div className="dsrc">
      <ScreenState state={load.state} message={load.message ?? (load.state === "empty" ? t.noBaseline : undefined)} onRetry={load.retry}>
        {d ? (
          <>
            <header className="dsrc-top">
              <div>
                <h2>{t.title}</h2>
                <p className="n-muted" role="status">
                  {empty ? t.empty : t.progress(d.counters.named ?? 0, d.counters.confirmed ?? 0)}{d.restricted ? `, ${t.restrictedLine(d.restricted)}` : ""}
                </p>
                {done ? <p className="n-muted">{t.doneAt(d.data_sources.done_by ?? "", d.days_to_done ?? null)}</p> : null}
              </div>
              <div className="dsrc-top__buttons">
                {d.can.draft ? <Button disabled={busy || !d.systems.length} onClick={() => void ask()} title={!d.systems.length ? t.draftOff : undefined}>{busy ? t.drafting : t.draft}</Button> : null}
                {d.can.add ? <Button variant="primary" onClick={() => setOpen({ kind: "new", id: "" })}>{t.add}</Button> : null}
                {d.can.done && !done ? <Button onClick={() => void finish()}>{t.done}</Button> : null}
              </div>
            </header>
            {d.can.draft && !d.systems.length ? <p className="n-muted">{t.draftOff}</p> : null}
            {note ? <p role="status" className="n-muted">{note}</p> : null}
            <div className="dsrc-grid">
              <nav className="dsrc-rail" aria-label={t.filters.state}>
                <label>{t.filters.clusters}
                  <select value={filter.cluster} onChange={(e) => setFilter({ ...filter, cluster: e.target.value })} disabled={!clusters.length}>
                    <option value="">{clusters.length ? t.filters.all : t.filters.none}</option>
                    {clusters.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                </label>
                <label>{t.filters.steps}
                  <select value={filter.step} onChange={(e) => setFilter({ ...filter, step: e.target.value })} disabled={!steps.length}>
                    <option value="">{t.filters.all}</option>
                    {steps.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                </label>
              </nav>
              <div className="dsrc-main">
                <Strip intentId={intentId} data={d} onOpen={(id) => setOpen({ kind: "area", id })} onChanged={() => setRound((n) => n + 1)} />
                {states.length > 1 ? (
                  <div className="dsrc-chips" aria-label={t.filters.state}>
                    <Chip tone={filter.state ? "default" : "active"} onClick={() => setFilter({ ...filter, state: "" })}>{t.filters.all}</Chip>
                    {states.map((s) => <Chip key={s} tone={filter.state === s ? "active" : "default"} onClick={() => setFilter({ ...filter, state: s })}>{t.states[s]}</Chip>)}
                  </div>
                ) : null}
                {empty ? <p className="n-muted">{t.empty}</p> : <Table rows={shown} onOpen={(id) => setOpen({ kind: "source", id })} />}
                {Array.from({ length: d.restricted }, (_, i) => <p key={i} className="ds-card dsrc-shut"><strong>{t.restricted}</strong></p>)}
              </div>
              {open?.kind === "area" && chip ? (
                <AreaDrawer key={chip.id} intentId={intentId} data={d} chip={chip} onClose={() => setOpen(null)} onChanged={() => setRound((n) => n + 1)}
                  onOpen={(kind, id) => setOpen({ kind: kind === "area" ? "area" : "source", id })} />
              ) : open?.kind === "new" || opened ? (
                <Drawer key={opened?.id ?? "new"} intentId={intentId} data={d} row={opened} onClose={() => setOpen(null)} onChanged={refresh} />
              ) : null}
            </div>
          </>
        ) : null}
      </ScreenState>
    </div>
  );
}

export default DataSourcesTab;
