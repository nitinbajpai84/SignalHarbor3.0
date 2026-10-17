import { useMemo, useState } from "react";

import type { KEdge, KNode, Kind } from "./api";
import { KIND_LABEL, KIND_ONE, STEPS, byId, flowLinks, kindColour } from "./kinds";

const CW = 180, GAP = 70, NH = 26, BH = 30, FH = 22, MH = 18, NG = 6, TOP = 34, PAD = 10;
/** Most top-level rows a column shows, and most files an open source band lists. Anything beyond is "+N more". */
export const MAX = 12, EXPAND = 6;
const cut = (s: string, n: number) => (s.length > n ? s.slice(0, n - 3) + "..." : s);

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

/** One candidate row before placement. `covers` are the flow nodes it stands for; a collapsed band covers its files. */
export interface Raw { key: string; kind: Kind; label: string; full: string; covers: string[]; hit: boolean; band?: boolean; open?: boolean; count?: number; child?: boolean; more?: boolean }
export interface Row extends Raw { x: number; y: number; w: number; h: number }
export interface Column { kind: Kind; x: number; rows: Row[]; more: number; moreY: number }
export interface Flow {
  columns: Column[];
  links: { from: string; to: string; kind: Kind; on: boolean }[];
  pos: Map<string, Row>;
  path: Set<string> | null;
  figures: KNode[];
  w: number;
  h: number;
}

/** Keep whole groups in order: a group holding a path row is always kept; the rest fit under the limit, and the first that does not fit ends the list. Returns the kept rows and how many groups were left out. */
export function capGroups(groups: Raw[][], limit: number): { kept: Raw[]; more: number } {
  const kept: Raw[] = [];
  let more = 0, full = false;
  for (const g of groups) {
    if (g.some((r) => r.hit) || (!full && kept.length + g.length <= limit)) kept.push(...g);
    else { more += 1; full = true; }
  }
  return { kept, more };
}

/** The lineage flow as rows: each source is one band of its files (open on click, and open when a picked figure runs through it); each column holds at most MAX rows. */
export function lineageLayout(nodes: KNode[], edges: KEdge[], open: ReadonlySet<string>, selected: string | null): Flow {
  const by = byId(nodes), links = flowLinks(nodes, edges);
  const path = selected ? pathOf(links, selected) : null;
  const hit = (id: string) => !!path && path.has(id);
  const name = (id: string) => by.get(id)?.label ?? id;
  const used = new Set(links.flatMap((l) => [l.from, l.to]));
  const bySort = (a: string, b: string) => Number(hit(b)) - Number(hit(a)) || name(a).localeCompare(name(b));

  // each file sits under the first source it feeds, by name
  const sourceOf = new Map<string, string>();
  for (const l of links) {
    if (by.get(l.from)?.kind !== "file" || by.get(l.to)?.kind !== "source") continue;
    const cur = sourceOf.get(l.from);
    if (!cur || name(l.to).localeCompare(name(cur)) < 0) sourceOf.set(l.from, l.to);
  }
  const feeds = new Map<string, string[]>();
  for (const [f, s] of sourceOf) feeds.set(s, [...(feeds.get(s) ?? []), f]);
  const bands = [...feeds].map(([s, files]) => ({ s, files: files.sort(bySort), on: files.some(hit) }))
    .sort((a, b) => Number(b.on) - Number(a.on) || name(a.s).localeCompare(name(b.s)));
  const fileGroups: Raw[][] = bands.map(({ s, files, on }) => {
    const isOpen = open.has(`band:${s}`) || on;
    const title = `${name(s)} · ${files.length} ${files.length === 1 ? "file" : "files"}`;
    const shown = isOpen ? files.slice(0, EXPAND) : [];
    const g: Raw[] = [{ key: `band:${s}`, kind: "file", label: name(s), full: title, covers: files.filter((f) => !shown.includes(f)), hit: on, band: true, open: isOpen, count: files.length }];
    for (const f of shown) g.push({ key: f, kind: "file", label: name(f), full: name(f), covers: [f], hit: hit(f), child: true });
    if (isOpen && files.length > shown.length) g.push({ key: `more:${s}`, kind: "file", label: `+${files.length - shown.length} more files`, full: title, covers: [], hit: false, child: true, more: true });
    return g;
  });
  const oneKind = (kind: Kind): Raw[][] => [...used].filter((id) => by.get(id)?.kind === kind).sort(bySort)
    .map((id) => [{ key: id, kind, label: name(id), full: name(id), covers: [id], hit: hit(id) }]);
  const groups = STEPS.map((kind, c) => (c === 0 ? fileGroups : oneKind(kind)));

  const columns: Column[] = [], pos = new Map<string, Row>();
  let bottom = TOP;
  STEPS.forEach((kind, c) => {
    const { kept, more } = capGroups(groups[c] ?? [], MAX);
    const x = PAD + c * (CW + GAP);
    let y = TOP;
    const rows = kept.map((r) => {
      const h = r.band ? BH : r.more ? MH : r.child ? FH : NH;
      const row: Row = { ...r, x: x + (r.child ? 10 : 0), y, w: CW - (r.child ? 10 : 0), h };
      pos.set(row.key, row);
      y += h + NG;
      return row;
    });
    columns.push({ kind, x, rows, more, moreY: y });
    bottom = Math.max(bottom, y + (more ? 16 : 0));
  });

  const itemOf = new Map<string, string>();
  for (const col of columns) for (const r of col.rows) for (const id of r.covers) itemOf.set(id, r.key);
  const drawn = new Map<string, Flow["links"][number]>();
  for (const l of links) {
    const a = itemOf.get(l.from), b = itemOf.get(l.to);
    if (!a || !b || a === b) continue;
    const k = `${a}|${b}`;
    drawn.set(k, { from: a, to: b, kind: by.get(l.from)?.kind ?? "file", on: (hit(l.from) && hit(l.to)) || !!drawn.get(k)?.on });
  }
  const figures = nodes.filter((n) => n.kind === "figure" && used.has(n.id)).sort((a, b) => a.label.localeCompare(b.label));
  return { columns, links: [...drawn.values()], pos, path, figures, w: PAD * 2 + STEPS.length * CW + (STEPS.length - 1) * GAP, h: bottom + PAD };
}

