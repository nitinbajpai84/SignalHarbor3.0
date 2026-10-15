import { useEffect, useState } from "react";

import { apiGet } from "../api/client";

// The knowledge map's shared reads (spec 55): what the gated map route draws, plus the scan results, owner kinds and last update from
// GET /api/intents/knowledge-map/overview. If the overview cannot be read the map still draws; scan tags and owner kinds are then absent.

export interface KNode { id: string; type: string; label: string; restricted?: boolean }
export interface KEdge { from: string; to: string; type: string }
export interface Check {
  result: string; word: string; scanned_at: string | null; found_in: { id: string; label: string } | null; confirmed_by: string | null;
  rejected_by: string | null; can_decide: boolean; gap_report: string;
}
export interface Overview {
  last_update: { id: string; moment: string; by: string; at: string; line: string } | null; updates_this_week: number;
  checks: Record<string, Check>; owners: Record<string, { id: string; label: string; kinds: string[] }[]>;
}
export const NO_OVERVIEW: Overview = { last_update: null, updates_this_week: 0, checks: {}, owners: {} };

export function useOverview(reload = 0): Overview | "failed" | null {
  const [ov, setOv] = useState<Overview | "failed" | null>(null);
  useEffect(() => {
    let live = true;
    apiGet<Overview>("/api/intents/knowledge-map/overview")
      .then((d) => { if (live) setOv(d && typeof d === "object" && d.checks ? d : "failed"); })
      .catch(() => { if (live) setOv("failed"); });
    return () => { live = false; };
  }, [reload]);
  return ov;
}

export const GROUPS: Record<string, string[]> = {
  data: ["Field", "File", "Source", "System", "Mart"], processes: ["Process", "Step"], people: ["Person", "Team"],
  work: ["Intent", "Charter", "GapReport", "Blueprint", "Pipeline", "Release"],
};
export const groupOf = (type: string): string | null => Object.keys(GROUPS).find((g) => GROUPS[g]!.includes(type)) ?? null;
export const LIVES = ["Field", "File", "Mart"];

const UP: [string, "out" | "in"][] = [["fed_by", "out"], ["held_in", "out"], ["lands_at", "out"], ["built_by", "out"], ["produced_by", "out"], ["uses", "in"], ["produces", "in"]];
const DOWN: [string, "out" | "in"][] = [["fed_by", "in"], ["held_in", "in"], ["lands_at", "in"], ["built_by", "in"], ["produced_by", "in"], ["uses", "out"], ["produces", "out"],
  ["released_in", "out"], ["designed_in", "out"], ["defined_in", "out"]];

function walk(seeds: string[], edges: KEdge[], rules: [string, "out" | "in"][]): Set<string> {
  const seen = new Set(seeds), todo = [...seeds];
  while (todo.length) {
    const cur = todo.pop()!;
    for (const e of edges) for (const [t, side] of rules) {
      if (e.type !== t) continue;
      const [a, b] = side === "out" ? [e.from, e.to] : [e.to, e.from];
      if (a === cur && !seen.has(b)) { seen.add(b); todo.push(b); }
    }
  }
  return seen;
}

/** The focus thing's own line: what supplies it (upstream) and what uses it (downstream), and no other topic. A field stands with its source. */
export function lineageIds(nodes: KNode[], edges: KEdge[], focus: string): Set<string> {
  const type = new Map(nodes.map((n) => [n.id, n.type]));
  const seeds = [focus, ...(type.get(focus) === "Field" ? edges.filter((e) => e.type === "uses" && e.to === focus).map((e) => e.from) : [])];
  const out = new Set([...walk(seeds, edges, UP), ...walk(seeds, edges, DOWN)]);
  if (type.get(focus) === "Field") for (const id of [...out]) if (id !== focus && type.get(id) === "Field") out.delete(id);
  return out;
}

export const LINEAGE_TYPES: string[][] = [["Process", "Step"], ["System"], ["File", "Source"], ["Field"], ["Pipeline", "Mart"], ["Measure"], ["Charter", "GapReport", "Blueprint", "Release"]];

/** The rows of the node page's "Where it lives" card, worked out from the viewer's own map. */
export function whereRows(nodes: KNode[], edges: KEdge[], id: string) {
  const by = new Map(nodes.map((n) => [n.id, n]));
  const type = by.get(id)?.type ?? "";
  const out = (t: string, from = id) => edges.filter((e) => e.type === t && e.from === from).map((e) => by.get(e.to)).filter((n): n is KNode => !!n && !n.restricted);
  const into = (t: string) => edges.filter((e) => e.type === t && e.to === id).map((e) => by.get(e.from)).filter((n): n is KNode => !!n && !n.restricted);
  const via = type === "Measure" ? out("fed_by").map((n) => n.id) : [id];
  const hop = (t: string) => via.flatMap((v) => out(t, v));
  const uniq = (xs: KNode[]) => [...new Map(xs.map((n) => [n.id, n])).values()];
  const fromSource = type === "Field" ? edges.filter((e) => e.type === "uses" && e.to === id).map((e) => e.from) : [];
  const feeds = uniq([...walk([id, ...fromSource], edges, [["fed_by", "in"], ["uses", "out"], ["built_by", "in"]])].map((x) => by.get(x)).filter((n): n is KNode => !!n && n.type === "Measure" && n.id !== id));
  return {
    heldIn: uniq([...hop("held_in"), ...fromSource.flatMap((s) => out("held_in", s))]), holds: uniq(into("held_in")),
    landsAt: uniq([...hop("lands_at"), ...via.flatMap((v) => out("built_by", v)).flatMap((p) => out("lands_at", p.id))]),
    writtenIn: uniq(out("defined_in")),
    feeds, fedBy: uniq(out("fed_by")),
    producedBy: uniq([...into("produces"), ...out("produced_by"), ...fromSource.flatMap((s) => [...out("produced_by", s), ...edges.filter((e) => e.type === "produces" && e.to === s).map((e) => by.get(e.from)).filter((n): n is KNode => !!n)])]),
  };
}
