import { useRef, useState, type ReactNode } from "react";

import { Button, Pill } from "../../design";
import type { LineEdit } from "../i4/api";
import Line from "../i6/Line";
import type { LayoutDoc, LayoutSection, Section } from "./api";
import "./templates.css";

// T1b: a document laid out from its template. Every section has its heading; what is still empty stays grey (the instruction, an example
// in italics, an empty table with its columns); what North or the person wrote shows as content, highlighted until "Looks right".

const head = (c: string, labels?: Record<string, string> | null) => labels?.[c] ?? (c.replace(/_/g, " ").replace(/^./, (x) => x.toUpperCase()));
const cell = (v: unknown) => (Array.isArray(v) ? v.join(", ") : v === null || v === undefined ? "" : String(v));
type Table = { columns: string[]; rows: Record<string, unknown>[] };

/** The grey form of a section: instruction, example, empty table columns. Used by the open documents and by the preview. */
export function Grey({ s }: { s: Pick<Section, "instruction" | "example" | "type"> & { columns?: string[] | null; labels?: Record<string, string> | null } }) {
  return (
    <div className="tpl-grey">
      {s.instruction ? <p className="tpl-ins">{s.instruction}</p> : null}
      {s.type === "table" && s.columns?.length ? (
        <div className="tpl-scroll"><table className="tpl-table"><thead><tr>{s.columns.map((c) => <th key={c}>{head(c, s.labels)}</th>)}</tr></thead>
          <tbody><tr>{s.columns.map((c) => <td key={c}>&nbsp;</td>)}</tr></tbody></table></div>
      ) : null}
      {s.example ? <p className="tpl-ex">For example: {s.example}</p> : null}
    </div>
  );
}

type Ed = LayoutSection["edits"][number];
const lineOnly = (s: LayoutSection) => s.edits.length > 0 && !Array.isArray(s.value) && s.edits.every((e) => e.index === undefined);

/** ED1: an editor for a filled section. A list is one line per item (add, remove); rows and cells get one box per cell. */
function Editor({ s, save, done }: { s: LayoutSection; save: (e: LineEdit) => Promise<void>; done: () => void }) {
  const asList = Array.isArray(s.value) && s.edits.length === 1 && s.edits[0]?.index === undefined;
  const [lines, setLines] = useState<string[]>(asList ? (s.value as string[]) : []);
  const [vals, setVals] = useState<string[]>(s.edits.map((e) => e.value));
  const go = async () => {
    if (asList) await save({ section: s.edits[0]!.section as LineEdit["section"], field: s.edits[0]!.field, value: lines.map((x) => x.trim()).filter(Boolean).join("\n") });
    else for (const [i, e] of s.edits.entries()) if (vals[i] !== e.value) await save({ section: e.section as LineEdit["section"], field: e.field, index: e.index, value: vals[i] ?? "" });
    done();
  };
  return (
    <form className="tpl-edit" aria-label={`Edit ${s.heading}`} onSubmit={(ev) => { ev.preventDefault(); void go(); }}>
      {asList ? <>
        {lines.map((x, i) => (
          <div key={i} style={{ display: "flex", gap: 8, margin: "4px 0" }}>
            <input className="ds-input" aria-label={`Item ${i + 1}`} value={x} style={{ flex: 1 }} onChange={(ev) => setLines(lines.map((y, j) => (j === i ? ev.target.value : y)))} />
            <Button onClick={() => setLines(lines.filter((_, j) => j !== i))} aria-label={`Remove item ${i + 1}`}>Remove</Button>
          </div>
        ))}
        <Button onClick={() => setLines([...lines, ""])}>Add item</Button>
      </> : s.edits.map((e: Ed, i) => (
        <label key={`${e.section}${e.index}${e.field}`} style={{ display: "block", margin: "4px 0" }}><span className="ds-muted">{e.label}</span>
          <input className="ds-input" aria-label={e.label} value={vals[i]} style={{ width: "100%" }} onChange={(ev) => setVals(vals.map((y, j) => (j === i ? ev.target.value : y)))} />
        </label>
      ))}
      <p><Button variant="primary" type="submit">Save</Button> <Button onClick={done}>Cancel</Button></p>
    </form>
  );
}

