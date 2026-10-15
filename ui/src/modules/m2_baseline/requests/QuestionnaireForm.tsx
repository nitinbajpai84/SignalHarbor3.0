import { useId, useRef, useState } from "react";

import { ApiError } from "../../../api/client";
import type { AnswerInputs, AnswerRecord, FieldSpec, FileUpload, Hop, Mark, Prov, QuestionnaireSpec, SourceRow } from "../api";
import { m2Form as T } from "../copy";

interface FieldState {
  mark: Mark | "";
  choice: string;
  text: string;
  hops: Hop[];
  rows: SourceRow[];
}

const blankHop = (): Hop => ({ who: "", what: "", step: "", manual: false });
const blankRow = (): SourceRow => ({});
const EMPTY: FieldState = { mark: "", choice: "", text: "", hops: [blankHop()], rows: [blankRow()] };

/** A saved source row back to what the person typed: each cell's value, a list as comma-separated words. */
function rowToText(saved: unknown): SourceRow {
  const out: SourceRow = {};
  for (const [k, cell] of Object.entries((saved ?? {}) as Record<string, Prov<unknown>>)) {
    const v = cell?.mark === "unknown" ? null : cell?.value;
    if (v !== null && v !== undefined && v !== "") out[k] = Array.isArray(v) ? v.join(", ") : String(v);
  }
  return out;
}

function startState(spec: FieldSpec, rec: AnswerRecord | null): FieldState {
  const p = rec ? (rec[spec.key] as Prov<unknown> | undefined) : undefined;
  const answered = p && !(rec?.unanswered ?? []).includes(spec.key);
  const value = answered ? p.value : null;
  return {
    mark: answered ? p.mark : "",
    choice: spec.kind === "choice" && typeof value === "string" ? value : "",
    text: spec.kind === "text" && typeof value === "string" ? value : "",
    hops: spec.kind === "hops" && Array.isArray(value) ? (value as Hop[]).map((h) => ({ ...blankHop(), ...h })) : [blankHop()],
    rows: spec.kind === "rows" && Array.isArray(value) && value.length > 0 ? value.map(rowToText) : [blankRow()],
  };
}

const rowHasContent = (r: SourceRow): boolean => Object.values(r).some((x) => x.trim() !== "");

const hasContent = (spec: FieldSpec, s: FieldState): boolean =>
  spec.kind === "choice"
    ? s.choice !== ""
    : spec.kind === "text"
      ? s.text.trim() !== ""
      : spec.kind === "rows"
        ? s.rows.some(rowHasContent)
        : s.hops.some((h) => [h.who, h.what, h.step].some((x) => (x ?? "").trim() !== ""));

/** What is sent for a list of systems or files: only the cells the person filled; an empty one is an unknown on the server. */
const rowsToInput = (rows: SourceRow[]): SourceRow[] =>
  rows.filter(rowHasContent).map((r) => Object.fromEntries(Object.entries(r).filter(([, v]) => v.trim() !== "")));

/** A hop sends only the parts its step kind has in the contract: "manual" exists on the in-between step alone. */
const hopToInput = (f: FieldSpec, h: Hop): Hop => {
  const keys = new Set((f.hop ?? []).map((p) => p.key));
  const rec = h as unknown as Record<string, unknown>;
  const text = keys.has("step") ? "step" : "what"; // `what` and `step` are one thing: the words of the step
  return Object.fromEntries(Object.entries(rec).filter(([k]) => keys.has(k) || ((k === "what" || k === "step") && k === text))) as unknown as Hop;
};

export function toInputs(spec: QuestionnaireSpec, state: Record<string, FieldState>): AnswerInputs | string {
  const out: AnswerInputs = {};
  for (const f of spec.fields) {
    const s = state[f.key] ?? EMPTY;
    if (s.mark === "") {
      if (hasContent(f, s)) return T.needMark;
      continue;
    }
    const value =
      s.mark === "unknown"
        ? null
        : f.kind === "choice"
          ? s.choice
          : f.kind === "text"
            ? s.text
            : f.kind === "rows"
              ? rowsToInput(s.rows)
              : s.hops.filter((h) => hasContent(f, { ...s, hops: [h] })).map((h) => hopToInput(f, h));
    out[f.key] = { value, mark: s.mark };
  }
  return out;
}

const readBase64 = (file: File): Promise<string> =>
  new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result).split(",")[1] ?? "");
    r.onerror = () => reject(new Error("read"));
    r.readAsDataURL(file);
  });

