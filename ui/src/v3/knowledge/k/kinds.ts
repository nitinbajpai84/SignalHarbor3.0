import type { KEdge, KNode, Kind } from "./api";

export const KIND_LABEL: Record<Kind, string> = { person: "People", entity: "Entities", fund: "Funds", source: "Sources", file: "Files", document: "Documents", recipe: "Recipes", figure: "Figures", signal: "Signals", rule: "Rules", usecase: "Use cases", decision: "Decisions" };
export const KIND_ONE: Record<Kind, string> = { person: "Person", entity: "Entity", fund: "Fund", source: "Source", file: "File", document: "Document", recipe: "Recipe", figure: "Figure", signal: "Signal", rule: "Rule", usecase: "Use case", decision: "Decision" };
export const KINDS = Object.keys(KIND_LABEL) as Kind[];
/** Colour means one thing (docs/v3/COLOURS.md): people are who can act, figures and recipes are what Harbor built, signals wait for a person, rules are signed, records are information. */
export const KIND_VAR: Record<Kind, string> = { person: "--act", usecase: "--ink", figure: "--harbor", recipe: "--harbor", signal: "--needs", rule: "--done", source: "--info", file: "--info", document: "--info", entity: "--mute", fund: "--mute", decision: "--problem" };
export const kindColour = (k: Kind) => `var(${KIND_VAR[k]})`;

export const byId = (nodes: KNode[]) => new Map(nodes.map((n) => [n.id, n]));
/** The other end of an edge, from the point of view of `id`, and whether `id` is the upstream end. Older edges without `up` read from -> to. */
export function ends(e: KEdge, id: string) { const other = e.from === id ? e.to : e.from; return { other, mineUp: (e.up ?? e.from) === id }; }
export const around = (edges: KEdge[], id: string) => edges.filter((e) => e.from === id || e.to === id);
export function neighbours(edges: KEdge[], id: string): Set<string> {
  const s = new Set<string>([id]);
  for (const e of edges) if (e.from === id || e.to === id) { s.add(e.from); s.add(e.to); }
  return s;
}
/** Everything a node rests on (up) or feeds (down): the lines of the Atlas panel. */
export function lines(edges: KEdge[], nodes: KNode[], id: string) {
  const by = byId(nodes), rests: Line[] = [], feeds: Line[] = [];
  for (const e of around(edges, id)) {
    const { other, mineUp } = ends(e, id), n = by.get(other);
    if (!n) continue;
    const side = mineUp ? feeds : rests, same = side.find((l) => l.node.id === n.id);  // two edges to the same thing read as one line
    if (same) { if (!same.label.includes(e.label)) same.label += `, ${e.label}`; same.why ||= e.why ?? ""; } else side.push({ node: n, label: e.label, why: e.why ?? "" });
  }
  const sort = (a: Line, b: Line) => a.node.label.localeCompare(b.node.label);
  return { rests: rests.sort(sort), feeds: feeds.sort(sort) };
}
export interface Line { node: KNode; label: string; why: string }
export const receipt = (n: KNode) => { const f = n.facts[0]; return f ? `${f.source}${f.at ? `, ${f.at}` : ""}` : ""; };

/** The flow of the lineage view: files -> sources -> figures -> use cases -> people, drawn only where a record joins two steps. */
export const STEPS: Kind[] = ["file", "source", "figure", "usecase", "person"];
export function flowLinks(nodes: KNode[], edges: KEdge[]): { from: string; to: string }[] {
  const by = byId(nodes), out = new Map<string, { from: string; to: string }>();
  const add = (a: string, b: string) => { const x = by.get(a)?.kind, y = by.get(b)?.kind; if (x && y && STEPS.indexOf(x) >= 0 && STEPS.indexOf(y) === STEPS.indexOf(x) + 1) out.set(`${a}|${b}`, { from: a, to: b }); };
  for (const e of edges) { add(e.from, e.to); add(e.to, e.from); }
  return [...out.values()];
}
