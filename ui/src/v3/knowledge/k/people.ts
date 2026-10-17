import type { KEdge, KNode } from "./api";
import { byId } from "./kinds";

/** What one person has to do with one figure: they use it, sign it (a use case or a rule they signed), or a signal about it goes to them. */
export interface Tie { uses: boolean; signs: boolean; signal: boolean }
const PERSON_USE = new Set(["asked by", "reads", "decides"]);

/** The ties, from the records alone: person -> use case (asks, reads, decides), use case -> figure, rule -> figure and signer, signal -> figure and person. */
export function ties(nodes: KNode[], edges: KEdge[]) {
  const by = byId(nodes), kind = (id: string) => by.get(id)?.kind;
  const people = nodes.filter((n) => n.kind === "person"), figures = nodes.filter((n) => n.kind === "figure");
  const figsOf = (uc: string) => new Set(edges.flatMap((e) => (e.from === uc && kind(e.to) === "figure" && ["uses", "answers with"].includes(e.label) ? [e.to] : e.to === uc && kind(e.from) === "figure" && e.label === "used by" ? [e.from] : [])));
  const out = new Map<string, Map<string, Tie>>();
  const tie = (p: string, f: string): Tie => {
    const row = out.get(p) ?? new Map<string, Tie>();
    out.set(p, row);
    const t = row.get(f) ?? { uses: false, signs: false, signal: false };
    row.set(f, t);
    return t;
  };
  const casesOf = new Map<string, { asks: Set<string>; reads: Set<string>; decides: Set<string> }>();
  for (const e of edges) {
    const [p, u] = kind(e.from) === "person" ? [e.from, e.to] : kind(e.to) === "person" ? [e.to, e.from] : ["", ""];
    if (!p || kind(u) !== "usecase" || !PERSON_USE.has(e.label)) continue;
    const c = casesOf.get(p) ?? { asks: new Set(), reads: new Set(), decides: new Set() };
    casesOf.set(p, c);
    (e.label === "asked by" ? c.asks : e.label === "reads" ? c.reads : c.decides).add(u);
    for (const f of figsOf(u)) { const t = tie(p, f); if (e.label === "decides") t.signs = true; else t.uses = true; }
  }
  for (const r of nodes.filter((n) => n.kind === "rule")) {
    const signers = edges.filter((e) => e.from === r.id && e.label === "signed by").map((e) => e.to);
    const fs = edges.filter((e) => e.from === r.id && e.label === "limits" && kind(e.to) === "figure").map((e) => e.to);
    for (const p of signers) for (const f of fs) tie(p, f).signs = true;
  }
  for (const s of nodes.filter((n) => n.kind === "signal")) {
    const ps = edges.filter((e) => e.from === s.id && e.label === "goes to").map((e) => e.to);
    const fs = edges.filter((e) => e.from === s.id && e.label === "watches" && kind(e.to) === "figure").map((e) => e.to);
    for (const p of ps) for (const f of fs) tie(p, f).signal = true;
  }
  return { people, figures, ties: out, casesOf, figsOf };
}

/** Whom a person depends on (who decides what they read, who signed the rules their figures answer to) and who depends on them. */
export function dependencies(nodes: KNode[], edges: KEdge[], person: string) {
  const { ties: t, casesOf } = ties(nodes, edges);
  const deciders = (u: string) => [...casesOf].filter(([, c]) => c.decides.has(u)).map(([p]) => p);
  const signersOf = (f: string) => edges.filter((e) => e.label === "checked by" && e.from === f).flatMap((r) => edges.filter((e) => e.from === r.to && e.label === "signed by").map((e) => e.to));
  const on = new Set<string>(), by = new Set<string>();
  for (const u of casesOf.get(person)?.reads ?? []) for (const d of deciders(u)) on.add(d);
  for (const f of t.get(person)?.keys() ?? []) for (const s of signersOf(f)) on.add(s);
  for (const [p, c] of casesOf) for (const u of c.reads) if (casesOf.get(person)?.decides.has(u)) by.add(p);
  for (const [p, row] of t) for (const f of row.keys()) if (signersOf(f).includes(person)) by.add(p);
  on.delete(person); by.delete(person);
  return { on: [...on], by: [...by] };
}
