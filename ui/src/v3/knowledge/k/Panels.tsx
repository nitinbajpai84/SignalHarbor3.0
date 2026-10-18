import { Link } from "react-router-dom";

import type { KEdge, KNode, Process, Thing } from "./api";
import { KIND_LABEL, KIND_ONE, look } from "./Graph";
import { thingPath } from "./kinds";

export function Side({ node, nodes, edges, onSelect }: { node: KNode | null; nodes: KNode[]; edges: KEdge[]; onSelect: (id: string) => void }) {
  if (!node) return <aside className="v3-card kg-side" aria-label="Selected"><p className="v3-mute">Click a box to see what is known about it and what it connects to.</p></aside>;
  const by = new Map(nodes.map((n) => [n.id, n]));
  const links = edges.filter((e) => e.from === node.id || e.to === node.id).map((e) => ({ e, other: by.get(e.from === node.id ? e.to : e.from), out: e.from === node.id }));
  return (
    <aside className="v3-card kg-side" aria-label="Selected">
      <span className="kg-kind">{KIND_ONE[node.kind]}<Tag n={node} /></span>
      <h2>{node.label}</h2>
      <p><Link className="kg-link" to={thingPath(node.id)}>Open full page</Link></p>
      <h3>What we know</h3>
      <Facts n={node} />
      <h3>Connected to</h3>
      {links.length ? <ul>{links.map(({ e, other, out }, i) => other && (
        <li key={i}><span className="v3-mute">{out ? e.label : `${e.label} (from)`}</span> <button type="button" className="kg-link" onClick={() => onSelect(other.id)}>{other.label}</button></li>))}</ul> : <p className="v3-mute">No links yet.</p>}
    </aside>
  );
}

const TAG: Record<string, string> = { Live: "done", "Being built": "harbor", Waiting: "needs", Suggested: "info" };
function Tag({ n }: { n: KNode }) {
  const t = look(n).tag;
  return t ? <span className={`v3-pill ${TAG[t]} kg-tag`}>{t}</span> : null;
}
const Facts = ({ n }: { n: KNode }) => (n.facts.length
  ? <ul>{n.facts.map((f, i) => <li key={i}>{f.text}<br /><span className="v3-mute">{f.source}{f.at ? `, ${f.at}` : ""}</span></li>)}</ul>
  : <p className="v3-mute">Nothing recorded yet.</p>);

/** Phone: the map as a searchable list grouped by kind; tapping an item opens its facts in place. */
export function PhoneList({ nodes, query, selected, onSelect }: { nodes: KNode[]; query: string; selected: string | null; onSelect: (id: string | null) => void }) {
  const q = query.trim().toLowerCase();
  const hit = (n: KNode) => !q || n.label.toLowerCase().includes(q) || n.facts.some((f) => f.text.toLowerCase().includes(q));
  const groups = (Object.keys(KIND_LABEL) as KNode["kind"][]).map((k) => [k, nodes.filter((n) => n.kind === k && hit(n)).sort((a, b) => a.label.localeCompare(b.label))] as const).filter(([, ns]) => ns.length);
  if (!groups.length) return <p className="v3-mute">Nothing matches that search.</p>;
  return <>{groups.map(([k, ns]) => (
    <section key={k} className="kg-group" aria-label={KIND_LABEL[k]}>
      <h2>{KIND_LABEL[k]} <span>{ns.length}</span></h2>
      <ul>{ns.map((n) => {
        const open = selected === n.id;
        return (
          <li key={n.id} className={open ? "on" : undefined}>
            <button type="button" aria-expanded={open} onClick={() => onSelect(open ? null : n.id)}><span>{n.label}</span><Tag n={n} /></button>
            {open && <div className="kg-facts"><Facts n={n} /><Link className="kg-link" to={thingPath(n.id)}>Open full page</Link></div>}
          </li>);
      })}</ul>
    </section>))}</>;
}

export function Processes({ items }: { items: Process[] }) {
  if (!items.length) return <div className="v3-card"><p>No process is written down yet. When a brief with a process is signed, its swim lanes appear here.</p></div>;
  return <>{items.map((p, i) => (
    <section key={i} className="v3-card" aria-label={p.title}>
      <h2>{p.title}</h2>
      {p.lanes.map((l) => (
        <div key={l} className="kg-lane" role="group" aria-label={l}>
          <b>{l}</b>
          <ol>{p.steps.map((s, j) => s.lane === l && <li key={j} value={j + 1}>{s.text}</li>)}</ol>
        </div>))}
    </section>))}</>;
}

export function Things({ items }: { items: Thing[] }) {
  if (!items.length) return <div className="v3-card"><p>Nothing is tracked yet.</p></div>;
  return <div className="v3-chips kg-things">{items.map((t) => <span key={t.name}><b>{t.count}</b> {t.name}{t.new ? <em className="kg-new"> new this month</em> : null}</span>)}</div>;
}
