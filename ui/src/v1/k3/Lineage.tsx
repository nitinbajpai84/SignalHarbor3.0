import { useMemo } from "react";

import OntoGraph from "./OntoGraph";
import type { DataModel, LineageNode, OntoEdge, OntoNode, OntoType } from "./api";

// DM2: the data model as a graph, left to right: sources, bronze, silver, gold, dashboards and reports, projects. The drawing is the ontology's (OntoGraph).
const COL: Record<LineageNode["kind"], number> = { source: 0, bronze: 1, silver: 2, gold: 3, dashboard: 4, report: 4, project: 5 };
const TALL = 12;   // silver is long: after this many tables it carries on in a second, third… column (col 2, 2.1, 2.2) so the page stays readable
export const LINEAGE_COLUMNS = ["Sources", "Bronze", "Silver", "Gold", "Dashboards, reports", "Projects"];
const WORD: Record<LineageNode["kind"], string> = { source: "source", bronze: "bronze table", silver: "silver table", gold: "gold table", dashboard: "dashboard", report: "report", project: "project" };

/** The picked node, everything it reads from (upstream) and everything that reads it (downstream). */
export function trace(id: string, edges: { from: string; to: string }[]): Set<string> {
  const out = new Set([id]);
  for (const [near, far] of [["from", "to"], ["to", "from"]] as const) {   // once following the arrows, once against them
    const todo = [id], seen = new Set([id]);
    for (let n = todo.pop(); n !== undefined; n = todo.pop()) for (const e of edges) if (e[near] === n && !seen.has(e[far])) { seen.add(e[far]); out.add(e[far]); todo.push(e[far]); }
  }
  return out;
}

export const usedBy = (n: number) => `used by ${n} project${n === 1 ? "" : "s"}`;

export default function Lineage({ m, shown, picked, onPick }: { m: DataModel; shown: Set<string>; picked: string | null; onPick: (id: string | null) => void }) {
  const path = useMemo(() => (picked ? trace(picked, m.lineage.edges) : undefined), [picked, m]);
  const nodes: OntoNode[] = useMemo(() => m.lineage.nodes.filter((n) => !["bronze", "silver", "gold"].includes(n.kind) || shown.has(n.id)).map((n, _i, all) => ({
    id: n.id, type: (n.kind === "bronze" || n.kind === "silver" || n.kind === "gold" ? "table" : n.kind) as OntoType, layer: null, label: n.label.replace(/^(bronze|silver|gold)\./, ""),
    sub: "", owner: null, project_id: null, at: null, health: null, health_note: null, steps: {}, state: "verified", waiting: false, sent_back: null, verified_by: null, verified_at: null,
    col: n.kind === "silver" ? COL.silver + Math.floor(all.filter((x) => x.kind === "silver" && x.id < n.id).length / TALL) / 10 : COL[n.kind], band: false, type_word: n.kind === "silver" && n.used_by > 0 ? usedBy(n.used_by) : WORD[n.kind],
  })), [m, shown]);
  const ids = new Set(nodes.map((n) => n.id));
  const edges: OntoEdge[] = m.lineage.edges.filter((e) => ids.has(e.from) && ids.has(e.to)).map((e) => ({ from: e.from, to: e.to, rel: e.rows ? `feeds · ${e.rows.toLocaleString("en-US")} rows` : "feeds", state: "verified" } as OntoEdge));
  return <OntoGraph nodes={nodes} edges={edges} columns={LINEAGE_COLUMNS} selected={picked} onSelect={onPick} path={path} />;
}
