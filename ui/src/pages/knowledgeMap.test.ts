import { lineageIds, whereRows, type KEdge, type KNode } from "./knowledgeMap";

const N = (id: string, type: string): KNode => ({ id, type, label: id });
const nodes = [N("m1", "Measure"), N("m2", "Measure"), N("s1", "Source"), N("s2", "Source"), N("f1", "Field"), N("f2", "Field"), N("sys", "System"), N("o", "Process")];
const edges: KEdge[] = [
  { from: "m1", to: "s1", type: "fed_by" }, { from: "m2", to: "s2", type: "fed_by" }, { from: "s1", to: "f1", type: "uses" }, { from: "s1", to: "f2", type: "uses" },
  { from: "s1", to: "sys", type: "held_in" }, { from: "f1", to: "sys", type: "held_in" }, { from: "s1", to: "o", type: "produced_by" },
];

describe("knowledge map reads", () => {
  test("a field's lineage holds its source, system, process and measure, and no sibling field or other topic", () => {
    const ids = lineageIds(nodes, edges, "f1");
    expect([...ids].sort()).toEqual(["f1", "m1", "o", "s1", "sys"]);
  });
  test("where it lives, worked out from the map", () => {
    const w = whereRows(nodes, edges, "f1");
    expect(w.heldIn.map((n) => n.id)).toEqual(["sys"]);
    expect(w.feeds.map((n) => n.id)).toEqual(["m1"]);
    expect(w.producedBy.map((n) => n.id)).toEqual(["o"]);
  });
});
