import type { KEdge, KNode, Kind } from "./api";

/** Columns by kind, left to right: who, what they hold, where data comes from, what is measured, what is built, what is decided. */
const COLS: Kind[][] = [["person"], ["entity"], ["fund"], ["source", "file"], ["figure"], ["usecase"], ["decision"]];
const W = 150, H = 30, GX = 70, GY = 14, PAD = 12;
export const KIND_LABEL: Record<Kind, string> = { person: "People", entity: "Entities", fund: "Funds", source: "Sources", file: "Files", figure: "Figures", usecase: "Use cases", decision: "Decisions" };
export const KIND_ONE: Record<Kind, string> = { person: "Person", entity: "Entity", fund: "Fund", source: "Source", file: "File", figure: "Figure", usecase: "Use case", decision: "Decision" };
/** Quiet tints by kind with slate (info) borders; status overrides: a live use case is done, one being built is Harbor's, a decision waiting needs a person. */
export function look(n: KNode): { fill: string; stroke: string; dash?: string; tag?: string } {
  if (n.kind === "usecase") return n.stage === "live" ? { fill: "var(--done-soft)", stroke: "var(--done)", tag: "Live" } : { fill: "var(--harbor-soft)", stroke: "var(--harbor)", dash: "4 3", tag: "Being built" };
  if (n.kind === "decision" && n.waiting) return { fill: "var(--needs-soft)", stroke: "var(--needs)", tag: "Waiting" };
  if (n.kind === "source" || n.kind === "file") return { fill: "var(--paper)", stroke: "var(--info)", dash: "4 3" };
  if (n.kind === "entity" || n.kind === "fund") return { fill: "var(--info-soft)", stroke: "var(--info)" };
  return { fill: "var(--card)", stroke: "var(--info)" };
}
const cut = (s: string) => (s.length > 22 ? s.slice(0, 21) + "..." : s);

/** Deterministic layout: the same records always give the same picture. */
export function layout(nodes: KNode[]): { pos: Map<string, { x: number; y: number }>; w: number; h: number } {
  const pos = new Map<string, { x: number; y: number }>();
  let x = PAD, h = 0;
  for (const kinds of COLS) {
    const col = nodes.filter((n) => kinds.includes(n.kind)).sort((a, b) => a.label.localeCompare(b.label) || a.id.localeCompare(b.id));
    if (!col.length) continue;
    col.forEach((n, i) => pos.set(n.id, { x, y: PAD + i * (H + GY) }));
    h = Math.max(h, PAD * 2 + col.length * (H + GY) - GY);
    x += W + GX;
  }
  return { pos, w: x - GX + PAD, h };
}

interface Props { nodes: KNode[]; edges: KEdge[]; query: string; selected: string | null; onSelect: (id: string) => void }

export default function Graph({ nodes, edges, query, selected, onSelect }: Props) {
  const { pos, w, h } = layout(nodes);
  const q = query.trim().toLowerCase();
  const hit = (n: KNode) => !q || n.label.toLowerCase().includes(q) || n.facts.some((f) => f.text.toLowerCase().includes(q));
  const on = new Set(nodes.filter(hit).map((n) => n.id));
  const near = (e: KEdge) => selected === e.from || selected === e.to;
  return (
    <div className="kg-scroll">
      <svg width="100%" style={{ maxWidth: w, height: "auto" }} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="xMinYMin meet" role="group" aria-label="Knowledge map">
        <defs><marker id="kg-arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" style={{ fill: "var(--info)" }} /></marker></defs>
        {edges.map((e, i) => {
          const a = pos.get(e.from), b = pos.get(e.to);
          if (!a || !b) return null;
          const fwd = a.x < b.x, x1 = a.x + (fwd ? W : 0), x2 = b.x + (fwd ? 0 : W), y1 = a.y + H / 2, y2 = b.y + H / 2;
          const same = a.x === b.x, mx = (x1 + x2) / 2 + (same ? W / 2 + 14 : 0), my = (y1 + y2) / 2;
          const d = same ? `M${x1} ${y1}C${x1 + W / 2 + 40} ${y1} ${x1 + W / 2 + 40} ${y2} ${x1} ${y2}` : `M${x1} ${y1}L${x2} ${y2}`;
          const lit = on.has(e.from) && on.has(e.to);
          return (
            <g key={i} opacity={q && !lit ? 0.12 : near(e) || !selected ? 1 : 0.35}>
              <path d={d} fill="none" style={{ stroke: near(e) ? "var(--act)" : "var(--info)" }} strokeWidth={near(e) ? 2 : 1.2} markerEnd="url(#kg-arr)" />
              <text x={mx} y={my - 3} fontSize="10" textAnchor="middle" style={{ fill: "var(--info)", stroke: "var(--card)" }} strokeWidth="3" paintOrder="stroke">{e.label}</text>
            </g>
          );
        })}
        {nodes.map((n) => {
          const p = pos.get(n.id);
          if (!p) return null;
          const c = look(n), sel = selected === n.id, mark = sel || (!!q && on.has(n.id));
          return (
            <g key={n.id} transform={`translate(${p.x} ${p.y})`} tabIndex={0} role="button" aria-label={`${KIND_ONE[n.kind]}: ${n.label}`} aria-pressed={sel}
              opacity={q && !on.has(n.id) ? 0.2 : 1} style={{ cursor: "pointer" }} onClick={() => onSelect(n.id)}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(n.id); } }}>
              <rect width={W} height={H} rx={8} style={{ fill: sel ? "var(--act-soft)" : c.fill, stroke: mark ? "var(--act)" : c.stroke }} strokeWidth={mark ? 2.5 : 1.2} strokeDasharray={mark ? undefined : c.dash} />
              <text x={W / 2} y={H / 2 + 4} fontSize="12" textAnchor="middle" style={{ fill: sel ? "var(--act)" : "var(--ink)" }} fontWeight={sel ? 600 : 400}>{cut(n.label)}</text>
              <title>{c.tag ? `${n.label} (${c.tag})` : n.label}</title>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