interface Props { nodes: KNode[]; edges: KEdge[]; selected: string | null; onSelect: (id: string) => void }

/** View 2, Lineage flow: files, sources, figures, use cases and people left to right. Files group under their source; pick a figure to see its whole path. */
export default function Lineage({ nodes, edges, selected, onSelect }: Props) {
  const [open, setOpen] = useState<ReadonlySet<string>>(() => new Set());
  const flow = useMemo(() => lineageLayout(nodes, edges, open, selected), [nodes, edges, open, selected]);
  const by = byId(nodes);
  if (!flow.links.length) return <p className="v3-mute">No flow to draw yet: it appears once files, sources, figures and use cases are joined.</p>;
  const toggle = (k: string) => setOpen((s) => { const n = new Set(s); if (n.has(k)) n.delete(k); else n.add(k); return n; });
  return (
    <div>
      <label className="kg-pick">Show the full path of{" "}
        <select value={by.get(selected ?? "")?.kind === "figure" ? selected ?? "" : ""} onChange={(e) => e.target.value && onSelect(e.target.value)}>
          <option value="">a figure...</option>
          {flow.figures.map((f) => <option key={f.id} value={f.id}>{f.label}</option>)}
        </select>
      </label>
      <div className="kg-scroll">
        <svg width="100%" style={{ maxWidth: flow.w, height: "auto" }} viewBox={`0 0 ${flow.w} ${flow.h}`} role="group" aria-label="Lineage flow" className="kg-flow">
          {flow.columns.map((c) => <text key={c.kind} x={c.x} y={16} fontSize="12" className="kg-cluster">{KIND_LABEL[c.kind]}</text>)}
          {flow.links.map((l, i) => {
            const a = flow.pos.get(l.from), b = flow.pos.get(l.to);
            if (!a || !b) return null;
            const x1 = a.x + a.w, x2 = b.x, mx = (x1 + x2) / 2, ya = a.y + a.h / 2, yb = b.y + b.h / 2;
            const lit = !!flow.path && l.on;
            return <path key={i} d={`M${x1} ${ya}C${mx} ${ya} ${mx} ${yb} ${x2} ${yb}`} fill="none" strokeWidth={lit ? 4 : 3} style={{ stroke: lit ? "var(--harbor)" : kindColour(l.kind) }} opacity={flow.path ? (lit ? 0.9 : 0.06) : 0.3} />;
          })}
          {flow.columns.flatMap((c) => c.rows).map((r) => {
            if (r.more) return <text key={r.key} x={r.x + 6} y={r.y + r.h / 2 + 4} fontSize="11" style={{ fill: "var(--mute)" }}>{r.label}</text>;
            const sel = selected === r.key, dim = !!flow.path && !r.hit;
            const act = () => (r.band ? toggle(r.key) : onSelect(r.key));
            return (
              <g key={r.key} tabIndex={0} role="button" aria-label={r.band ? `${r.full}, ${r.open ? "expanded" : "collapsed"}` : `${KIND_ONE[r.kind]}: ${r.full}`} aria-expanded={r.band ? !!r.open : undefined} aria-pressed={r.band ? undefined : sel}
                opacity={dim ? 0.25 : 1} style={{ cursor: "pointer" }} onClick={act} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); act(); } }}>
                <rect x={r.x} y={r.y} width={r.w} height={r.h} rx={6} style={{ fill: "var(--card)", stroke: sel ? "var(--act)" : kindColour(r.kind) }} strokeWidth={sel ? 3 : r.band ? 2 : 1.4} />
                {r.band ? (
                  <>
                    <text x={r.x + 8} y={r.y + r.h / 2 + 4} fontSize="12" style={{ fill: "var(--mute)" }}>{r.open ? "▾" : "▸"}</text>
                    <text x={r.x + 20} y={r.y + r.h / 2 + 4} fontSize="12" style={{ fill: "var(--ink)" }}>{cut(r.label, 16)}</text>
                    <text x={r.x + r.w - 8} y={r.y + r.h / 2 + 4} textAnchor="end" fontSize="11" style={{ fill: "var(--mute)" }}>{r.count} {r.count === 1 ? "file" : "files"}</text>
                  </>
                ) : (
                  <text x={r.x + 8} y={r.y + r.h / 2 + 4} fontSize="12" style={{ fill: "var(--ink)" }}>{cut(r.label, r.child ? 24 : 26)}</text>
                )}
                <title>{r.full}</title>
              </g>
            );
          })}
          {flow.columns.filter((c) => c.more).map((c) => <text key={`more-${c.kind}`} x={c.x + 6} y={c.moreY + 12} fontSize="11" style={{ fill: "var(--mute)" }}>+{c.more} more</text>)}
        </svg>
      </div>
    </div>
  );
}
