import type { Lens, OntoEdge, OntoNode, OntoType, Ontology, Relation } from "./api";

// Pure helpers for the company map: which nodes show, and where each one sits. A layered layout: one column per layer, left to right;
// definitions, decisions and cases sit in a band beneath. Order inside a column follows the neighbours in the column before it.
export const W = 132, H = 46, GX = 28, GY = 14, TOP = 34;  // F1: narrow enough that eight columns fit a normal screen

export const GROUPS: { id: string; label: string; types: OntoType[] }[] = [
  { id: "person", label: "People", types: ["person"] }, { id: "project", label: "Projects", types: ["project", "intent"] },
  { id: "source", label: "Sources", types: ["source"] }, { id: "table", label: "Tables", types: ["table"] }, { id: "definition", label: "Definitions", types: ["definition"] },
  { id: "output", label: "Dashboards, reports", types: ["dashboard", "report"] }, { id: "case", label: "Cases", types: ["case"] }, { id: "decision", label: "Decisions", types: ["decision"] },
];

export interface Filters { lens: string; hidden: Set<string>; state: "all" | "verified" | "in_progress"; project: string | null; q: string }

export function visible(o: Ontology, f: Filters): { nodes: OntoNode[]; edges: OntoEdge[] } {
  const lens: Lens | undefined = o.lenses.find((l) => l.id === f.lens);
  const hide = new Set(GROUPS.filter((g) => f.hidden.has(g.id)).flatMap((g) => g.types));
  const nodes = o.nodes.filter((n) => n.type !== "agent" && (!lens || lens.types.includes(n.type)) && !hide.has(n.type) && (f.state === "all" || n.state === f.state)
    && (!f.project || n.steps[f.project] !== undefined));
  const ids = new Set(nodes.map((n) => n.id));
  const rels: Relation[] = lens?.rels ?? o.relations;
  return { nodes, edges: o.edges.filter((e) => rels.includes(e.rel) && ids.has(e.from) && ids.has(e.to)) };
}

export interface Placed { n: OntoNode; x: number; y: number }
export function layout(nodes: OntoNode[], edges: OntoEdge[]): { placed: Map<string, Placed>; width: number; height: number; columns: number[] } {
  const cols = [...new Set(nodes.map((n) => n.col))].sort((a, b) => a - b);
  const x = new Map(cols.map((c, i) => [c, 16 + i * (W + GX)]));
  const pos = new Map<string, number>(); // row index of a node in its column, for the barycentre sweep
  const placed = new Map<string, Placed>();
  const nb = new Map<string, string[]>();
  for (const e of edges) { (nb.get(e.to) ?? nb.set(e.to, []).get(e.to)!).push(e.from); (nb.get(e.from) ?? nb.set(e.from, []).get(e.from)!).push(e.to); }
  let main = 0;
  const put = (list: OntoNode[], y0: number) => {
    list.forEach((n, i) => { pos.set(n.id, i); placed.set(n.id, { n, x: x.get(n.col)!, y: y0 + i * (H + GY) }); });
    return list.length;
  };
  for (const band of [false, true]) {
    let tallest = 0;
    for (const c of cols) {
      const list = nodes.filter((n) => n.col === c && n.band === band);
      const key = (n: OntoNode) => { const ps = (nb.get(n.id) ?? []).filter((i) => pos.has(i)).map((i) => pos.get(i)!); return ps.length ? ps.reduce((a, b) => a + b, 0) / ps.length : 1e6; };
      list.sort((a, b) => key(a) - key(b) || a.label.localeCompare(b.label));
      tallest = Math.max(tallest, put(list, band ? main + 36 : TOP));
    }
    if (!band) main = TOP + tallest * (H + GY);
    else main = main + 36 + tallest * (H + GY);
  }
  return { placed, width: 16 + cols.length * (W + GX) + 8, height: Math.max(main, 120) + 8, columns: cols };
}

export const near = (id: string, edges: OntoEdge[]): Set<string> => new Set([id, ...edges.flatMap((e) => (e.from === id ? [e.to] : e.to === id ? [e.from] : []))]);

export const matches = (o: Ontology, q: string): Set<string> => {
  const t = q.trim().toLowerCase();
  return new Set(t ? o.nodes.filter((n) => `${n.label} ${n.sub} ${n.type_word} ${n.owner ?? ""}`.toLowerCase().includes(t)).map((n) => n.id) : []);
};

