import { useMemo, useState } from "react";

import type { KEdge, KNode } from "./api";
import { byId, kindColour, KIND_ONE } from "./kinds";
import { dependencies, ties } from "./people";

const W = 1100, H = 640, CX = 550, CY = 320, R1 = 120, R2 = 225;
/** Most shown on each ring and in each side list, most connected first. The rest sit behind a "+N more" list. */
export const INNER = 8, OUTER = 12, SIDE = 10;
const cut = (s: string, n = 26) => (s.length > n ? s.slice(0, n - 1) + "..." : s);
const at = (i: number, n: number, r: number) => { const a = (i / Math.max(1, n)) * 2 * Math.PI - Math.PI / 2 + 0.3; return { x: CX + r * Math.cos(a), y: CY + r * Math.sin(a), left: Math.cos(a) < 0 }; };

export interface Box { x0: number; x1: number; y0: number; y1: number }
/** Where a label's text sits, given its dot. Estimated from the character count (12px type). */
const boxOf = (x: number, y: number, left: boolean, r: number, text: string): Box => {
  const w = text.length * 6.6, x0 = left ? x - r - 5 - w : x + r + 5;
  return { x0, x1: x0 + w, y0: y - 8, y1: y + 5 };
};
const hits = (a: Box, b: Box) => a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1;
const titleBox = (text: string, x: number, y: number, anchor: "start" | "middle" | "end"): Box => {
  const w = text.length * 6.2, x0 = anchor === "start" ? x : anchor === "end" ? x - w : x - w / 2;
  return { x0, x1: x0 + w, y0: y - 9, y1: y + 3 };
};

export interface Mark { id: string; x: number; y: number; left: boolean; r: number; label: string | null }
export type Ties = ReturnType<typeof ties>;
export interface PersonLayout {
  inner: Mark[];
  outer: Mark[];
  sideOn: Mark[];
  sideBy: Mark[];
  more: { inner: string[]; outer: string[]; on: string[]; by: string[] };
  links: [string, string][];
  pos: Map<string, { x: number; y: number }>;
  /** Every label drawn, with its box: no two of them overlap. */
  boxes: { id: string; box: Box }[];
}

/** The map around one person: the top items on each ring, placed; a label is drawn only where it clears every label and title before it. */
export function personLayout(nodes: KNode[], edges: KEdge[], t: Ties, pid: string): PersonLayout {
  const by = byId(nodes), label = (id: string) => by.get(id)?.label ?? id;
  const c = t.casesOf.get(pid);
  const cases = [...new Set([...(c?.asks ?? []), ...(c?.reads ?? []), ...(c?.decides ?? [])])].filter((u) => by.has(u));
  const signals = edges.filter((e) => e.label === "goes to" && e.to === pid).map((e) => e.from);
  const figs = new Set<string>(t.ties.get(pid)?.keys() ?? []);
  const links: [string, string][] = [];
  for (const u of cases) for (const f of t.figsOf(u)) { figs.add(f); links.push([u, f]); }
  for (const e of edges) if (e.label === "watches" && signals.includes(e.from) && by.get(e.to)?.kind === "figure") { figs.add(e.to); links.push([e.from, e.to]); }
  const deg = new Map<string, number>();
  for (const e of edges) for (const id of [e.from, e.to]) deg.set(id, (deg.get(id) ?? 0) + 1);
  const rank = (a: string, b: string) => (deg.get(b) ?? 0) - (deg.get(a) ?? 0) || label(a).localeCompare(label(b));
  const innerAll = [...cases, ...signals].sort(rank), outerAll = [...figs].filter((f) => by.has(f)).sort(rank);
  const innerIds = innerAll.slice(0, INNER), outerIds = outerAll.slice(0, OUTER);
  const dep = dependencies(nodes, edges, pid);
  const onIds = dep.on.slice(0, SIDE), byIds = dep.by.slice(0, SIDE);

  const mark = (id: string, i: number, n: number, r: number, dot: number): Mark => { const p = at(i, n, r); return { id, x: p.x, y: p.y, left: p.left, r: dot, label: null }; };
  const inner = innerIds.map((id, i) => mark(id, i, innerIds.length, R1, 7));
  const outer = outerIds.map((id, i) => mark(id, i, outerIds.length, R2, 6));
  const sideOn: Mark[] = onIds.map((id, i) => ({ id, x: 16, y: 58 + i * 34, left: false, r: 6, label: cut(label(id), 22) }));
  const sideBy: Mark[] = byIds.map((id, i) => ({ id, x: W - 16, y: 58 + i * 34, left: true, r: 6, label: cut(label(id), 22) }));

  const boxes: { id: string; box: Box }[] = [];
  const taken: Box[] = [
    { x0: CX - 30, x1: CX + 30, y0: CY - 30, y1: CY + 30 },
    titleBox("What they ask, and signals to them", CX, CY - R1 - 8, "middle"),
    titleBox("Figures that reach them", CX, CY - R2 - 8, "middle"),
    titleBox("Depends on", 10, 30, "start"),
    titleBox("Relied on by", W - 10, 30, "end"),
  ];
  for (const m of [...sideOn, ...sideBy]) {
    const box = boxOf(m.x, m.y, m.left, m.r, m.label ?? "");
    taken.push(box);
    boxes.push({ id: m.id, box });
  }
  for (const m of [...inner, ...outer]) {
    const text = cut(label(m.id));
    const box = boxOf(m.x, m.y, m.left, m.r, text);
    if (taken.some((b) => hits(b, box))) continue;
    taken.push(box);
    boxes.push({ id: m.id, box });
    m.label = text;
  }
  const pos = new Map<string, { x: number; y: number }>();
  for (const m of [...inner, ...outer]) pos.set(m.id, { x: m.x, y: m.y });
  return {
    inner, outer, sideOn, sideBy, boxes, pos,
    more: { inner: innerAll.slice(INNER), outer: outerAll.slice(OUTER), on: dep.on.slice(SIDE), by: dep.by.slice(SIDE) },
    links: links.filter(([a, b]) => pos.has(a) && pos.has(b)),
  };
}

