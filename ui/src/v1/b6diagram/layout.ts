// B3: a small layered layout, left to right: Sources > Bronze > Silver > Gold > Consumers. No library.
export type DiagramLayer = "source" | "bronze" | "silver" | "gold" | "consumer";
export interface DNode { id: string; label: string; layer: DiagramLayer; new: boolean; note: string }
export interface DEdge { from: string; to: string }
export interface PlanDiagramData { project_id: string; version: number; state: string; layers: DiagramLayer[]; nodes: DNode[]; edges: DEdge[] }
export interface Placed extends DNode { x: number; y: number; w: number; h: number }
export interface Laid { nodes: Placed[]; edges: { from: Placed; to: Placed }[]; width: number; height: number; columns: { layer: DiagramLayer; x: number }[] }

export const BOX_W = 190, BOX_H = 46, GAP_Y = 16, GAP_X = 90, PAD = 24, HEAD = 36;

export function layout(d: PlanDiagramData): Laid {
  const used = d.layers.filter((l) => d.nodes.some((n) => n.layer === l));
  const colOf = new Map(used.map((l, i) => [l, i]));
  const cols: DNode[][] = used.map((l) => d.nodes.filter((n) => n.layer === l));
  const row = new Map<string, number>();
  cols.forEach((col, c) => {
    // order by the mean row of the boxes that feed it, so lines cross less; ties keep plan order
    const score = (n: DNode) => {
      const from = d.edges.filter((e) => e.to === n.id && row.has(e.from)).map((e) => row.get(e.from)!);
      return from.length ? from.reduce((a, b) => a + b, 0) / from.length : Number.MAX_SAFE_INTEGER;
    };
    if (c > 0) col.sort((a, b) => score(a) - score(b));
    col.forEach((n, i) => row.set(n.id, i));
  });
  const placed = new Map<string, Placed>();
  cols.forEach((col, c) => col.forEach((n, i) =>
    placed.set(n.id, { ...n, x: PAD + c * (BOX_W + GAP_X), y: PAD + HEAD + i * (BOX_H + GAP_Y), w: BOX_W, h: BOX_H })));
  const tallest = Math.max(1, ...cols.map((c) => c.length));
  return {
    nodes: [...placed.values()],
    edges: d.edges.flatMap((e) => (placed.has(e.from) && placed.has(e.to) && colOf.get(placed.get(e.from)!.layer)! < colOf.get(placed.get(e.to)!.layer)!
      ? [{ from: placed.get(e.from)!, to: placed.get(e.to)! }] : [])),
    width: PAD * 2 + used.length * BOX_W + Math.max(0, used.length - 1) * GAP_X,
    height: PAD * 2 + HEAD + tallest * BOX_H + (tallest - 1) * GAP_Y,
    columns: used.map((layer, i) => ({ layer, x: PAD + i * (BOX_W + GAP_X) })),
  };
}

// The Archify-style JSON spec (docs/architecture/*.json shape) for the same plan.
const TYPE: Record<DiagramLayer, string> = { source: "external", bronze: "database", silver: "database", gold: "database", consumer: "frontend" };
export function archifySpec(d: PlanDiagramData): object {
  const l = layout(d);
  return {
    schema_version: 1, diagram_type: "architecture",
    meta: { title: `Build plan ${d.project_id} v${d.version}`, subtitle: `Approval state: ${d.state}`, quality_profile: "standard" },
    components: l.nodes.map((n) => ({ id: n.id, type: TYPE[n.layer], label: n.label, sublabel: n.new ? "new" : n.note, pos: [n.x, n.y], size: [n.w, n.h] })),
    connections: l.edges.map((e, i) => ({ id: `e${i + 1}`, from: e.from.id, to: e.to.id })),
  };
}
