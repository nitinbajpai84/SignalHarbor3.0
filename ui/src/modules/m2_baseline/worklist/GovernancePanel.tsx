import { useState } from "react";

import { putGovernance, type KpiFull, type Personal, type WorkList } from "../api";
import { m2Work } from "../copy";
import { S } from "./layout";

const PERSONAL: Personal[] = ["yes", "no", "not_sure"];

/** M2-05 (per measure): personal data yes, no or not sure (treated as personal), sensitive to the business, and who may see it.
 * The server enforces who may see; this only asks. */
export default function GovernancePanel({ id, kpi, locked, act }: { id: string; kpi: KpiFull; locked: boolean; act: (p: Promise<WorkList>) => void }) {
  const g = kpi.governance;
  const [names, setNames] = useState(g.may_see.join(", "));
  return (
    <div>
      <h3 style={S.h3}>{m2Work.governanceTitle}</h3>
      <fieldset style={S.fieldset} disabled={locked}>
        <legend>{m2Work.personal}</legend>
        {PERSONAL.map((p) => (
          <label key={p} className="m1-choice">
            <input type="radio" name={`personal-${kpi.id}`} checked={g.personal === p} onChange={() => act(putGovernance(id, kpi.id, { personal: p }))} />{" "}
            {m2Work.personalOptions[p]}
          </label>
        ))}
      </fieldset>
      {g.personal === "not_sure" ? <p className="n-muted">{m2Work.notSureNote}</p> : null}
      <label className="n-flex">
        <input type="checkbox" checked={g.sensitive} disabled={locked} onChange={(e) => act(putGovernance(id, kpi.id, { sensitive: e.target.checked }))} /> {m2Work.sensitive}
      </label>
      <label style={S.label}>
        {m2Work.mayAccess}
        <input className="n-input" value={names} disabled={locked} onChange={(e) => setNames(e.target.value)} />
      </label>
      <p className="n-muted">{m2Work.mayHelp}</p>
      <button type="button" className="n-btn sm" disabled={locked}
        onClick={() => act(putGovernance(id, kpi.id, { may_see: names.split(",").map((n) => n.trim()).filter(Boolean) }))}>
        {m2Work.save}
      </button>
    </div>
  );
}
