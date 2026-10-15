import Panel from "../../../components/Panel";
import { copy } from "../../../copy";
import StatusPill from "../../../components/StatusPill";
import type { PictureGraph } from "../api";
import { m1Charter } from "../copy";

const ROW = 44;
const TOP = 28;
const W = 300;
const GAP = 140;
const MAX_CHARS = 36;

// Tokens only (the look test bans colour literals): the legacy stylesheet's own variables.
const BOX = { fill: "var(--surface-elevated)", stroke: "var(--border-hairline)" } as const;
const KPI_BOX = { fill: "var(--surface-elevated)", stroke: "var(--border-luminous)" } as const;
const LABEL = { fill: "var(--text-primary)", fontSize: 12 } as const;
const HEAD = { fill: "var(--text-muted)", fontSize: 11 } as const;
const LINK = { stroke: "var(--accent)", strokeWidth: 1.5, fill: "none", opacity: 0.7 } as const;

const short = (s: string) => (s.length > MAX_CHARS ? `${s.slice(0, MAX_CHARS - 1)}\u2026` : s);

/**
 * D-022: a simple picture of the business graph at sign-off, as plain SVG: the charter's problems on the left, the
 * measures the company's own industry pack lists for them on the right, a line for each link. Always a suggestion.
 */
export default function GraphPicture({ graph }: { graph: PictureGraph }) {
  const P = m1Charter.picture;
  const rows = Math.max(graph.problems.length, graph.kpis.length);
  const height = TOP + rows * ROW + 8;
  const left = (i: number) => TOP + i * ROW + ROW / 2 - 4;
  const right = (i: number) => TOP + i * ROW + ROW / 2 - 4;
  const pIndex = new Map(graph.problems.map((p, i) => [p.id, i]));
  const kIndex = new Map(graph.kpis.map((k, i) => [k.id, i]));
  return (
    <Panel eyebrow={P.title} title={P.label} actions={<StatusPill tone="info">{copy.wizard.suggestion}</StatusPill>} className="m1-picture">
      <p className="n-e1-def-note">{P.note}</p>
      <p className="n-e1-def-note">{graph.label}</p>
      <svg viewBox={`0 0 ${W * 2 + GAP} ${height}`} role="img" aria-label={P.label} style={{ width: "100%", height: "auto", maxWidth: 720, display: "block" }}>
        <text x={0} y={14} style={HEAD}>
          {P.problems}
        </text>
        <text x={W + GAP} y={14} style={HEAD}>
          {P.measures}
        </text>
        {graph.links.map((l) => {
          const a = pIndex.get(l.problem);
          const b = kIndex.get(l.kpi);
          return a === undefined || b === undefined ? null : (
            <path key={`${l.problem}-${l.kpi}`} className="link" style={LINK} d={`M${W} ${left(a)} C${W + GAP / 2} ${left(a)} ${W + GAP / 2} ${right(b)} ${W + GAP} ${right(b)}`} />
          );
        })}
        {graph.problems.map((p, i) => (
          <g key={p.id} className="node problem" transform={`translate(0 ${left(i) - 16})`}>
            <title>{p.title}</title>
            <rect width={W} height={32} rx={6} style={BOX} />
            <text x={10} y={21} style={LABEL}>
              {short(p.title)}
            </text>
          </g>
        ))}
        {graph.kpis.map((k, i) => (
          <g key={k.id} className="node kpi" transform={`translate(${W + GAP} ${right(i) - 16})`}>
            <title>{k.name}</title>
            <rect width={W} height={32} rx={6} style={KPI_BOX} />
            <text x={10} y={21} style={LABEL}>
              {short(k.name)}
            </text>
          </g>
        ))}
      </svg>
      <ul className="n-e1-def-note">
        {graph.problems.map((p) => (
          <li key={p.id}>
            {p.title}: {graph.links.filter((l) => l.problem === p.id).map((l) => graph.kpis.find((k) => k.id === l.kpi)?.name).filter(Boolean).join(", ")}
          </li>
        ))}
      </ul>
    </Panel>
  );
}
