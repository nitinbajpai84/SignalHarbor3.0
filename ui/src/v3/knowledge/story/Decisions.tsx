import { useState } from "react";
import { Link } from "react-router-dom";

import { Failed, useRead } from "../../board/common";
import { getDecisions, type DecisionRow } from "./api";

const KINDS: ["all" | DecisionRow["kind"], string][] = [["all", "All"], ["rule", "Rules"], ["decision", "Decisions"], ["assumption", "Assumptions"]];
const NAME = { rule: "Rule", decision: "Decision", assumption: "Assumption" } as const;

/** One list: signed rules (version and signer), decisions (signed briefs, go-lives, sign-offs) and assumptions, each with the use cases it affects. */
export default function Decisions() {
  const [got, again] = useRead(getDecisions);
  const [kind, setKind] = useState<"all" | DecisionRow["kind"]>("all");
  if (got.state === "loading") return <p className="v3-mute" role="status">Reading the decisions and rules</p>;
  if (got.state === "error") return <Failed message={got.message} again={again} />;
  const d = got.data;
  const rows = d.items.filter((i) => kind === "all" || i.kind === kind);
  const count = (k: "all" | DecisionRow["kind"]) => (k === "all" ? d.items.length : d.counts[k]);
  return (
    <section className="kx" aria-label="Decisions and rules">
      <div className="km-head">
        <h2>Decisions and rules</h2>
        <div className="kg-pills" role="group" aria-label="Filter by kind">
          {KINDS.map(([k, l]) => <button key={k} type="button" aria-pressed={kind === k} onClick={() => setKind(k)}>{l} {"·"} {count(k)}</button>)}
        </div>
      </div>
      <p className="kd-intro">What the office has signed, decided or assumed, and which use cases each one affects. Rules are signed by a person and versioned; assumptions are what Harbor was told or had to take as read.</p>
      {rows.length === 0 && <div className="v3-card"><p>Nothing of this kind yet.</p></div>}
      <ul className="kx-list">
        {rows.map((i) => (
          <li key={i.id} className="kx-item">
            <div className="kx-top"><span className={`kx-kind ${i.kind}`}>{NAME[i.kind]}</span><b>{i.label}</b><span className="v3-mute">{i.sub}</span></div>
            {i.detail.filter((x) => x.k === "What it says" || x.k === "What I assumed" || x.k === "Question in the brief" || x.k === "What was said").slice(0, 1).map((x) => <p key={x.k} className="kx-text">{x.v}</p>)}
            <p className="kx-uses">{i.usecases.length ? <><b>Affects:</b> {i.usecases.map((u, n) => <span key={u.id}>{n ? ", " : ""}<Link to={`/v3/knowledge?tab=usecases&uc=${encodeURIComponent(u.id)}`}>{u.title}</Link></span>)}</> : <span className="v3-mute">No use case reads it yet.</span>}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
