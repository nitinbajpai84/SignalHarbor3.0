import { useEffect, useState } from "react";

import type { BriefGroup, BriefLine } from "../api";

export type NodeKind = "question" | "readers" | "when" | "figure" | "source" | "rule";
export interface GraphNode { id: string; kind: NodeKind; label: string; value: string; x: number; y: number; lines: BriefLine[]; changed: boolean; suggested: boolean }

const W = 800, H = 580, CX = 400, CY = 290, NW = 164, NH = 52;
const spread = (n: number, a: number, b: number) => Array.from({ length: n }, (_, i) => (n === 1 ? (a + b) / 2 : a + ((b - a) * i) / (n - 1)));
const cut = (s: string, n: number) => (s.length > n ? `${s.slice(0, n - 1)}...` : s);

/** The brief document laid out in fixed places: the question in the centre, readers and timing left, figures right, rules above, sources below. */
export function buildNodes(doc: BriefGroup[]): GraphNode[] {
  const out: GraphNode[] = [];
  const add = (n: Omit<GraphNode, "changed" | "suggested">) => out.push({ ...n, changed: n.lines.some((l) => l.changed), suggested: n.lines.some((l) => l.suggested) });
  const what = doc.find((g) => g.title === "What you want")?.lines ?? [];
  const f = (field: string) => what.filter((l) => l.field === field);
  const q = [...f("line"), ...f("why")];
  const first = q[0];
  if (first) add({ id: "question", kind: "question", label: "The question", value: first.value, x: CX, y: CY, lines: q });
  const reads = [...f("readers"), ...f("decisions")];
  const left = [
    { id: "readers", kind: "readers" as const, label: "Who reads and decides", value: reads.map((l) => l.value).filter(Boolean).join(" · "), lines: reads },
    { id: "when", kind: "when" as const, label: "When", value: f("needed_by")[0]?.value ?? "", lines: f("needed_by") },
  ].filter((n) => n.lines.length);
  const ys = spread(left.length, 190, 400);
  left.forEach((n, i) => add({ ...n, x: 100, y: ys[i] ?? CY }));
  const figs = doc.filter((g) => g.title.startsWith("Figure:"));
  const fy = spread(figs.length, 120, 470);
  figs.forEach((g, i) => add({ id: `figure:${g.title}`, kind: "figure", label: g.title.slice(7).trim() || "Figure", value: g.lines.find((l) => l.field === "definition")?.value ?? "", x: 700, y: fy[i] ?? CY, lines: g.lines }));
  const srcs = doc.find((g) => g.title === "Where the data comes from")?.lines ?? [];
  const sx = spread(srcs.length, 200, 600);
  srcs.forEach((l, i) => add({ id: `source:${i}`, kind: "source", label: l.label, value: l.value, x: sx[i] ?? CX, y: 535, lines: [l] }));
  const rules = doc.find((g) => g.title === "Rules")?.lines ?? [];
  const rx = spread(rules.length, 230, 470);
  rules.forEach((l, i) => add({ id: `rule:${i}`, kind: "rule", label: "Rule", value: l.value, x: rx[i] ?? CX, y: 45, lines: [l] }));
  return out;
}

/** One line of the brief with its own edit: pencil, change the words, save. Saved straight into the brief, no model call. */
export function EditLine({ line, onSave, busy }: { line: BriefLine; onSave: (v: string) => Promise<void>; busy: boolean }) {
  const [editing, setEditing] = useState(false);
  const [v, setV] = useState(line.value);
  useEffect(() => { if (!editing) setV(line.value); }, [line.value, editing]);
  return (
    <div className={line.changed ? "v3-bline changed" : "v3-bline"}>
      <dt>{line.label}{line.suggested && <span className="v3-sug">suggested</span>}{line.changed && <span className="v3-new">updated</span>}</dt>
      {editing ? (
        <dd>
          <textarea aria-label={`Change ${line.label}`} rows={2} value={v} onChange={(e) => setV(e.target.value)} autoFocus />
          <span className="v3-row">
            <button className="go" disabled={busy || !v.trim()} onClick={() => void onSave(v.trim()).then(() => setEditing(false))}>Save</button>
            <button onClick={() => { setV(line.value); setEditing(false); }}>Cancel</button>
          </span>
        </dd>
      ) : (
        <dd>
          <span className={line.value ? "" : "v3-mute"}>{line.value || "Not said yet"}</span>
          <button className="v3-pencil" aria-label={`Edit ${line.label}`} title="Edit" onClick={() => setEditing(true)}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" /></svg>
          </button>
        </dd>
      )}
    </div>
  );
}