interface Props { nodes: KNode[]; edges: KEdge[]; selected: string | null; onSelect: (id: string) => void }

/** View 3, Person-centred: pick a person; around them what they ask and sign, the figures and signals that reach them, and whom they depend on. */
export default function PersonMap({ nodes, edges, selected, onSelect }: Props) {
  const t = useMemo(() => ties(nodes, edges), [nodes, edges]);
  const by = byId(nodes);
  const richest = [...t.people].sort((a, b) => (t.ties.get(b.id)?.size ?? 0) - (t.ties.get(a.id)?.size ?? 0) || a.label.localeCompare(b.label))[0];
  const [mine, setMine] = useState<string | null>(null);
  const pid = (selected && by.get(selected)?.kind === "person" ? selected : mine) ?? richest?.id ?? "";
  const me = by.get(pid);
  const L = useMemo(() => personLayout(nodes, edges, t, pid), [nodes, edges, t, pid]);
  if (!t.people.length || !me) return <p className="v3-mute">No people to centre on yet.</p>;
  const one = (m: Mark) => {
    const n = by.get(m.id);
    if (!n) return null;
    return (
      <g key={m.id} tabIndex={0} role="button" aria-label={`${KIND_ONE[n.kind]}: ${n.label}`} aria-pressed={selected === m.id} style={{ cursor: "pointer" }} onClick={() => onSelect(m.id)}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(m.id); } }}>
        <circle cx={m.x} cy={m.y} r={m.r} style={{ fill: kindColour(n.kind), stroke: selected === m.id ? "var(--act)" : "var(--card)" }} strokeWidth={selected === m.id ? 3 : 1.5} />
        {m.label && <text x={m.x + (m.left ? -m.r - 5 : m.r + 5)} y={m.y + 4} textAnchor={m.left ? "end" : "start"} fontSize="12" style={{ fill: "var(--ink)" }}>{m.label}</text>}
        <title>{n.label}</title>
      </g>
    );
  };
  const More = ({ ids, what }: { ids: string[]; what: string }) => (ids.length === 0 ? null : (
    <details className="kg-more">
      <summary>+{ids.length} more {what}</summary>
      <ul>{ids.map((id) => <li key={id}><button type="button" onClick={() => onSelect(id)}>{by.get(id)?.label ?? id}</button></li>)}</ul>
    </details>
  ));
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
          {L.links.map(([a, b], i) => { const p = L.pos.get(a), q = L.pos.get(b); return p && q ? <line key={i} x1={p.x} y1={p.y} x2={q.x} y2={q.y} style={{ stroke: "var(--line-2)" }} strokeWidth="1" /> : null; })}
          {L.inner.map((m) => <line key={m.id} x1={CX} y1={CY} x2={m.x} y2={m.y} style={{ stroke: "var(--act)" }} strokeWidth="1.2" opacity="0.5" />)}
          <g><circle cx={CX} cy={CY} r={30} style={{ fill: "var(--act)" }} /><text x={CX} y={CY + 4} textAnchor="middle" fontSize="12" fontWeight="600" style={{ fill: "var(--on-fill)" }}>{cut(me.label, 12)}</text></g>
          {L.inner.map(one)}
          {L.outer.map(one)}
          <text x={10} y={30} fontSize="12" className="kg-cluster">Depends on</text>
          {L.sideOn.length === 0 && <text x={10} y={56} fontSize="12" style={{ fill: "var(--mute)" }}>No one yet</text>}
          {L.sideOn.map(one)}
          <text x={W - 10} y={30} fontSize="12" textAnchor="end" className="kg-cluster">Relied on by</text>
          {L.sideBy.length === 0 && <text x={W - 10} y={56} fontSize="12" textAnchor="end" style={{ fill: "var(--mute)" }}>No one yet</text>}
          {L.sideBy.map(one)}
        </svg>
      </div>
      <More ids={L.more.inner} what="asks and signals" />
      <More ids={L.more.outer} what="figures that reach them" />
      <More ids={L.more.on} what="people depended on" />
      <More ids={L.more.by} what="people relying on them" />
      {!L.inner.length && <p className="v3-mute">{me.label} has no use case or signal in the records yet.</p>}
    </div>
  );
}