interface Props {
  spec: QuestionnaireSpec;
  measure: string;
  initial: AnswerRecord | null;
  onSave: (answers: AnswerInputs) => Promise<AnswerRecord>;
  onSample: (file: FileUpload) => Promise<AnswerRecord>;
  saveLabel?: string;
  /** Called after each good save with the saved record. */
  onSaved?: (rec: AnswerRecord) => void;
}

/**
 * The owner questionnaire for one measure (deck slides 7 and 8: sense and trace). The same form is used on the answer page and by the
 * organiser answering in a meeting. Every answer is marked: I am sure, my best guess, or I don't know.
 */
export default function QuestionnaireForm({ spec, measure, initial, onSave, onSample, saveLabel, onSaved }: Props) {
  const uid = useId();
  const [state, setState] = useState<Record<string, FieldState>>(() => Object.fromEntries(spec.fields.map((f) => [f.key, startState(f, initial)])));
  const [sample, setSample] = useState<string | null>(initial?.sample_title ?? null);
  const [uploaded, setUploaded] = useState<string | null>(null);
  const [busy, setBusy] = useState<"save" | "file" | null>(null);
  const [note, setNote] = useState<{ kind: "ok" | "bad"; text: string } | null>(null);
  const file = useRef<HTMLInputElement>(null);

  const set = (key: string, patch: Partial<FieldState>) => setState((s) => ({ ...s, [key]: { ...(s[key] ?? EMPTY), ...patch } }));
  const fail = (e: unknown) => setNote({ kind: "bad", text: e instanceof ApiError && e.message ? e.message : T.noPage });

  async function save() {
    const inputs = toInputs(spec, state);
    if (typeof inputs === "string") {
      setNote({ kind: "bad", text: inputs });
      return;
    }
    setBusy("save");
    setNote(null);
    try {
      const rec = await onSave(inputs);
      setNote({ kind: "ok", text: T.saved });
      onSaved?.(rec);
    } catch (e) {
      fail(e);
    } finally {
      setBusy(null);
    }
  }

  async function upload(f: File | undefined) {
    if (!f) return;
    setBusy("file");
    setNote(null);
    try {
      const rec = await onSample({ filename: f.name, data: await readBase64(f) });
      setSample(rec.sample_title ?? f.name);
      setUploaded(T.uploadedAt(f.name, new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })));
      onSaved?.(rec);
    } catch (e) {
      fail(e);
    } finally {
      setBusy(null);
      if (file.current) file.current.value = "";
    }
  }

  return (
    <form
      aria-label={measure}
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
    >
      {spec.fields.map((f) => (
        <Question key={f.key} uid={uid} field={f} marks={spec.marks} s={state[f.key] ?? EMPTY} change={(p) => set(f.key, p)} maxHops={spec.limits.hops} maxRows={spec.limits.source_rows ?? 12} />
      ))}
      <fieldset className="m1-fieldset">
        <legend>{T.sample}</legend>
        <p className="n-e1-def-note">{T.sampleHelp}</p>
        {sample ? <p>{T.sampleAdded(sample)}</p> : null}
        <label>
          {T.addSample}
          <input ref={file} type="file" disabled={busy !== null} onChange={(e) => void upload(e.target.files?.[0])} />
        </label>
        {uploaded && busy !== "file" ? <span role="status" className="n-muted"> {uploaded}</span> : null}
        {busy === "file" ? (
          <p role="status" className="n-muted">
            {T.uploading}
          </p>
        ) : null}
      </fieldset>
      <div className="m1-actions">
        <button type="submit" className="n-btn primary" disabled={busy !== null}>
          {busy === "save" ? T.saving : (saveLabel ?? T.saveMeasure)}
        </button>
      </div>
      {note ? (
        <p role={note.kind === "bad" ? "alert" : "status"} className={note.kind === "bad" ? "state state-error" : "state n-muted"}>
          {note.text}
        </p>
      ) : null}
    </form>
  );
}

interface QuestionProps {
  uid: string;
  field: FieldSpec;
  marks: QuestionnaireSpec["marks"];
  s: FieldState;
  change: (patch: Partial<FieldState>) => void;
  maxHops: number;
  maxRows: number;
}