function Filled({ s, can, save, cards }: { s: LayoutSection; can: boolean; save: (e: LineEdit) => Promise<void>; cards: boolean }) {
  if (lineOnly(s)) return <>{s.edits.map((e) => <Line key={e.field} label={e.label} value={e.value} edit={{ section: e.section as LineEdit["section"], field: e.field, index: e.index }} can={can} save={save} />)}</>;
  if (s.type === "table") {
    const t = s.value as Table;
    if (s.view === "steps") {
      return <ol className="tpl-list">{t.rows.map((r, i) => (
        <li key={i}><strong>{cell(r.name)}</strong>{r.who ? ` (${cell(r.who)}${r.system ? `, ${cell(r.system)}` : ""})` : r.system ? ` (${cell(r.system)})` : ""}{r.does ? `: ${cell(r.does)}` : ""}</li>
      ))}</ol>;
    }
    if (cards) {
      return (
        <div className="tpl-cards">{t.rows.map((r, i) => (
          <div key={i} className="tpl-card">
            <strong>{cell(r.name)}</strong> {r._suggested ? <Pill tone="draft">Suggestion</Pill> : null}{r._status === "unclear" ? <Pill tone="late">Unclear</Pill> : null}
            {t.columns.filter((c) => c !== "name").map((c) => <p key={c} className="tpl-line"><span className="ds-muted">{head(c, s.labels)}: </span>{cell(r[c]) || <span className="tpl-empty">Not stated</span>}</p>)}
            <p className="tpl-line"><span className="ds-muted">What good looks like: </span><span className="tpl-empty">{s.example ? `e.g. ${s.example}` : "Not stated yet"}</span></p>
          </div>
        ))}</div>
      );
    }
    return (
      <div className="tpl-scroll"><table className="tpl-table"><thead><tr>{t.columns.map((c) => <th key={c}>{head(c, s.labels)}</th>)}</tr></thead>
        <tbody>{t.rows.map((r, i) => <tr key={i}>{t.columns.map((c) => <td key={c}>{cell(r[c])}</td>)}</tr>)}</tbody></table></div>
    );
  }
  if (Array.isArray(s.value)) return <ul className="tpl-list">{s.value.map((x, i) => <li key={i}>{x}</li>)}</ul>;
  return <p className="tpl-text">{String(s.value)}</p>;
}

export default function DocumentLayout({ doc, can, save, onSwitch, swim, after, iid }: {
  doc: LayoutDoc; can: boolean; save: (e: LineEdit) => Promise<void>; onSwitch?: (kind: string, templateId: string) => void;
  /** The process map's swimlane with its buttons (the conversation page owns them). */
  swim?: ReactNode; after?: ReactNode; iid?: string;
}) {
  const sig = (s: LayoutSection) => (s.filled ? JSON.stringify(s.value) : "");
  const base = useRef<Record<string, string> | null>(null);
  const [okd, setOkd] = useState<Record<string, string>>({});
  if (base.current === null) base.current = Object.fromEntries(doc.sections.map((s) => [s.key, sig(s)]));
  const fresh = (s: LayoutSection) => s.filled && sig(s) !== (okd[s.key] ?? base.current?.[s.key] ?? "");
  const [editing, setEditing] = useState<string | null>(null);
  const left = doc.sections.filter((s) => s.required && !s.filled).length; // a9.2: a signed document (can is false) has nothing left to fill in
  return (
    <div className="tpl-doc" data-iid={iid}>
      <p className="tpl-bar">
        {onSwitch && doc.choices.length > 1 ? (
          <label>Template{" "}
            <select className="ds-input" aria-label={`Template for ${doc.title}`} value={doc.template.id} onChange={(ev) => onSwitch(doc.kind, ev.target.value)}>
              {doc.choices.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
        ) : <span className="ds-muted">Template: {doc.template.name}</span>}
        {left && can ? <span className="ds-muted"> · {left} required {left === 1 ? "section" : "sections"} still to fill in</span> : null}
      </p>
      {doc.sections.map((s) => (
        <section key={s.key} className={`tpl-sec${s.filled ? "" : " tpl-sec--grey"}${fresh(s) ? " tpl-sec--new" : ""}`} data-filled={s.filled} aria-label={s.heading}>
          <h3 className="tpl-h">{s.heading}{s.required && !s.filled && can ? <span className="tpl-req"> Required</span> : null}</h3>
          {editing === s.key ? <Editor s={s} save={save} done={() => setEditing(null)} /> : s.filled && s.view === "swimlane" && swim ? swim : s.filled ? <Filled s={s} can={can} save={save} cards={s.view === "cards"} /> : <Grey s={s} />}
          {s.filled && can && s.edits.length && !lineOnly(s) && editing !== s.key ? (
            <p><button type="button" className="ds-link" aria-label={`Edit ${s.heading}`} onClick={() => setEditing(s.key)}>Edit</button></p>
          ) : null}
          {s.filled && s.from.length ? <p className="tpl-from">From {s.from.join(", ")}</p> : null}
          {fresh(s) ? (
            <p className="tpl-new">North just filled this in. <button type="button" className="ds-link" aria-label={`Looks right: ${s.heading}`}
              onClick={() => setOkd({ ...okd, [s.key]: sig(s) })}>Looks right</button></p>
          ) : null}
          {!s.filled && can && s.edits[0] ? <Line label={s.edits[0].label} value="" edit={{ section: s.edits[0].section as LineEdit["section"], field: s.edits[0].field }} can save={save} /> : null}
        </section>
      ))}
      {after}
    </div>
  );
}
