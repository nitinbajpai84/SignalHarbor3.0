import { useMemo, useState } from "react";

import type { KEdge, KNode } from "./api";
import { ties } from "./people";

interface Props { nodes: KNode[]; edges: KEdge[]; selected: string | null; onSelect: (id: string) => void }
const MARKS = [["uses", "uses", "act"], ["signs", "signs", "done"], ["signal", "signal", "needs"]] as const;

/** View 4, Matrix: people against figures. Each cell says whether the person uses the figure, signs it, or receives a signal about it; an empty column is a gap. */
export default function Matrix({ nodes, edges, selected, onSelect }: Props) {
  const t = useMemo(() => ties(nodes, edges), [nodes, edges]);
  const [gaps, setGaps] = useState(false);
  const people = t.people.slice().sort((a, b) => a.label.localeCompare(b.label));
  const figures = t.figures.slice().sort((a, b) => a.label.localeCompare(b.label));
  const owners = (f: string) => people.filter((p) => { const x = t.ties.get(p.id)?.get(f); return x && (x.uses || x.signs || x.signal); });
  const noSigner = (f: string) => !people.some((p) => t.ties.get(p.id)?.get(f)?.signs);
  const shown = gaps ? figures.filter((f) => !owners(f.id).length || noSigner(f.id)) : figures;
  if (!people.length || !figures.length) return <p className="v3-mute">The matrix appears once the office has people and figures.</p>;
  return (
    <div>
      <div className="kg-mx-tools">
        <label><input type="checkbox" checked={gaps} onChange={(e) => setGaps(e.target.checked)} /> Show only figures with a gap (no one uses them, or no one signs them)</label>
        <ul className="kg-key" aria-label="Marks">{MARKS.map(([k, w, c]) => <li key={k}><i style={{ background: `var(--${c})` }} />{w === "uses" ? "Uses it" : w === "signs" ? "Signs it" : "Gets a signal about it"}</li>)}</ul>
      </div>
      <div className="kg-scroll">
        <table className="kg-mx">
          <thead>
            <tr>
              <th scope="col">Person</th>
              {shown.map((f) => (
                <th key={f.id} scope="col" className={selected === f.id ? "on" : undefined}>
                  <button type="button" onClick={() => onSelect(f.id)} title={f.label}>{f.label}</button>
                  {!owners(f.id).length ? <em>No one yet</em> : noSigner(f.id) ? <em>No signer</em> : null}
                </th>))}
            </tr>
          </thead>
          <tbody>
            {people.map((p) => (
              <tr key={p.id}>
                <th scope="row" className={selected === p.id ? "on" : undefined}><button type="button" onClick={() => onSelect(p.id)}>{p.label}</button></th>
                {shown.map((f) => {
                  const x = t.ties.get(p.id)?.get(f.id);
                  const said = MARKS.filter(([k]) => x?.[k]).map(([, w]) => (w === "uses" ? "uses it" : w === "signs" ? "signs it" : "gets a signal about it"));
                  return (
                    <td key={f.id} aria-label={said.length ? `${p.label} ${said.join(", ")}: ${f.label}` : `${p.label} and ${f.label}: nothing`}>
                      {MARKS.map(([k, w, c]) => x?.[k] && <span key={k} className={`v3-pill ${c}`}>{w}</span>)}
                    </td>);
                })}
              </tr>))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
