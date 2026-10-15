import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import { DiagramSvg } from "./PlanDiagram";
import { archifySpec, layout, type DNode, type PlanDiagramData } from "./layout";

function plan(): PlanDiagramData {
  const nodes: DNode[] = [];
  const edges: { from: string; to: string }[] = [];
  const add = (id: string, layer: DNode["layer"], isNew = true) => nodes.push({ id, label: id, layer, new: isNew, note: "" });
  add("source:admin", "source", false);
  for (let i = 0; i < 6; i++) { add(`b${i}`, "bronze"); edges.push({ from: "source:admin", to: `b${i}` }); }
  for (let i = 0; i < 6; i++) { add(`s${i}`, "silver", i > 4); edges.push({ from: `b${i}`, to: `s${i}` }); }
  for (let i = 0; i < 6; i++) { add(`g${i}`, "gold"); edges.push({ from: `s${i}`, to: `g${i}` }, { from: `s${(i + 1) % 6}`, to: `g${i}` }); }
  add("consumers", "consumer");
  for (let i = 0; i < 6; i++) edges.push({ from: `g${i}`, to: "consumers" });
  return { project_id: "EV-0003", version: 2, state: "proposed", layers: ["source", "bronze", "silver", "gold", "consumer"], nodes, edges };
}

describe("plan diagram", () => {
  it("places 20 boxes without overlap, layers left to right", () => {
    const l = layout(plan());
    expect(l.nodes).toHaveLength(20);
    for (const a of l.nodes) for (const b of l.nodes) {
      if (a === b) continue;
      const apart = a.x + a.w <= b.x || b.x + b.w <= a.x || a.y + a.h <= b.y || b.y + b.h <= a.y;
      expect(apart).toBe(true);
    }
    const x = (id: string) => l.nodes.find((n) => n.id === id)!.x;
    expect(x("source:admin")).toBeLessThan(x("b0"));
    expect(x("b0")).toBeLessThan(x("s0"));
    expect(x("s0")).toBeLessThan(x("g0"));
    expect(x("g0")).toBeLessThan(x("consumers"));
    expect(l.edges.length).toBe(plan().edges.length);
  });
  it("marks new items and shows the approval state", () => {
    const html = renderToStaticMarkup(<DiagramSvg data={plan()} />);
    expect(html).toContain("Waiting for approval");
    expect(html.match(/>new</g)!.length).toBe(14); // 6 bronze, 1 silver, 6 gold, consumers box (UI test data marks it new)
    expect(JSON.stringify(archifySpec(plan()))).toContain("\"sublabel\":\"new\"");
  });
  it("W2/OB-9: follows the theme (no fixed white), scales to its column instead of cutting the right side", () => {
    const html = renderToStaticMarkup(<DiagramSvg data={plan()} />);
    expect(html).not.toMatch(/fill="#|stroke="#/); // a fixed white ground was a white slab in dark mode
    expect(html).toContain("var(--ds-surface, #ffffff)"); // a downloaded SVG, where the tokens are missing, keeps the light colours
    expect(html).toMatch(/style="width:100%;max-width:\d+px;height:auto/);
  });
  it("W2/OB-9: the two download buttons use the design button, not the browser's white default", async () => {
    const { render, screen } = await import("@testing-library/react");
    const PlanDiagram = (await import("./PlanDiagram")).default;
    const d = plan();
    globalThis.fetch = (async () => new Response(JSON.stringify(d), { status: 200, headers: { "Content-Type": "application/json" } })) as typeof fetch;
    render(<PlanDiagram projectId="EV-0003" />);
    for (const b of await screen.findAllByRole("button", { name: /Download the diagram/ })) expect(b).toHaveClass("ds-btn");
  });
});