/** The small dot on a neutral box: done when a source has arrived (or the figure is live), needs when it is still waiting on something. */
function dotOf(n: GraphNode, arrived: Set<string>, live: boolean): "done" | "needs" | null {
  if (n.kind === "question") return null;
  if (!n.value) return "needs";
  if (n.kind === "source") return arrived.has(n.label.trim().toLowerCase()) ? "done" : "needs";
  if (n.kind === "figure") return live ? "done" : null;
  return null;
}

/** The brief as plain groups with the same pencils: what a phone shows instead of the graph. */
export function BriefList({ doc, busy, onSave }: { doc?: BriefGroup[] | null; busy: boolean; onSave: (line: BriefLine, value: string) => Promise<void> }) {
  if (!doc?.length) return <p className="v3-mute b3-empty" role="status">Nothing to show yet. Say what you want and Harbor writes the brief here.</p>;
  return (
    <div className="b3-brief">
      {doc.map((g) => (
        <section key={g.title} className="v3-bgroup">
          <h3>{g.title}</h3>
          <dl>{g.lines.map((l) => <EditLine key={`${l.section}.${l.index}.${l.field}`} line={l} busy={busy} onSave={(v) => onSave(l, v)} />)}</dl>
        </section>
      ))}
    </div>
  );
}

export default function IntentGraph({ doc, busy, onSave, arrived = new Set(), live = false }: {
  doc?: BriefGroup[] | null; busy: boolean; onSave: (line: BriefLine, value: string) => Promise<void>;
  /** Lower-cased source names that have at least one file. */ arrived?: Set<string>; live?: boolean;
}) {
  const [sel, setSel] = useState<string | null>(null);
  const nodes = buildNodes(doc ?? []);
  if (nodes.length === 0) return <p className="v3-mute b3-empty" role="status">Nothing to draw yet. Say what you want and Harbor draws it here.</p>;
  const centre = nodes.find((n) => n.kind === "question");
  const open = nodes.find((n) => n.id === sel);
  const pick = (id: string) => setSel((s) => (s === id ? null : id));
  return (
    <div className="b3-graph">
      <svg viewBox={`0 0 ${W} ${H}`} role="group" aria-label="The intent, drawn from the brief">
        {centre && nodes.filter((n) => n !== centre).map((n) => (
          <line key={`e-${n.id}`} className={`b3-edge${n.kind === "source" ? " dashed" : ""}${n.suggested ? " suggested" : ""}`} x1={centre.x} y1={centre.y} x2={n.x} y2={n.y} />
        ))}
        {nodes.map((n) => {
          const dot = dotOf(n, arrived, live);
          return (
            <g
              key={n.id}
              role="button"
              tabIndex={0}
              aria-label={n.label}
              aria-pressed={sel === n.id}
              className={`b3-node ${n.kind}${n.suggested ? " suggested" : ""}${n.changed ? " glow" : ""}${sel === n.id ? " on" : ""}`}
              onClick={() => pick(n.id)}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(n.id); } }}
            >
              <rect x={n.x - NW / 2} y={n.y - NH / 2} width={NW} height={NH} rx={14} />
              {dot && <circle className={`b3-ndot ${dot}`} cx={n.x - NW / 2 + 12} cy={n.y - 6 - 4} r={4} />}
              <text x={n.x} y={n.y - 6} textAnchor="middle" className="b3-t1">{cut(n.label, 24)}</text>
              <text x={n.x} y={n.y + 12} textAnchor="middle" className="b3-t2">{cut(n.value || "not said yet", 26)}</text>
              {n.changed ? <text x={n.x + NW / 2 - 6} y={n.y - NH / 2 - 5} textAnchor="end" className="b3-tag">just added</text>
                : n.suggested ? <text x={n.x + NW / 2 - 6} y={n.y - NH / 2 - 5} textAnchor="end" className="b3-tag">suggested</text> : null}
            </g>
          );
        })}
      </svg>
      {open ? (
        <section className="v3-card b3-edit" aria-label={`Edit ${open.label}`}>
          <div className="v3-row" style={{ justifyContent: "space-between" }}>
            <span className="v3-kicker">{open.label}</span>
            <button onClick={() => setSel(null)}>Close</button>
          </div>
          <dl>{open.lines.map((l) => <EditLine key={`${l.section}.${l.index}.${l.field}`} line={l} busy={busy} onSave={(v) => onSave(l, v)} />)}</dl>
        </section>
      ) : (
        <small className="v3-mute">Click any box to see it, or change it.</small>
      )}
    </div>
  );
}
