import { useMemo, useState } from "react";

import type { KEdge, KNode } from "./api";
import { KIND_ONE, byId, kindColour } from "./kinds";
import { dependencies, ties } from "./people";

const W = 1100, H = 640, CX = 550, CY = 320, R1 = 120, R2 = 225;
const cut = (s: string, n = 24) => (s.length > n ? s.slice(0, n - 1) + "..." : s);
const at = (i: number, n: number, r: number) => { const a = (i / Math.max(1, n)) * 2 * Math.PI - Math.PI / 2 + 0.3; return { x: CX + r * Math.cos(a), y: CY + r * Math.sin(a), left: Math.cos(a) < 0 }; };

interface Props { nodes: KNode[]; edges: KEdge[]; selected: string | null; onSelect: (id: string) => void }

/** View 3, Person-centred: pick a person; around them what they ask and sign, the figures and signals that reach them, and whom they depend on. */
export default function PersonMap({ nodes, edges, selected, onSelect }: Props) {
  const t = useMemo(() => ties(nodes, edges), [nodes, edges]);
  const by = byId(nodes);
  const richest = [...t.people].sort((a, b) => (t.ties.get(b.id)?.size ?? 0) - (t.ties.get(a.id)?.size ?? 0) || a.label.localeCompare(b.label))[0];
  const [mine, setMine] = useState<string | null>(null);
  const pid = (selected && by.get(selected)?.kind === "person" ? selected : mine) ?? richest?.id ?? "";
  const me = by.get(pid);
  const m = useMemo(() => {
    const c = t.casesOf.get(pid), cases = [...new Set([...(c?.asks ?? []), ...(c?.reads ?? []), ...(c?.decides ?? [])])].filter((u) => by.has(u));
    const signals = edges.filter((e) => e.label === "goes to" && e.to === pid).map((e) => e.from);
    const figs = new Set<string>([...(t.ties.get(pid)?.keys() ?? [])]);
    const links: [string, string][] = [];
    for (const u of cases) for (const f of t.figsOf(u)) { figs.add(f); links.push([u, f]); }
    for (const e of edges) if (e.label === "watches" && signals.includes(e.from) && by.get(e.to)?.kind === "figure") { figs.add(e.to); links.push([e.from, e.to]); }
    const inner = [...cases, ...signals], outer = [...figs].filter((f) => by.has(f));
    const pos = new Map<string, { x: number; y: number; left: boolean }>();
    inner.forEach((id, i) => pos.set(id, at(i, inner.length, R1)));
    outer.forEach((id, i) => pos.set(id, at(i, outer.length, R2)));
    return { inner, outer, links: links.filter(([a, b]) => pos.has(a) && pos.has(b)), pos, dep: dependencies(nodes, edges, pid) };
  }, [t, pid, edges, nodes, by]);
  if (!t.people.length || !me) return <p className="v3-mute">No people to centre on yet.</p>;
  const one = (id: string, x: number, y: number, left: boolean, r: number) => {
    const n = by.get(id);
    if (!n) return null;
    return (
      <g key={id} tabIndex={0} role="button" aria-label={`${KIND_ONE[n.kind]}: ${n.label}`} aria-pressed={selected === id} style={{ cursor: "pointer" }} onClick={() => onSelect(id)}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(id); } }}>
        <circle cx={x} cy={y} r={r} style={{ fill: kindColour(n.kind), stroke: selected === id ? "var(--act)" : "var(--card)" }} strokeWidth={selected === id ? 3 : 1.5} />
        <text x={x + (left ? -r - 5 : r + 5)} y={y + 4} textAnchor={left ? "end" : "start"} fontSize="12" style={{ fill: "var(--ink)" }}>{cut(n.label)}</text>
        <title>{n.label}</title>
      </g>
    );
  };
  const side = (ids: string[], x: number, title: string, left: boolean) => (
    <g>
      <text x={left ? x : x} y={30} fontSize="12" textAnchor={left ? "start" : "end"} className="kg-cluster">{title}</text>
      {ids.length === 0 && <text x={x} y={56} fontSize="12" textAnchor={left ? "start" : "end"} style={{ fill: "var(--mute)" }}>No one yet</text>}
      {ids.map((id, i) => one(id, left ? x + 6 : x - 6, 58 + i * 34, !left, 6))}
    </g>
  );
  return (
    <div>
      <label className="kg-pick">Centre on{" "}
        <select value={pid} onChange={(e) => { setMine(e.target.value); onSelect(e.target.value); }}>
          {t.people.slice().sort((a, b) => a.label.localeCompare(b.label)).map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
        </select>
      </label>
      <div className="kg-scroll">
        <svg className="kg-radial" viewBox={`0 0 ${W} ${H}`} role="group" aria-label={`Map around ${me.label}`}>
          <circle cx={CX} cy={CY} r={R1} fill="none" style={{ stroke: "var(--line)" }} strokeDasharray="3 5" />
          <circle cx={CX} cy={CY} r={R2} fill="none" style={{ stroke: "var(--line)" }} strokeDasharray="3 5" />
          <text x={CX} y={CY - R1 - 8} textAnchor="middle" fontSize="11" className="kg-cluster">What they ask, and signals to them</text>
          <text x={CX} y={CY - R2 - 8} textAnchor="middle" fontSize="11" className="kg-cluster">Figures that reach them</text>
          {m.links.map(([a, b], i) => { const p = m.pos.get(a), q = m.pos.get(b); return p && q ? <line key={i} x1={p.x} y1={p.y} x2={q.x} y2={q.y} style={{ stroke: "var(--line-2)" }} strokeWidth="1" /> : null; })}
          {m.inner.map((id) => { const p = m.pos.get(id); return p ? <line key={id} x1={CX} y1={CY} x2={p.x} y2={p.y} style={{ stroke: "var(--act)" }} strokeWidth="1.2" opacity="0.5" /> : null; })}
          <g><circle cx={CX} cy={CY} r={30} style={{ fill: "var(--act)" }} /><text x={CX} y={CY + 4} textAnchor="middle" fontSize="12" fontWeight="600" style={{ fill: "var(--on-fill)" }}>{cut(me.label, 12)}</text></g>
          {m.inner.map((id) => { const p = m.pos.get(id); return p ? one(id, p.x, p.y, p.left, 7) : null; })}
          {m.outer.map((id) => { const p = m.pos.get(id); return p ? one(id, p.x, p.y, p.left, 6) : null; })}
          {side(m.dep.on, 10, "Depends on", true)}
          {side(m.dep.by, W - 10, "Relied on by", false)}
        </svg>
      </div>
      {!m.inner.length && <p className="v3-mute">{me.label} has no use case or signal in the records yet.</p>}
    </div>
  );
}
