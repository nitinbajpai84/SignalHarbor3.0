import { useEffect, useRef, useState } from "react";

import { getDiagram } from "./api";
import { archifySpec, layout, BOX_H, type PlanDiagramData } from "./layout";

const LAYER_NAME = { source: "Sources", bronze: "Bronze · raw as landed", silver: "Silver · the company model", gold: "Gold · ready for dashboards", consumer: "Consumers" };
const STATE_WORD: Record<string, string> = { draft: "Draft", proposed: "Waiting for approval", approved: "Approved", rejected: "Sent back", built: "Built", live: "Live" };

function save(name: string, text: string, type: string) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type }));
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

// Colours follow the page theme through the design tokens; a downloaded SVG has no tokens, so it falls back to the light values.
const C = {
  ground: "var(--ds-surface, #ffffff)", head: "var(--ds-ink-soft, #334155)", line: "var(--ds-line-2, #94a3b8)", ink: "var(--ds-ink, #0f172a)",
  soft: "var(--ds-ink-muted, #475569)", box: "var(--ds-surface-2, #f8fafc)", edge: "var(--ds-node-grey, #64748b)",
  newBox: "color-mix(in srgb, var(--ds-teal, #059669) 18%, var(--ds-surface, #ffffff))", newEdge: "var(--ds-teal-bright, #059669)",
};

export function DiagramSvg({ data, svgRef }: { data: PlanDiagramData; svgRef?: React.Ref<SVGSVGElement> }) {
  const l = layout(data);
  const state = STATE_WORD[data.state] ?? data.state;
  return (
    <svg ref={svgRef} xmlns="http://www.w3.org/2000/svg" viewBox={`0 0 ${l.width + 150} ${l.height}`} width={l.width + 150} height={l.height}
      style={{ width: "100%", maxWidth: l.width + 150, height: "auto", display: "block" }} role="img" aria-label={`Architecture of build plan ${data.project_id}, version ${data.version}, ${state}`} fontFamily="system-ui, sans-serif" fontSize="12">
      <rect width="100%" height="100%" style={{ fill: C.ground }} />
      {l.columns.map((c) => <text key={c.layer} x={c.x} y={36} fontWeight="600" style={{ fill: C.head }}>{LAYER_NAME[c.layer]}</text>)}
      <g fill="none" strokeWidth="1.2" style={{ stroke: C.line }}>
        {l.edges.map((e, i) => {
          const x1 = e.from.x + e.from.w, y1 = e.from.y + BOX_H / 2, x2 = e.to.x, y2 = e.to.y + BOX_H / 2, m = (x1 + x2) / 2;
          return <path key={i} d={`M${x1},${y1} C${m},${y1} ${m},${y2} ${x2},${y2}`} />;
        })}
      </g>
      {l.nodes.map((n) => (
        <g key={n.id} data-node={n.id}>
          <rect x={n.x} y={n.y} width={n.w} height={n.h} rx="6" style={{ fill: n.new ? C.newBox : C.box, stroke: n.new ? C.newEdge : C.edge }} />
          <text x={n.x + 8} y={n.y + 19} style={{ fill: C.ink }}>{n.label.length > 27 ? `${n.label.slice(0, 26)}…` : n.label}</text>
          <text x={n.x + 8} y={n.y + 35} fontSize="10" style={{ fill: C.soft }}>{n.new ? "new" : n.note.slice(0, 30)}</text>
          <title>{n.label}{n.note ? ` · ${n.note}` : ""}</title>
        </g>
      ))}
      <text x={l.width + 140} y={20} textAnchor="end" fontWeight="600" style={{ fill: C.ink }}>{state}</text>
      <text x={l.width + 140} y={34} textAnchor="end" fontSize="10" style={{ fill: C.soft }}>plan v{data.version}</text>
    </svg>
  );
}

export default function PlanDiagram({ projectId }: { projectId: string }) {
  const [data, setData] = useState<PlanDiagramData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef<SVGSVGElement>(null);
  useEffect(() => {
    setData(null);
    setError(null);
    getDiagram(projectId).then(setData, (e: Error) => setError(e.message));
  }, [projectId]);
  if (error) return <p role="alert">{error}</p>;
  if (!data) return <p>Loading the diagram…</p>;
  if (!data.nodes.length) return <p>This plan has no tables yet, so there is nothing to draw.</p>;
  return (
    <section aria-label="Plan diagram">
      <div style={{ display: "flex", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
        <button type="button" className="ds-btn" onClick={() => ref.current && save(`${projectId}-plan-v${data.version}.svg`, new XMLSerializer().serializeToString(ref.current), "image/svg+xml")}>Download the diagram as an SVG picture</button>
        <button type="button" className="ds-btn" onClick={() => save(`${projectId}-plan-v${data.version}.json`, JSON.stringify(archifySpec(data), null, 2), "application/json")}>Download the diagram as an Archify spec for the docs</button>
      </div>
      <div style={{ overflow: "auto", minWidth: 0, maxWidth: "100%" }}><DiagramSvg data={data} svgRef={ref} /></div>
      <p style={{ fontSize: 12 }}>Green boxes marked "new" are created or changed by this plan.</p>
    </section>
  );
}