function Question({ uid, field, marks, s, change, maxHops, maxRows }: QuestionProps) {
  const name = `${uid}-${field.key}`;
  const off = s.mark === "unknown";
  return (
    <fieldset className="m1-fieldset">
      <legend>{field.question}</legend>
      {field.kind === "choice"
        ? field.choices?.map((c) => (
            <label key={c.value} className="m1-choice">
              <input type="radio" name={name} value={c.value} checked={s.choice === c.value} disabled={off} onChange={() => change({ choice: c.value })} />
              <span>{c.label}</span>
            </label>
          ))
        : null}
      {field.kind === "text" ? (
        <textarea aria-label={field.question} rows={2} value={s.text} disabled={off} onChange={(e) => change({ text: e.target.value })} />
      ) : null}
      {field.kind === "hops" ? <Hops field={field} s={s} off={off} change={change} max={maxHops} /> : null}
      {field.kind === "rows" ? <Rows field={field} s={s} off={off} change={change} max={maxRows} /> : null}
      <fieldset className="m1-fieldset">
        <legend className="n-e1-def-note">{T.sureness}</legend>
        <div className="m1-actions">
          {marks.map((m) => (
            <label key={m.value} className="m1-choice">
              <input type="radio" name={`${name}-mark`} value={m.value} checked={s.mark === m.value} onChange={() => change({ mark: m.value })} />
              <span>{m.label}</span>
            </label>
          ))}
        </div>
      </fieldset>
    </fieldset>
  );
}

function Rows({ field, s, off, change, max }: { field: FieldSpec; s: FieldState; off: boolean; change: (p: Partial<FieldState>) => void; max: number }) {
  const edit = (i: number, key: string, value: string) => change({ rows: s.rows.map((r, n) => (n === i ? { ...r, [key]: value } : r)) });
  return (
    <div>
      <p className="n-e1-def-note">{T.sourceHelp}</p>
      {s.rows.map((r, i) => (
        <div key={i} className="n-panel tight" role="group" aria-label={T.sourceLabel(i + 1)}>
          {field.row?.map((col) => (
            <label key={col.key}>
              {col.label}
              {col.kind === "choice" ? (
                <select value={r[col.key] ?? ""} disabled={off} onChange={(e) => edit(i, col.key, e.target.value)}>
                  <option value="">{T.chooseOne}</option>
                  {col.choices?.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </select>
              ) : (
                <input type="text" placeholder={col.kind === "list" ? T.listHint : undefined} value={r[col.key] ?? ""} disabled={off} onChange={(e) => edit(i, col.key, e.target.value)} />
              )}
            </label>
          ))}
          {s.rows.length > 1 ? (
            <button type="button" className="n-btn" disabled={off} onClick={() => change({ rows: s.rows.filter((_, n) => n !== i) })}>
              {T.removeSource}
            </button>
          ) : null}
        </div>
      ))}
      {s.rows.length < max ? (
        <button type="button" className="n-btn" disabled={off} onClick={() => change({ rows: [...s.rows, blankRow()] })}>
          {T.addSource}
        </button>
      ) : null}
    </div>
  );
}

function Hops({ field, s, off, change, max }: { field: FieldSpec; s: FieldState; off: boolean; change: (p: Partial<FieldState>) => void; max: number }) {
  const edit = (i: number, patch: Partial<Hop>) => change({ hops: s.hops.map((h, n) => (n === i ? { ...h, ...patch } : h)) });
  return (
    <div>
      {s.hops.map((h, i) => (
        <div key={i} className="n-panel tight" role="group" aria-label={T.stepLabel(i + 1)}>
          {field.hop?.map((part) =>
            part.key === "manual" ? (
              <label key={part.key} className="m1-choice">
                <input type="checkbox" checked={h.manual === true} disabled={off} onChange={(e) => edit(i, { manual: e.target.checked })} />
                <span>{part.label}</span>
              </label>
            ) : (
              <label key={part.key}>
                {part.label}
                <input type="text" inputMode={part.key === "order" ? "numeric" : undefined} value={String((h as unknown as Record<string, unknown>)[part.key] ?? "")} disabled={off} onChange={(e) => edit(i, { [part.key]: e.target.value })} />
              </label>
            ),
          )}
          {s.hops.length > 1 ? (
            <button type="button" className="n-btn" disabled={off} onClick={() => change({ hops: s.hops.filter((_, n) => n !== i) })}>
              {T.removeStep}
            </button>
          ) : null}
        </div>
      ))}
      {s.hops.length < max ? (
        <button type="button" className="n-btn" disabled={off} onClick={() => change({ hops: [...s.hops, blankHop()] })}>
          {T.addStep}
        </button>
      ) : null}
    </div>
  );
}
