import { useState } from "react";

import { ApiError } from "../../../api/client";
import {
  answerQuestion, confirmKpi, lensRedraft, notifyChanged, putOwners, putTriage, type LensAsk, type LensState, type RefineItem,
} from "../api";
import { m2Lens } from "../copy";
import ProvCell from "../worklist/ProvCell";

const failed = (e: unknown) => (e instanceof ApiError ? e.message : m2Lens.sayFailed);

/** One measure or suggestion with Lens's draft and the three things a person can do: use it, edit it, or tell Lens what to change.
 * A person's own wording is shown as theirs; Lens's redraft then goes beside it as a proposal, never over it. */
export function RefineCard({ baselineId, item, pending, locked }: { baselineId: string; item: RefineItem; pending: boolean; locked: boolean }) {
  const [mode, setMode] = useState<"" | "edit" | "tell">("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const d = item.definition;
  const mine = !!d && d.mark === "stated";

  /** A suggestion becomes a measure only when a person says so: using or editing its draft is that person saying so. */
  const withMeasure = async () => {
    if (item.kind === "suggestion") await confirmKpi(baselineId, { suggestion_id: item.id });
  };
  const run = async (job: () => Promise<{ lens_note?: string } | unknown>) => {
    setBusy(true);
    setNote("");
    try {
      const r = (await job()) as { lens_note?: string } | undefined;
      setNote(r?.lens_note ?? "");
      setMode("");
      notifyChanged();
    } catch (e) {
      setNote(failed(e));
    } finally {
      setBusy(false);
    }
  };
  const use = () => run(async () => { await withMeasure(); return putTriage(baselineId, item.id, { definition: { text: d?.value ?? "", mark: "stated" } }); });
  const save = () => run(async () => { await withMeasure(); return putTriage(baselineId, item.id, { definition: { text, mark: "stated" } }); });
  const redraft = () => run(() => lensRedraft(baselineId, item.id, text));

  return (
    <li className="n-companion-card" style={{ listStyle: "none", padding: "8px 0", borderTop: "1px solid var(--n-line, #ddd)" }}>
      <strong>{item.name}</strong>
      {item.label ? <div className="n-muted">{m2Lens.suggestion} · {item.label}</div> : null}
      {item.problems.length ? <div className="n-muted">{item.problems.join(", ")}</div> : null}
      {pending ? <p className="n-muted" role="status">{m2Lens.working}</p> : d && d.mark !== "unknown" ? <ProvCell p={d} /> : <p className="n-muted">{m2Lens.noDefinition}</p>}
      {mine ? <span className="n-muted">{m2Lens.yours}</span> : null}
      {mode === "" ? (
        <div className="n-flex wrap">
          {!mine && d && d.value ? <button type="button" className="n-btn sm" disabled={locked || busy} aria-label={`${m2Lens.use}: ${item.name}`} onClick={use}>{m2Lens.use}</button> : null}
          <button type="button" className="n-btn sm" disabled={locked || busy} aria-label={`${m2Lens.edit}: ${item.name}`} onClick={() => { setText(d?.value ?? ""); setMode("edit"); }}>{m2Lens.edit}</button>
          <button type="button" className="n-btn sm" disabled={locked || busy} aria-label={`${m2Lens.tell}: ${item.name}`} onClick={() => { setText(""); setMode("tell"); }}>{m2Lens.tell}</button>
        </div>
      ) : (
        <div>
          <textarea className="n-input" rows={2} value={text} aria-label={mode === "edit" ? m2Lens.editLabel(item.name) : m2Lens.tellLabel(item.name)} onChange={(e) => setText(e.target.value)} />
          <div className="n-flex wrap">
            <button type="button" className="n-btn sm primary" disabled={busy || !text.trim()} onClick={mode === "edit" ? save : redraft}>{mode === "edit" ? m2Lens.save : m2Lens.redraft}</button>
            <button type="button" className="n-btn sm" disabled={busy} onClick={() => setMode("")}>{m2Lens.cancel}</button>
          </div>
        </div>
      )}
      {note ? <p role="status" className="n-muted">{note}</p> : null}
    </li>
  );
}

/** The one question Lens is asking now. The answer goes to the same field the work list's table uses, stated by this person. */
export function AskCard({ baselineId, ask, people, locked, onSkip }: { baselineId: string; ask: LensAsk; people: LensState["people"]; locked: boolean; onSkip: () => void }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const send = async (answer: string) => {
    const a = answer.trim();
    if (!a) return;
    setBusy(true);
    setNote("");
    try {
      if (ask.field === "owner" && ask.role) {
        const who = people.find((p) => p.display_name.trim().toLowerCase() === a.toLowerCase());
        await putOwners(baselineId, ask.kpi_id, { [ask.role]: who ? { account_id: who.account_id } : { name: a, has_account: false } });
      } else if (ask.field === "question" && ask.question_id) await answerQuestion(baselineId, ask.kpi_id, ask.question_id, a);
      else if (ask.field === "definition" || ask.field === "producer" || ask.field === "gathered") await putTriage(baselineId, ask.kpi_id, { [ask.field]: { text: a, mark: "stated" } });
      setText("");
      notifyChanged();
    } catch (e) {
      setNote(failed(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div>
      <p>{ask.text}</p>
      {ask.draft ? <button type="button" className="n-btn sm" disabled={locked || busy} onClick={() => send(ask.draft?.value ?? "")}>{m2Lens.useOwner(ask.draft.value)}</button> : null}
      {ask.field === "owner" ? (
        <input className="n-input" value={text} aria-label={m2Lens.answerLabel} list="m2-people" onChange={(e) => setText(e.target.value)} />
      ) : (
        <textarea className="n-input" rows={2} value={text} aria-label={m2Lens.answerLabel} onChange={(e) => setText(e.target.value)} />
      )}
      {ask.field === "owner" ? <datalist id="m2-people">{people.map((p) => <option key={p.account_id} value={p.display_name} />)}</datalist> : null}
      <div className="n-flex wrap">
        <button type="button" className="n-btn sm primary" disabled={locked || busy || !text.trim()} onClick={() => send(text)}>{m2Lens.answer}</button>
        <button type="button" className="n-btn sm" disabled={busy} onClick={onSkip}>{m2Lens.skip}</button>
      </div>
      {note ? <p role="alert" className="state state-error">{note}</p> : null}
    </div>
  );
}
