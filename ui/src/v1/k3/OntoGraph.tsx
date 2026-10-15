import { useEffect, useMemo, useRef, useState } from "react";

import type { OntoEdge, OntoNode, OntoType } from "./api";
import { GX, H, layout, layoutCompany, near, W, type Label } from "./onto";

// The company map, drawn as layers left to right. Solid border: verified. Dashed border: in progress. Every node is a button.
const ACCENT: Record<OntoType, string> = {
  person: "var(--ds-ink-soft)", agent: "var(--ds-teal-bright)", project: "var(--ds-teal-bright)", intent: "var(--ds-teal-bright)", source: "var(--ds-ink-muted)",
  table: "var(--ds-ink-muted)", definition: "var(--ds-amber)", dashboard: "var(--ds-teal-bright)", report: "var(--ds-teal-bright)", case: "var(--ds-red)", decision: "var(--ds-amber)",
};
const HEALTH: Record<string, string> = { ok: "var(--ds-teal-bright)", attention: "var(--ds-amber)", affected: "var(--ds-amber)" };
const clamp = (s: number) => Math.min(2.5, Math.max(0.5, s));
const short = (s: string, n: number) => (s.length > n ? s.slice(0, n - 1) + "…" : s);

export default function OntoGraph({ nodes, edges, columns, selected, onSelect, lit, fade, healthLens, company, path }: {
  nodes: OntoNode[]; edges: OntoEdge[]; columns: string[]; selected: string | null; onSelect: (id: string | null) => void;
  lit?: Set<string>; fade?: (n: OntoNode) => boolean; healthLens?: boolean;
  /** V6 (F1): the whole-company arrangement: people across the top, data in the middle, meaning below. */
  company?: boolean;
  /** DM2: with a pick, every node on the way up and down (the lineage); edges between them are lit, not only the pick's own. */
  path?: Set<string>;
}) {
  const L = useMemo(() => {
    if (company) return { ...layoutCompany(nodes, edges, columns), rows: true as const };
    const l = layout(nodes, edges);
    const labels: Label[] = l.columns.map((c, i) => ({ x: 16 + i * (W + GX), y: 14, text: columns[c] ?? "" }));
    return { ...l, labels, rows: false as const };
  }, [nodes, edges, columns, company]);
  const focus = selected && !path ? near(selected, edges) : null;
  // Zoom: the svg already fits the box (meet), so scale 1 at origin is "Fit". Zoom is a CSS transform on the inner layer; wheel with ctrl/cmd (also trackpad pinch) zooms at the cursor, drag pans.
  const box = useRef<HTMLDivElement>(null), drag = useRef<{ x: number; y: number; moved: boolean } | null>(null), moved = useRef(false);
  const [v, setV] = useState({ s: 1, x: 0, y: 0 });
  const zoomAt = (f: number, cx: number, cy: number) => setV((o) => { const s = clamp(o.s * f); const r = s / o.s; return { s, x: cx - (cx - o.x) * r, y: cy - (cy - o.y) * r }; });
  const zoomBtn = (f: number) => { const r = box.current?.getBoundingClientRect(); zoomAt(f, (r?.width ?? 0) / 2, (r?.height ?? 0) / 2); };
  useEffect(() => {
    const el = box.current; if (!el) return;
    const wheel = (e: WheelEvent) => {
      if (!e.ctrlKey && !e.metaKey) return;   // plain scroll still scrolls the page
      e.preventDefault();
      const r = el.getBoundingClientRect();
      zoomAt(Math.exp(-e.deltaY * 0.01), e.clientX - r.left, e.clientY - r.top);
    };
    el.addEventListener("wheel", wheel, { passive: false });
    return () => el.removeEventListener("wheel", wheel);
  }, []);
  const tool = { padding: "2px 10px", font: "inherit", cursor: "pointer", background: "var(--ds-surface)", color: "var(--ds-ink)", border: "1px solid var(--ds-line-2)", borderRadius: 8 } as const;
  return (
    <div className="ds-card" style={{ position: "relative", padding: 8 }}>
      <div role="group" aria-label="Zoom" style={{ position: "absolute", top: 12, right: 12, zIndex: 1, display: "flex", gap: 4 }}>
        <button type="button" style={tool} aria-label="Zoom in" onClick={() => zoomBtn(1.25)}>+</button>
        <button type="button" style={tool} aria-label="Zoom out" onClick={() => zoomBtn(0.8)}>−</button>
        <button type="button" style={tool} aria-label="Fit" onClick={() => setV({ s: 1, x: 0, y: 0 })}>Fit</button>
      </div>
      <div ref={box} style={{ overflow: "hidden", height: "calc(100vh - 300px)", minHeight: 360, touchAction: "none", cursor: v.s > 1 ? "grab" : undefined }}
        onPointerDown={(e) => { if (v.s > 1 && e.button === 0) { drag.current = { x: e.clientX, y: e.clientY, moved: false }; moved.current = false; } }}
        onPointerMove={(e) => { const d = drag.current; if (!d) return; const dx = e.clientX - d.x, dy = e.clientY - d.y; if (!d.moved && Math.abs(dx) + Math.abs(dy) < 4) return; d.moved = moved.current = true; d.x = e.clientX; d.y = e.clientY; setV((o) => ({ ...o, x: o.x + dx, y: o.y + dy })); }}
        onPointerUp={() => { drag.current = null; }} onPointerLeave={() => { drag.current = null; }}
        onClickCapture={(e) => { if (moved.current) { e.stopPropagation(); moved.current = false; } }}>
      <div data-testid="graph-zoom" style={{ width: "100%", height: "100%", transformOrigin: "0 0", transform: `translate(${v.x}px, ${v.y}px) scale(${v.s})` }}>
      <svg viewBox={`0 0 ${L.width} ${L.height}`} width="100%" height="100%" role="group" aria-label="Company graph" style={{ display: "block" }}>
        {L.labels.map((l, i) => <text key={`${l.text}-${i}`} x={l.x} y={l.y} fontSize={11} fill="var(--ds-ink-muted)" style={{ letterSpacing: 1, textTransform: "uppercase" }}>{l.text}</text>)}
        {edges.map((e) => {
          const a = L.placed.get(e.from), b = L.placed.get(e.to);
          if (!a || !b) return null;
          const across = L.rows && (a as { row?: number }).row !== (b as { row?: number }).row, down = b.y >= a.y;   // between rows the line leaves the bottom (or top) edge
          const fwd = !across && b.x > a.x;
          const x1 = across ? a.x + W / 2 : fwd ? a.x + W : a.x + W / 2, y1 = across ? (down ? a.y + H : a.y) : fwd ? a.y + H / 2 : a.y + H;
          const x2 = across ? b.x + W / 2 : fwd ? b.x : b.x + W / 2, y2 = across ? (down ? b.y : b.y + H) : fwd ? b.y + H / 2 : b.y;
          const mid = (x1 + x2) / 2, on = path ? !!selected && path.has(e.from) && path.has(e.to) : !!selected && (e.from === selected || e.to === selected), dim = (selected && !on) || (fade && (fade(a.n) || fade(b.n)));
          return (
            <g key={`${e.from}|${e.to}|${e.rel}`} opacity={dim ? 0.18 : 1}>
              <path d={across ? `M${x1},${y1} C${x1},${(y1 + y2) / 2} ${x2},${(y1 + y2) / 2} ${x2},${y2}` : fwd ? `M${x1},${y1} C${mid},${y1} ${mid},${y2} ${x2},${y2}` : `M${x1},${y1} C${x1},${y1 + 30} ${x2},${y2 - 30} ${x2},${y2}`} fill="none"
                stroke={on ? "var(--ds-teal-bright)" : "var(--ds-line-2)"} strokeWidth={on ? 2 : 1.2} strokeDasharray={e.state === "verified" ? undefined : "5 4"}>
                <title>{`${a.n.label} ${e.rel} ${b.n.label}`}</title>
              </path>
              {on ? <text x={(x1 + x2) / 2} y={(y1 + y2) / 2 - 4} fontSize={11} textAnchor="middle" fill="var(--ds-ink-soft)">{e.rel}</text> : null}
            </g>
          );
        })}
        {nodes.map((n) => {
          const p = L.placed.get(n.id);
          if (!p) return null;
          const sel = selected === n.id, dim = (lit && lit.size && !lit.has(n.id)) || (path && selected && !path.has(n.id)) || (focus && !focus.has(n.id)) || (fade && fade(n));
          const hc = healthLens && n.health ? HEALTH[n.health] : null;
          return (
            <g key={n.id} transform={`translate(${p.x},${p.y})`} role="button" tabIndex={0} aria-pressed={sel} opacity={dim ? 0.3 : 1} style={{ cursor: "pointer" }}
              aria-label={`${n.label}, ${n.type_word}, ${n.state === "verified" ? "verified" : "in progress"}${n.health_note && healthLens ? `, ${n.health_note}` : ""}`}
              onClick={() => onSelect(sel ? null : n.id)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(sel ? null : n.id); } }}>
              <rect width={W} height={H} rx={10} fill="var(--ds-surface)" stroke={sel ? "var(--ds-ink)" : hc ?? "var(--ds-line-2)"} strokeWidth={sel ? 2.5 : 1.5} strokeDasharray={n.state === "verified" ? undefined : "5 4"} />
              <rect width={4} height={H - 16} x={8} y={8} rx={2} fill={ACCENT[n.type]} />
              <text x={20} y={19} fontSize={13} fill="var(--ds-ink)">{short(n.label, 17)}</text>
              <text x={20} y={35} fontSize={11} fill={hc ?? "var(--ds-ink-muted)"}>{short(healthLens && n.health_note ? n.health_note : n.type_word, 21)}</text>
              <title>{n.label}</title>
            </g>
          );
        })}
      </svg>
      </div>
      </div>
    </div>
  );
}
