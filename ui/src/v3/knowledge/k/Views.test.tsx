import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import * as client from "../../../api/client";
import KnowledgePage from "../KnowledgePage";
import * as k from "./api";
import { dependencies } from "./people";
import { flowLinks } from "./kinds";
import { forceLayout, placeLabels } from "./Network";
import { pathOf } from "./Lineage";

vi.mock("../../Frame", () => ({ default: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));
vi.mock("../../../api/client", () => ({ getCompany: vi.fn() }));
vi.mock("./api", () => ({ getKnowledge: vi.fn() }));
const made = vi.hoisted(() => ({ calls: [] as unknown[], fail: false, cam: [] as unknown[][], nodes: [] as { id: string }[] }));
vi.mock("3d-force-graph", () => ({
  default: class {
    private self: unknown;
    constructor(_el: HTMLElement, o: unknown) {
      if (made.fail) throw new Error("Error creating WebGL context.");
      made.calls.push(o);
      const stub: Record<string, unknown> = {
        controls: () => ({ autoRotate: false, autoRotateSpeed: 0, addEventListener: () => undefined }), _destructor: () => undefined,
      };
      this.self = new Proxy(stub, { get: (t, p) => (p in t ? t[p as string] : (...a: unknown[]) => {
        if (p === "graphData" && !a.length) return { nodes: made.nodes.map((n) => ({ ...n, x: 10, y: 20, z: 30 })) };
        if (p === "graphData") { made.calls.push({ graphData: a[0] }); made.nodes = (a[0] as { nodes: { id: string }[] }).nodes; }
        if (p === "cameraPosition") made.cam.push(a);
        return this.self;
      }) });
      return this.self as this;
    }
  },
}));

const m = vi.mocked(k);
const at = () => render(<MemoryRouter><KnowledgePage /></MemoryRouter>);
const f = (text: string, source = "Figure record", on = "2026-10-13") => ({ text, source, at: on });
const data = (): k.Knowledge => ({
  nodes: [
    { id: "person:1", kind: "person", label: "Anita Rao", facts: [f("Role: head of data", "Accounts", "")] },
    { id: "person:2", kind: "person", label: "Daniel Foo", facts: [] },
    { id: "person:3", kind: "person", label: "Raj Patel", facts: [] },
    { id: "file:a", kind: "file", label: "bank_2026-10.csv", facts: [f("Arrived and read as bank statement", "Files")] },
    { id: "source:bank", kind: "source", label: "bank statement", facts: [f("3 files read so far", "Files")] },
    { id: "recipe:cash", kind: "recipe", label: "Cash by entity", facts: [f("A written recipe", "Pack recipes", "")] },
    { id: "figure:cash", kind: "figure", label: "Cash", status: "verified", versions: 2, facts: [f("Version 1 of 2, checked and current")] },
    { id: "figure:orphan", kind: "figure", label: "Orphan figure", facts: [] },
    { id: "rule:tol", kind: "rule", label: "Cash may differ by up to 5,000", facts: [f("Cash may differ by up to 5,000", "Signed rule")] },
    { id: "signal:call", kind: "signal", label: "A capital call has arrived", fired: 2, facts: [f("Fired 2 times", "Fired signals")] },
    { id: "usecase:1", kind: "usecase", label: "Capital calls", stage: "live", facts: [] },
  ],
  edges: [
    { from: "file:a", to: "source:bank", label: "feeds", up: "file:a", why: "bank_2026-10.csv was read as bank statement" },
    { from: "figure:cash", to: "source:bank", label: "reads", up: "source:bank", why: "Cash reads bank statement" },
    { from: "figure:cash", to: "recipe:cash", label: "built from", up: "recipe:cash", why: "Cash follows the written recipe Cash by entity" },
    { from: "figure:cash", to: "usecase:1", label: "used by", up: "figure:cash", why: "Capital calls uses Cash" },
    { from: "usecase:1", to: "person:1", label: "asked by", up: "person:1", why: "Anita Rao is who asks this" },
    { from: "person:2", to: "usecase:1", label: "decides", up: "usecase:1" },
    { from: "person:3", to: "usecase:1", label: "reads", up: "usecase:1" },
    { from: "rule:tol", to: "figure:cash", label: "limits", up: "rule:tol", why: "Cash is read against this rule" },
    { from: "figure:cash", to: "rule:tol", label: "checked by", up: "rule:tol" },
    { from: "rule:tol", to: "person:2", label: "signed by", up: "person:2" },
    { from: "signal:call", to: "figure:cash", label: "watches", up: "figure:cash" },
    { from: "signal:call", to: "person:1", label: "goes to", up: "signal:call" },
  ],
  processes: [], things: [{ name: "People", count: 3, new: false }], empty: false,
});
const phone = (on: boolean) => Object.defineProperty(window, "matchMedia", { configurable: true, writable: true, value: (q: string) => ({ matches: on && q.includes("max-width"), addEventListener: () => undefined, removeEventListener: () => undefined }) });
beforeEach(() => {
  vi.resetAllMocks(); made.calls.length = 0; made.cam.length = 0; made.nodes = []; made.fail = false; phone(false);
  vi.mocked(client.getCompany).mockResolvedValue({ company_id: "evergreen", name: "Evergreen", industry: "" });
  m.getKnowledge.mockResolvedValue(data());
});
const open = async (view?: string) => { at(); await screen.findByRole("heading", { name: "How Evergreen works" }); if (view) fireEvent.click(screen.getByRole("button", { name: view })); };

test("the switcher offers the views with the Atlas first and selected; the headline counts the office's own things and links", async () => {
  await open();
  const bar = screen.getByRole("group", { name: "Map views" });
  expect(within(bar).getAllByRole("button").map((b) => b.textContent)).toEqual(["Atlas", "Network", "Lineage flow", "Around a person", "People and figures", "Columns", "List"]);
  expect(within(bar).getByRole("button", { name: "Atlas" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("heading", { name: "Everything Evergreen knows" })).toBeInTheDocument();
  expect(screen.getByText(/11 things and 12 links, each saying what it rests on and why/)).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/ontology|schema/i);
});

test("the Atlas loads the 3D library lazily, legend toggles hide a kind, and a dot opens what it rests on and what it feeds with reasons and receipts", async () => {
  await open();
  await waitFor(() => expect(made.calls[0]).toEqual({ controlType: "orbit" }));
  await waitFor(() => expect(made.calls.map((c) => (c as { graphData?: { nodes: unknown[] } }).graphData?.nodes?.length)).toContain(11));
  const tog = screen.getByRole("button", { name: /^Rules/ });
  fireEvent.click(tog);
  expect(tog).toHaveAttribute("aria-pressed", "false");
  await waitFor(() => expect(made.calls.some((c) => (c as { graphData?: { nodes: unknown[] } }).graphData?.nodes.length === 10)).toBe(true));
  fireEvent.change(screen.getByRole("searchbox", { name: "Search knowledge" }), { target: { value: "cash" } });
  fireEvent.click(screen.getByRole("button", { name: "Figure: Cash" }));
  const panel = screen.getByRole("complementary", { name: "Selected" });
  expect(within(panel).getByText("Rests on 3 things")).toBeInTheDocument();
  expect(within(panel).getByText("Cash follows the written recipe Cash by entity")).toBeInTheDocument();
  expect(within(panel).getByText("Pack recipes")).toBeInTheDocument();
  expect(within(panel).getByRole("heading", { name: "Feeds into" })).toBeInTheDocument();
  expect(within(panel).getByText("Capital calls uses Cash")).toBeInTheDocument();
  fireEvent.click(within(panel).getByRole("button", { name: "Cash by entity" }));  // the chain can be followed
  expect(within(screen.getByRole("complementary", { name: "Selected" })).getByRole("heading", { name: "Cash by entity" })).toBeInTheDocument();
});

test("the camera flies to a figure picked from the search or the side panel; reduced motion jumps there", async () => {
  await open();
  await waitFor(() => expect(made.nodes.length).toBe(11));
  fireEvent.change(screen.getByRole("searchbox", { name: "Search knowledge" }), { target: { value: "cash" } });
  fireEvent.click(screen.getByRole("button", { name: "Figure: Cash" }));
  await waitFor(() => expect(made.cam.at(-1)?.[1]).toMatchObject({ id: "figure:cash" }));
  expect(made.cam.at(-1)?.[2]).toBe(900);
  fireEvent.click(within(screen.getByRole("complementary", { name: "Selected" })).getByRole("button", { name: "Cash by entity" }));
  await waitFor(() => expect(made.cam.at(-1)?.[1]).toMatchObject({ id: "recipe:cash" }));
});

test("with reduced motion the camera jumps instead of flying", async () => {
  Object.defineProperty(window, "matchMedia", { configurable: true, writable: true, value: (q: string) => ({ matches: q.includes("reduce"), addEventListener: () => undefined, removeEventListener: () => undefined }) });
  await open();
  await waitFor(() => expect(made.nodes.length).toBe(11));
  fireEvent.change(screen.getByRole("searchbox", { name: "Search knowledge" }), { target: { value: "cash" } });
  fireEvent.click(screen.getByRole("button", { name: "Figure: Cash" }));
  await waitFor(() => expect(made.cam.at(-1)?.[2]).toBe(0));
});

test("Network cluster names never sit on one another, even when the clusters pile up", () => {
  const nodes = data().nodes, pos = new Map(nodes.map((n) => [n.id, { id: n.id, x: 500, y: 300, r: 6 }]));
  const ls = placeLabels(nodes, pos);
  expect(ls.length).toBe(new Set(nodes.map((n) => n.kind)).size);
  for (const a of ls) for (const b of ls) if (a !== b) expect(Math.abs(a.y - b.y) >= 15 || a.x !== b.x).toBe(true);
});

test("without WebGL the Atlas falls back to the flat network", async () => {
  made.fail = true;
  await open();
  expect(await screen.findByRole("group", { name: "Network map" })).toBeInTheDocument();
});

test("Network: dots are clustered by kind, hovering lights the neighbours and a click focuses", async () => {
  await open("Network");
  const cash = screen.getByRole("button", { name: "Figure: Cash" });
  fireEvent.mouseEnter(cash);
  expect(screen.getByRole("button", { name: "Source: bank statement" }).getAttribute("opacity")).toBe("1");
  expect(screen.getByRole("button", { name: "Figure: Orphan figure" }).getAttribute("opacity")).toBe("0.18");
  fireEvent.mouseLeave(cash);
  fireEvent.click(cash);
  expect(screen.getByText("Version 1 of 2, checked and current")).toBeInTheDocument();
  const a = forceLayout(data().nodes, data().edges), b = forceLayout(data().nodes, data().edges);
  expect([...a.pos.values()]).toEqual([...b.pos.values()]);  // the same records, the same picture
});

test("Lineage flow: files, sources, figures, use cases, people; picking a figure keeps its path and fades the rest", async () => {
  await open("Lineage flow");
  expect(screen.getByRole("group", { name: "Lineage flow" })).toBeInTheDocument();
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "figure:cash" } });
  expect(screen.getByRole("button", { name: "File: bank_2026-10.csv" }).getAttribute("opacity")).toBe("1");
  expect(screen.getByRole("button", { name: "Person: Anita Rao" }).getAttribute("opacity")).toBe("1");
  expect(screen.queryByRole("button", { name: "Figure: Orphan figure" })).toBeNull();  // not joined to anything, so not in the flow
  const links = flowLinks(data().nodes, data().edges);
  expect([...pathOf(links, "figure:cash")].sort()).toEqual(["figure:cash", "file:a", "person:1", "person:2", "person:3", "source:bank", "usecase:1"]);
});

