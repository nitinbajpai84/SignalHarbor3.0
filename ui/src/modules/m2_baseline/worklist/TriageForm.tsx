import { useState } from "react";

import { putTriage, type KpiFull, type Mark, type Prov, type WorkList } from "../api";
import { m2Work } from "../copy";
import { S } from "./layout";

type Field = "definition" | "producer" | "gathered";
const FIELDS: Field[] = ["definition", "producer", "gathered"];
const MARKS: Mark[] = ["stated", "guessed", "unknown"];

function FieldRow({ id, kpi, field, locked, act }: { id: string; kpi: KpiFull; field: Field; locked: boolean; act: (p: Promise<WorkList>) => void }) {
  const current: Prov = kpi[field];
  const [text, setText] = useState(current.value ?? "");
  const [mark, setMark] = useState<Mark>(current.mark);
  const label = m2Work.fields[field];
  return (
    <div style={S.field}>
      <label style={S.label}>
        {label}
        <textarea className="n-input" rows={2} value={text} disabled={locked} onChange={(e) => { setText(e.target.value); if (mark === "unknown") setMark("stated"); }} />
      </label>
      <label style={S.label}>
        {m2Work.markLabel}
        <select className="n-select" aria-label={`${label}: ${m2Work.markLabel}`} value={mark} disabled={locked} onChange={(e) => setMark(e.target.value as Mark)}>
          {MARKS.map((m) => (
            <option key={m} value={m}>
              {m2Work.markWords[m]}
            </option>
          ))}
        </select>
      </label>
      <button type="button" className="n-btn sm" disabled={locked || (mark !== "unknown" && !text.trim())} aria-label={`${m2Work.save}: ${label}`}
        onClick={() => act(putTriage(id, kpi.id, { [field]: { text, mark } }))}>
        {m2Work.save}
      </button>
    </div>
  );
}

/** The three things a person can say about a measure here: the definition, who produces the data, how it is gathered.
 * Each is stated, a guess or unknown. Lens's newer draft sits beside a stated definition and is used only when the person says so. */
export default function TriageForm({ id, kpi, locked, act }: { id: string; kpi: KpiFull; locked: boolean; act: (p: Promise<WorkList>) => void }) {
  const p = kpi.definition_proposal;
  return (
    <div>
      <h3 style={S.h3}>{m2Work.triageEdit}</h3>
      {p?.value ? (
        <div className="n-suggest-block">
          <div className="n-suggest-label">{m2Work.proposalTitle}</div>
          <p>{p.value}</p>
          <p className="n-muted">{m2Work.suggestionTag}{p.from ? ` · ${m2Work.fromWhere(p.from)}` : ""}</p>
          <button type="button" className="n-btn sm" disabled={locked} onClick={() => act(putTriage(id, kpi.id, { definition: { text: p.value ?? "", mark: "stated" } }))}>
            {m2Work.useProposal}
          </button>
        </div>
      ) : null}
      {FIELDS.map((f) => (
        <FieldRow key={`${kpi.id}-${f}-${kpi[f].at}`} id={id} kpi={kpi} field={f} locked={locked} act={act} />
      ))}
    </div>
  );
}
