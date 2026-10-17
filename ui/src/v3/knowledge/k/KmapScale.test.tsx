import type { KEdge, KNode } from "./api";
import { EXPAND, MAX, capGroups, lineageLayout, type Flow } from "./Lineage";
import { INNER, OUTER, personLayout } from "./PersonMap";
import { ties } from "./people";

// A synthetic office at full size: 341 files in six sources, 120 figures, 20 use cases, 8 people.
const SOURCES: [string, number][] = [["bank statement", 83], ["custodian report", 97], ["capital call notice", 61], ["fund ledger", 44], ["payroll file", 30], ["FX fixing sheet", 26]];
function bigOffice(): { nodes: KNode[]; edges: KEdge[] } {
  const nodes: KNode[] = [], edges: KEdge[] = [];
  SOURCES.forEach(([label, n], s) => {
    nodes.push({ id: `source:${s}`, kind: "source", label, facts: [] });
    for (let j = 0; j < n; j++) {
      const id = `file:${s}-${j}`;
      nodes.push({ id, kind: "file", label: `${label.replace(/ /g, "_")}_${j}.csv`, facts: [] });
      edges.push({ from: id, to: `source:${s}`, label: "feeds", up: id, why: `read as ${label}` });
    }
  });
  for (let p = 0; p < 8; p++) nodes.push({ id: `person:${p}`, kind: "person", label: `Person ${p}`, facts: [] });
  for (let u = 0; u < 20; u++) {
    nodes.push({ id: `usecase:${u}`, kind: "usecase", label: `Use case ${u}`, facts: [] });
    edges.push({ from: `usecase:${u}`, to: `person:${u % 8}`, label: "asked by", up: `person:${u % 8}` });
    edges.push({ from: `person:${(u + 1) % 8}`, to: `usecase:${u}`, label: "decides", up: `usecase:${u}` });
    edges.push({ from: `person:${(u + 2) % 8}`, to: `usecase:${u}`, label: "reads", up: `usecase:${u}` });
  }
  for (let f = 0; f < 120; f++) {
    const s = f % SOURCES.length, u = f % 20;
    nodes.push({ id: `figure:${f}`, kind: "figure", label: `Figure ${f}`, facts: [] });
    edges.push({ from: `figure:${f}`, to: `source:${s}`, label: "reads", up: `source:${s}` });
    edges.push({ from: `figure:${f}`, to: `usecase:${u}`, label: "used by", up: `figure:${f}` });
  }
  for (let g = 0; g < 10; g++) {
    nodes.push({ id: `signal:${g}`, kind: "signal", label: `Signal ${g}`, facts: [] });
    edges.push({ from: `signal:${g}`, to: `figure:${g}`, label: "watches", up: `figure:${g}` });
    edges.push({ from: `signal:${g}`, to: "person:0", label: "goes to", up: `signal:${g}` });
  }
  return { nodes, edges };
}
const overlap = (a: { x0: number; x1: number; y0: number; y1: number }, b: { x0: number; x1: number; y0: number; y1: number }) =>
  a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1;
const { nodes, edges } = bigOffice();
const col = (f: Flow, i: number) => f.columns[i] as NonNullable<Flow["columns"][number]>;

test("the office is the size the brief names", () => {
  expect(nodes.filter((n) => n.kind === "file")).toHaveLength(341);
  expect(nodes.filter((n) => n.kind === "figure").length).toBeGreaterThanOrEqual(100);
});

test("lineage: each source is one band with its file count", () => {
  const flow = lineageLayout(nodes, edges, new Set(), null);
  const files = col(flow, 0);
  expect(files.rows).toHaveLength(SOURCES.length);
  expect(files.rows.every((r) => r.band)).toBe(true);
  expect(files.rows.map((r) => r.full)).toContain("bank statement · 83 files");
  expect(files.more).toBe(0);
});

test("lineage: every column is capped at MAX rows, the rest counted as more", () => {
  const flow = lineageLayout(nodes, edges, new Set(), null);
  const figs = col(flow, 2), uses = col(flow, 3), people = col(flow, 4);
  expect(figs.rows).toHaveLength(MAX);
  expect(figs.rows.length + figs.more).toBe(120);
  expect(uses.rows.length + uses.more).toBe(20);
  expect(people.rows).toHaveLength(8);
  expect(flow.h).toBeLessThanOrEqual(900);  // one screen at 1440x900
});

test("lineage: an open band lists up to EXPAND files, then says how many more", () => {
  const flow = lineageLayout(nodes, edges, new Set(["band:source:0"]), null);
  const rows = col(flow, 0).rows;
  expect(rows.filter((r) => r.child && !r.more)).toHaveLength(EXPAND);
  expect(rows.find((r) => r.more)?.label).toBe(`+${83 - EXPAND} more files`);
  expect(flow.h).toBeLessThanOrEqual(900);
});

test("lineage: picking a figure keeps its whole path on screen and opens its source band", () => {
  const flow = lineageLayout(nodes, edges, new Set(), "figure:7");  // figure 7 reads custodian report
  expect(flow.path?.has("source:1")).toBe(true);
  expect(flow.path?.has("file:1-96")).toBe(true);
  const band = col(flow, 0).rows.find((r) => r.key === "band:source:1");
  expect(band?.open).toBe(true);
  expect(band?.hit).toBe(true);
  expect(col(flow, 2).rows.find((r) => r.key === "figure:7")?.hit).toBe(true);
  expect(flow.links.some((l) => l.on)).toBe(true);
  expect(flow.h).toBeLessThanOrEqual(900);
});

test("capGroups keeps the groups that fit and counts the rest; a group on the path is always kept", () => {
  const g = (k: string, hit = false) => [{ key: k, kind: "file" as const, label: k, full: k, covers: [k], hit }];
  expect(capGroups([g("a"), g("b"), g("c")], 2)).toEqual({ kept: [...g("a"), ...g("b")], more: 1 });
  expect(capGroups([g("a"), g("b"), g("c", true)], 2).kept.map((r) => r.key)).toEqual(["a", "b", "c"]);
});

test("around a person: the top items per ring are shown, the rest are counted, and no two labels overlap", () => {
  const t = ties(nodes, edges);
  const L = personLayout(nodes, edges, t, "person:0");
  expect(L.inner.length).toBeLessThanOrEqual(INNER);
  expect(L.outer.length).toBeLessThanOrEqual(OUTER);
  expect(L.inner.length + L.more.inner.length).toBeGreaterThan(INNER);   // the big office overflows both rings
  expect(L.outer.length + L.more.outer.length).toBeGreaterThan(OUTER);
  expect(L.inner.filter((m) => m.label).length).toBeGreaterThanOrEqual(INNER - 2);
  for (const [i, a] of L.boxes.entries()) for (const b of L.boxes.slice(i + 1)) expect(overlap(a.box, b.box)).toBe(false);
});

test("around a person: the most connected items come first on each ring", () => {
  const L = personLayout(nodes, edges, ties(nodes, edges), "person:0");
  const deg = new Map<string, number>();
  for (const e of edges) for (const id of [e.from, e.to]) deg.set(id, (deg.get(id) ?? 0) + 1);
  const d = L.outer.map((m) => deg.get(m.id) ?? 0);
  expect(d.length).toBeGreaterThan(1);
  expect(d).toEqual([...d].sort((a, b) => b - a));
});