test("Around a person: asks, reaches, and whom they depend on and who relies on them", async () => {
  await open("Around a person");
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "person:3" } });
  expect(screen.getByRole("group", { name: "Map around Raj Patel" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Use case: Capital calls" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Figure: Cash" })).toBeInTheDocument();
  expect(screen.getByText("Depends on")).toBeInTheDocument();
  expect(within(screen.getByRole("group", { name: "Map around Raj Patel" })).getAllByRole("button", { name: "Person: Daniel Foo" }).length).toBe(1);
  expect(dependencies(data().nodes, data().edges, "person:3").on).toContain("person:2");
  expect(dependencies(data().nodes, data().edges, "person:2").by).toContain("person:3");
});

test("Matrix: each cell says uses, signs or gets a signal; a figure nobody has is a gap", async () => {
  await open("People and figures");
  expect(screen.getByRole("cell", { name: "Anita Rao uses it, gets a signal about it: Cash" })).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "Daniel Foo signs it: Cash" })).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "Raj Patel uses it: Cash" })).toBeInTheDocument();
  expect(screen.getByText("No one yet")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("checkbox"));
  expect(screen.queryByRole("button", { name: "Cash" })).toBeNull();
  expect(screen.getByRole("button", { name: "Orphan figure" })).toBeInTheDocument();
});

test("the old column graph is still there, and a phone gets Atlas, Around a person and List only", async () => {
  await open("Columns");
  expect(screen.getByRole("group", { name: "Knowledge map" })).toBeInTheDocument();
});

test("on a phone the switcher is short and the Atlas is the flat map", async () => {
  phone(true);
  await open();
  const bar = screen.getByRole("group", { name: "Map views" });
  expect(within(bar).getAllByRole("button").map((b) => b.textContent)).toEqual(["Atlas", "Around a person", "List"]);
  expect(made.calls).toEqual([]);  // the 3D library is not even asked for
  expect(await screen.findByRole("group", { name: "Network map" })).toBeInTheDocument();
});
