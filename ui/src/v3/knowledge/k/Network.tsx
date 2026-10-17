import { forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY } from "d3-force";
import { useMemo, useState } from "react";

import type { KEdge, KNode, Kind } from "./api";
import { KIND_LABEL, KIND_ONE, KINDS, kindColour, neighbours } from "./kinds";

const W = 1000, H = 640, R = 230;
interface P { id: string; x: number; y: number; r: number }
interface S { id: string; kind: Kind; r: number; x: number; y: number }

/** The same records always give the same picture: d3-force starts from its fixed spiral and runs a fixed number of steps, pulled to a place per kind. */
export function forceLayout(nodes: KNode[], edges: KEdge[]): { pos: Map<string, P>; centres: Map<Kind, { x: number; y: number }> } {
  const kinds = KINDS.filter((k) => nodes.some((n) => n.kind === k));
  const centres = new Map(kinds.map((k, i) => [k, { x: W / 2 + R * 1.25 * Math.cos((i / kinds.length) * 2 * Math.PI - Math.PI / 2), y: H / 2 + R * 0.95 * Math.sin((i / kinds.length) * 2 * Math.PI - Math.PI / 2) }]));
  const deg = new Map<string, number>();
  for (const e of edges) for (const id of [e.from, e.to]) deg.set(id, (deg.get(id) ?? 0) + 1);
  const sim: S[] = nodes.map((n) => ({ id: n.id, kind: n.kind, r: 4 + Math.min(9, Math.sqrt(deg.get(n.id) ?? 0) * 1.6), x: 0, y: 0 }));
  const ids = new Set(nodes.map((n) => n.id));
  const links = edges.filter((e) => ids.has(e.from) && ids.has(e.to)).map((e) => ({ source: e.from, target: e.to }));
  const f = forceSimulation<S>(sim).stop()
    .force("link", forceLink<S, { source: string; target: string }>(links).id((d) => d.id).distance(34).strength(0.15))
    .force("charge", forceManyBody<S>().strength(-26))
    .force("x", forceX<S>((d) => centres.get(d.kind)?.x ?? W / 2).strength(0.16))
    .force("y", forceY<S>((d) => centres.get(d.kind)?.y ?? H / 2).strength(0.16))
    .force("hit", forceCollide<S>((d) => d.r + 1.5));
  f.tick(260);
  return { pos: new Map(sim.map((d) => [d.id, { id: d.id, x: Math.max(14, Math.min(W - 14, d.x)), y: Math.max(14, Math.min(H - 14, d.y)), r: d.r }])), centres };
}

interface Props { nodes: KNode[]; edges: KEdge[]; query: string; selected: string | null; onSelect: (id: string) => void; legend?: boolean }

/** View 1, Network: a map clustered by kind. Hover a dot to light its neighbours; click to focus it. */
export default function Network({ nodes, edges, query, selected, onSelect, legend = true }: Props) {
  const { pos, centres } = useMemo(() => forceLayout(nodes, edges), [nodes, edges]);
  const [hover, setHover] = useState<string | null>(null);
  const focus = hover ?? selected;
  const lit = useMemo(() => (focus ? neighbours(edges, focus) : null), [edges, focus]);
  const q = query.trim().toLowerCase();
  const hit = (n: KNode) => !q || n.label.toLowerCase().includes(q) || n.facts.some((f) => f.text.toLowerCase().includes(q));
  const dim = (id: string, n: KNode) => (lit ? !lit.has(id) : false) || !hit(n);
  return (
    <div className="kg-scroll">
      <svg className="kg-net" viewBox={`0 0 ${W} ${H}`} role="group" aria-label="Network map">
        {[...centres].map(([k, c]) => <text key={k} x={c.x} y={c.y - 46} textAnchor="middle" fontSize="12" className="kg-cluster">{KIND_LABEL[k]}</text>)}
        {edges.map((e, i) => {
          const a = pos.get(e.from), b = pos.get(e.to);
          if (!a || !b) return null;
          const on = lit && lit.has(e.from) && lit.has(e.to) && (e.from === focus || e.to === focus);
          return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} style={{ stroke: on ? "var(--act)" : "var(--line-2)" }} strokeWidth={on ? 1.6 : 0.6} opacity={lit ? (on ? 1 : 0.12) : 0.5} />;
        })}
        {nodes.map((n) => {
          const p = pos.get(n.id);
          if (!p) return null;
          const sel = selected === n.id, shown = focus === n.id || sel || (!!lit && lit.size <= 9 && lit.has(n.id));  // a crowd of neighbours is not all named
          return (
            <g key={n.id} tabIndex={0} role="button" aria-label={`${KIND_ONE[n.kind]}: ${n.label}`} aria-pressed={sel} opacity={dim(n.id, n) ? 0.18 : 1} style={{ cursor: "pointer" }}
              onMouseEnter={() => setHover(n.id)} onMouseLeave={() => setHover(null)} onFocus={() => setHover(n.id)} onBlur={() => setHover(null)} onClick={() => onSelect(n.id)}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(n.id); } }}>
              <circle cx={p.x} cy={p.y} r={sel ? p.r + 3 : p.r} style={{ fill: kindColour(n.kind), stroke: sel ? "var(--act)" : "var(--card)" }} strokeWidth={sel ? 3 : 1} />
              {shown && <text x={p.x} y={p.y - p.r - 5} textAnchor="middle" fontSize="12" className="kg-tip">{n.label.length > 30 ? n.label.slice(0, 29) + "..." : n.label}</text>}
              <title>{n.label}</title>
            </g>
          );
        })}
      </svg>
      {legend && <Legend nodes={nodes} />}
    </div>
  );
}

export function Legend({ nodes }: { nodes: KNode[] }) {
  return (
    <ul className="kg-key" aria-label="Colours">
      {KINDS.filter((k) => nodes.some((n) => n.kind === k)).map((k) => <li key={k}><i style={{ background: kindColour(k) }} />{KIND_LABEL[k]} {nodes.filter((n) => n.kind === k).length}</li>)}
    </ul>
  );
}
