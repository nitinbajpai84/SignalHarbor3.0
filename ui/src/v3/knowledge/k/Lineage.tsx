import { useMemo } from "react";

import type { KEdge, KNode } from "./api";
import { KIND_LABEL, KIND_ONE, STEPS, byId, flowLinks, kindColour } from "./kinds";

const CW = 160, GAP = 100, NH = 22, NG = 8, TOP = 34, PAD = 10;

/** Walk the flow both ways from a node: everything it rests on and everything it feeds. */
export function pathOf(links: { from: string; to: string }[], id: string): Set<string> {
  const seen = new Set<string>([id]);
  for (const dir of ["up", "down"] as const) {
    const stack = [id];
    while (stack.length) {
      const x = stack.pop() as string;
      for (const l of links) {
        const [a, b] = dir === "down" ? [l.from, l.to] : [l.to, l.from];
        if (a === x && !seen.has(b)) { seen.add(b); stack.push(b); }
      }
    }
  }
  return seen;
}

interface Props { nodes: KNode[]; edges: KEdge[]; selected: string | null; onSelect: (id: string) => void }

/** View 2, Lineage flow: files, sources, figures, use cases and people left to right as bands. Pick a figure to see its whole path. */
export default function Lineage({ nodes, edges, selected, onSelect }: Props) {
  const m = useMemo(() => {
    const links = flowLinks(nodes, edges), used = new Set(links.flatMap((l) => [l.from, l.to]));
    const cols = STEPS.map((k) => nodes.filter((n) => n.kind === k && used.has(n.id)).sort((a, b) => a.label.localeCompare(b.label)));
    const deg = new Map<string, number>();
    for (const l of links) for (const id of [l.from, l.to]) deg.set(id, (deg.get(id) ?? 0) + 1);
    const pos = new Map<string, { x: number; y: number; h: number }>();
    let h = 0;
    cols.forEach((col, c) => {
      let y = TOP;
      for (const n of col) { const nh = Math.max(NH, Math.min(70, NH + (deg.get(n.id) ?? 1) * 3)); pos.set(n.id, { x: PAD + c * (CW + GAP), y, h: nh }); y += nh + NG; }
      h = Math.max(h, y);
    });
    return { links, cols, pos, w: PAD * 2 + STEPS.length * CW + (STEPS.length - 1) * GAP, h: h + PAD };
  }, [nodes, edges]);
  const path = useMemo(() => (selected ? pathOf(m.links, selected) : null), [m, selected]);
  const by = byId(nodes), figures = m.cols[2] ?? [];
  if (!m.links.length) return <p className="v3-mute">No flow to draw yet: it appears once files, sources, figures and use cases are joined.</p>;
  return (
    <div>
      <label className="kg-pick">Show the full path of{" "}
        <select value={by.get(selected ?? "")?.kind === "figure" ? selected ?? "" : ""} onChange={(e) => e.target.value && onSelect(e.target.value)}>
          <option value="">a figure...</option>
          {figures.map((f) => <option key={f.id} value={f.id}>{f.label}</option>)}
        </select>
      </label>
      <div className="kg-scroll">
        <svg width="100%" style={{ maxWidth: m.w, height: "auto" }} viewBox={`0 0 ${m.w} ${m.h}`} role="group" aria-label="Lineage flow" className="kg-flow">
          {STEPS.map((k, c) => <text key={k} x={PAD + c * (CW + GAP)} y={16} fontSize="12" className="kg-cluster">{KIND_LABEL[k]}</text>)}
          {m.links.map((l, i) => {
            const a = m.pos.get(l.from), b = m.pos.get(l.to);
            if (!a || !b) return null;
            const x1 = a.x + CW, x2 = b.x, mx = (x1 + x2) / 2;
            const on = path ? path.has(l.from) && path.has(l.to) : true;
            const d = `M${x1} ${a.y + a.h / 2}C${mx} ${a.y + a.h / 2} ${mx} ${b.y + b.h / 2} ${x2} ${b.y + b.h / 2}`;
            return <path key={i} d={d} fill="none" strokeWidth={on && path ? 4 : 3} style={{ stroke: on && path ? "var(--harbor)" : kindColour(by.get(l.from)?.kind ?? "file") }} opacity={path ? (on ? 0.9 : 0.06) : 0.3} />;
          })}
          {m.cols.flat().map((n) => {
            const p = m.pos.get(n.id);
            if (!p) return null;
            const sel = selected === n.id, on = !path || path.has(n.id);
            return (
              <g key={n.id} tabIndex={0} role="button" aria-label={`${KIND_ONE[n.kind]}: ${n.label}`} aria-pressed={sel} opacity={on ? 1 : 0.25} style={{ cursor: "pointer" }}
                onClick={() => onSelect(n.id)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(n.id); } }}>
                <rect x={p.x} y={p.y} width={CW} height={p.h} rx={6} style={{ fill: "var(--card)", stroke: sel ? "var(--act)" : kindColour(n.kind) }} strokeWidth={sel ? 3 : 1.4} />
                <text x={p.x + 8} y={p.y + p.h / 2 + 4} fontSize="12" style={{ fill: "var(--ink)" }}>{n.label.length > 24 ? n.label.slice(0, 23) + "..." : n.label}</text>
                <title>{n.label}</title>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
