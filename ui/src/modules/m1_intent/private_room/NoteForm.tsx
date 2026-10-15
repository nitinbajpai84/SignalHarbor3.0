import { useState } from "react";

import { ApiError } from "../../../api/client";
import { copy } from "../../../copy";
import { m1Notes as t } from "../copy";
import { wallCopy } from "../wall/copy";
import { prefillNote, saveNote, submitNote, type FieldValue, type NoteKind, type Room, type RoomNote } from "./roomApi";

interface Props {
  sessionId: string;
  note: RoomNote;
  form: Room["form"];
  open: boolean;
  northAvailable: boolean;
  onRoom: (room: Room) => void;
  /** The four kinds of note with their own details, how names are shown, and the pack's suggestions: all from the room. */
  kinds?: Room["kinds"];
  names?: Room["names"];
  north?: Room["north"];
}

const show = (v: FieldValue | undefined): string => (v === undefined ? "" : Array.isArray(v) ? v.join(", ") : String(v));

/** M1-11, M1-12: the form of one note (fields from the contract), By name / Anonymous, and Submit. */
export default function NoteForm({ sessionId, note, form, open, northAvailable, onRoom, kinds = [], names = "choice", north }: Props) {
  const kind: NoteKind = note.kind ?? "intent";
  const info = kinds.find((k) => k.id === kind);
  const base = form.filter((f) => f.id !== "problem");
  const every = [...base, ...kinds.flatMap((k) => k.fields)];
  // what this kind of note asks about: the fields every kind has (or that name this kind), then the kind's own details
  const fields = [...base.filter((f) => !f.kinds?.length || f.kinds.includes(kind)), ...(info?.fields ?? [])];
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(every.map((f) => [f.id, show(note.fields[f.id])])),
  );
  const [busy, setBusy] = useState(false);
  const [filling, setFilling] = useState(false); // North is working on the fields: it takes a few seconds
  const [error, setError] = useState<string | null>(null);
  const submitted = note.state === "submitted";
  const editable = open && !submitted;

  async function run(work: () => Promise<Room>, refill = false) {
    setBusy(true);
    setFilling(refill);
    setError(null);
    try {
      const room = await work();
      onRoom(room);
      if (refill) {
        const fresh = room.notes.find((n) => n.id === note.id);
        if (fresh) setValues(Object.fromEntries(every.map((f) => [f.id, show(fresh.fields[f.id])])));
      }
    } catch (e) {
      setError(e instanceof ApiError && e.message ? e.message : copy.errors.server);
    } finally {
      setBusy(false);
      setFilling(false);
    }
  }

  const payload = (): Record<string, FieldValue | null> =>
    Object.fromEntries(
      fields.map((f): [string, FieldValue | null] => {
        const raw = (values[f.id] ?? "").trim();
        if (raw === "") return [f.id, null];
        if (f.kind === "number") return [f.id, Number(raw)];
        if (f.kind === "labels") return [f.id, raw.split(",").map((x) => x.trim()).filter(Boolean)];
        return [f.id, raw];
      }),
    );

  return (
    <fieldset className="m1-fieldset" disabled={busy}>
      <legend>{t.detailsHeading}</legend>
      {submitted ? (
        <p role="status" className="n-muted">
          {t.submittedHelp}
        </p>
      ) : null}
      {filling ? (
        <p role="status" aria-live="polite" className="n-muted">
          {t.filling}
        </p>
      ) : null}
      {kinds.length > 0 ? (
        <fieldset className="m1-fieldset" disabled={!editable || busy}>
          <legend>{t.kindLegend}</legend>
          {kinds.map((k) => (
            <label key={k.id} className="m1-choice">
              <input
                type="radio"
                name={`kind-${note.id}`}
                checked={kind === k.id}
                onChange={() => void run(() => saveNote(sessionId, note.id, { kind: k.id }))}
              />
              <span>
                <strong>{k.label}</strong>
              </span>
            </label>
          ))}
          <span className="m1-help">{t.kindHelp}</span>
          {editable && note.kind_suggested && note.kind_suggested !== kind ? (
            <p>
              {t.kindSuggested(kinds.find((k) => k.id === note.kind_suggested)?.label ?? "")}{" "}
              <button type="button" className="n-btn" onClick={() => void run(() => saveNote(sessionId, note.id, { kind: note.kind_suggested as NoteKind }))}>
                {t.kindUse}
              </button>
            </p>
          ) : null}
          {editable && kind !== "intent" ? <Suggestions label={info?.heading ?? ""} items={north?.suggestions?.[kind] ?? []} tag={north?.suggestions_label} empty={north?.suggestions_empty} /> : null}
        </fieldset>
      ) : null}
      {editable && northAvailable ? (
        <p>
          <button type="button" className="n-btn" onClick={() => void run(() => prefillNote(sessionId, note.id), true)}>
            {t.askNorth}
          </button>{" "}
          <span className="n-muted">{t.askNorthHelp}</span>
        </p>
      ) : null}
      {fields.map((f) => (
        <label key={f.id}>
          {f.label}
          {f.guess ? <span className="n-pill tone-info">{t.guessTag}</span> : null}
          <input
            type={f.kind === "number" ? "number" : "text"}
            step="any"
            value={values[f.id] ?? ""}
            disabled={!editable}
            onChange={(e) => setValues({ ...values, [f.id]: e.target.value })}
          />
          {f.person_only ? <span className="m1-help">{t.beliefHelp}</span> : null}
          {f.kind === "labels" ? <span className="m1-help">{t.labelsHelp}</span> : null}
        </label>
      ))}
      {editable && note.labels_suggested.length > 0 ? (
        <p>
          {t.labelsSuggested}{" "}
          {note.labels_suggested.map((l) => (
            <button
              key={l}
              type="button"
              className="n-btn"
              onClick={() => {
                const id = fields.find((f) => f.kind === "labels")?.id;
                if (id) setValues({ ...values, [id]: [values[id], l].filter((x) => x && x.trim() !== "").join(", ") });
              }}
            >
              {l}
            </button>
          ))}
        </p>
      ) : null}
      {note.missing.length > 0 && !submitted ? (
        <p className="n-muted">
          {t.stillToFill} {form.filter((f) => note.missing.includes(f.id)).map((f) => f.label).join(", ")}
        </p>
      ) : null}
      {names !== "choice" ? <p className="m1-help">{names === "named" ? t.namesNamed : t.namesAnonymous}</p> : null}
      {names === "choice" ? (
      <fieldset className="m1-fieldset" disabled={!editable || busy}>
        <legend>{t.choiceLegend}</legend>
        <label className="m1-choice">
          <input
            type="radio"
            name={`choice-${note.id}`}
            checked={!note.anonymous}
            onChange={() => void run(() => saveNote(sessionId, note.id, { anonymous: false }))}
          />
          <span>
            <strong>{t.byName}</strong> <span className="m1-help">{t.byNameHelp}</span>
          </span>
        </label>
        <label className="m1-choice">
          <input
            type="radio"
            name={`choice-${note.id}`}
            checked={note.anonymous}
            onChange={() => void run(() => saveNote(sessionId, note.id, { anonymous: true }))}
          />
          <span>
            <strong>{t.anonymous}</strong> <span className="m1-help">{t.anonymousHelp}</span>
          </span>
        </label>
      </fieldset>
      ) : null}
      <label className="m1-choice">
        <input
          type="checkbox"
          disabled={!editable || busy}
          checked={note.restricted === true}
          onChange={(e) => void run(() => saveNote(sessionId, note.id, { restricted: e.target.checked }))}
        />
        <span>{wallCopy.sealBox}</span>
      </label>
      {error ? (
        <p role="alert" className="state state-error">
          {error}
        </p>
      ) : null}
      {editable ? (
        <div className="m1-actions">
          <button type="button" className="n-btn" onClick={() => void run(() => saveNote(sessionId, note.id, { fields: payload() }))}>
            {busy ? t.saving : t.save}
          </button>
          <button
            type="button"
            className="n-btn primary"
            onClick={() =>
              void run(async () => {
                await saveNote(sessionId, note.id, { fields: payload() });
                return submitNote(sessionId, note.id);
              })
            }
          >
            {t.submit}
          </button>
          <span className="n-muted">{t.submitHelp}</span>
        </div>
      ) : null}
    </fieldset>
  );
}

/** What others in the industry usually raise for this kind of note, labelled as a suggestion; an honest empty state without a pack. */
function Suggestions({ label, items, tag, empty }: { label: string; items: string[]; tag?: string | null; empty?: string | null }) {
  if (items.length === 0) return empty ? <p className="n-muted">{empty}</p> : null;
  return (
    <div className="n-suggest-block" role="group" aria-label={t.suggestionsFor(label)}>
      <div className="n-suggest-label">{tag ?? ""}</div>
      <p className="n-muted">{t.suggestionsFor(label)}</p>
      <ul>
        {items.map((i) => (
          <li key={i}>{i}</li>
        ))}
      </ul>
    </div>
  );
}