// V6 (F1): the whole company on one page, as the artboard draws it: people and agents across the top, the projects beneath them, the data flowing left to
// right (sources to dashboards) in the middle, and what things mean (definitions, decisions, cases) in a band at the bottom.
export interface Label { x: number; y: number; text: string }
export interface CompanyLayout { placed: Map<string, Placed & { row: number }>; width: number; height: number; labels: Label[] }
const PER_ROW = 8;

export function layoutCompany(nodes: OntoNode[], edges: OntoEdge[], names: string[]): CompanyLayout {
  const row = (n: OntoNode) => (n.type === "person" || n.type === "agent" ? 0 : n.type === "project" || n.type === "intent" ? 1 : n.band ? 3 : 2);
  const placed = new Map<string, Placed & { row: number }>();
  const labels: Label[] = [];
  const nb = new Map<string, string[]>();
  for (const e of edges) { (nb.get(e.to) ?? nb.set(e.to, []).get(e.to)!).push(e.from); (nb.get(e.from) ?? nb.set(e.from, []).get(e.from)!).push(e.to); }
  const X = (i: number) => 16 + i * (W + GX);
  let y = 0;
  let widest = 1;
  const strip = (list: OntoNode[], r: number, heading: string | null) => {   // a horizontal row of boxes, wrapped at PER_ROW
    if (!list.length) return;
    if (heading) labels.push({ x: X(0), y: y + 12, text: heading });
    y += heading ? 22 : 0;
    list.forEach((n, i) => placed.set(n.id, { n, x: X(i % PER_ROW), y: y + Math.floor(i / PER_ROW) * (H + GY), row: r }));
    y += Math.ceil(list.length / PER_ROW) * (H + GY) + 18;
    widest = Math.max(widest, Math.min(PER_ROW, list.length));
  };
  const byLabel = (a: OntoNode, b: OntoNode) => a.label.localeCompare(b.label);
  const people = nodes.filter((n) => n.type === "person").sort(byLabel), agents = nodes.filter((n) => n.type === "agent").sort(byLabel);
  if (people.length || agents.length) {   // people then agents on one line, each with its own heading
    const off = people.length + 1;
    labels.push({ x: X(0), y: y + 12, text: names[0] ?? "People" });
    if (agents.length) labels.push({ x: X(off), y: y + 12, text: names[1] ?? "Agents" });
    y += 22;
    people.forEach((n, i) => placed.set(n.id, { n, x: X(i), y, row: 0 }));
    agents.forEach((n, i) => placed.set(n.id, { n, x: X(off + i), y, row: 0 }));
    y += H + GY + 18;
    widest = Math.max(widest, off + agents.length);
  }
  strip(nodes.filter((n) => row(n) === 1).sort(byLabel), 1, names[2] ?? "Projects");
  const flow = nodes.filter((n) => row(n) === 2);
  const cols = [...new Set(flow.map((n) => n.col))].sort((a, b) => a - b);
  if (flow.length) {
    cols.forEach((c, i) => labels.push({ x: X(i), y: y + 12, text: names[c] ?? "" }));
    y += 22;
    const pos = new Map<string, number>();
    let tallest = 0;
    cols.forEach((c, i) => {
      const list = flow.filter((n) => n.col === c);
      const key = (n: OntoNode) => { const ps = (nb.get(n.id) ?? []).filter((id) => pos.has(id)).map((id) => pos.get(id)!); return ps.length ? ps.reduce((a, b) => a + b, 0) / ps.length : 1e6; };
      list.sort((a, b) => key(a) - key(b) || byLabel(a, b));
      list.forEach((n, k) => { pos.set(n.id, k); placed.set(n.id, { n, x: X(i), y: y + k * (H + GY), row: 2 }); });
      tallest = Math.max(tallest, list.length);
    });
    y += tallest * (H + GY) + 18;
    widest = Math.max(widest, cols.length);
  }
  strip(nodes.filter((n) => row(n) === 3).sort((a, b) => a.col - b.col || byLabel(a, b)), 3, "Definitions, decisions, cases");
  return { placed, width: X(widest) + 8, height: Math.max(y, 120), labels };
}
