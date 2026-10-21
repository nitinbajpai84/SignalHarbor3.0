import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import * as client from "../../../api/client";
import KnowledgePage from "../KnowledgePage";
import * as k from "./api";

vi.mock("../../Frame", () => ({ default: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));
vi.mock("../../../api/client", () => ({ getCompany: vi.fn() }));
vi.mock("./api", () => ({ getKnowledge: vi.fn() }));
const calls = vi.hoisted(() => ({ width: [] as number[], made: 0 }));
vi.mock("3d-force-graph", () => ({
  default: class {
    constructor() {
      calls.made += 1;
      const g: object = new Proxy({}, { get: (_t, p) => (p === "width" ? (w: number) => { calls.width.push(w); return g; } : p === "graphData" ? (d?: unknown) => (d ? g : { nodes: [] }) : p === "controls" ? () => ({ addEventListener: () => undefined }) : () => g) });
      return g as never;
    }
  },
}));

const resize: (() => void)[] = [];
class RO { constructor(f: () => void) { resize.push(f); } observe() { /* the browser calls back on a size change */ } disconnect() { /* nothing held */ } }

const data: k.Knowledge = {
  nodes: [{ id: "person:1", kind: "person", label: "Anita Rao", facts: [] }, { id: "figure:cash", kind: "figure", label: "Cash", facts: [] }],
  edges: [{ from: "person:1", to: "figure:cash", label: "uses" }], processes: [], things: [], empty: false,
};
beforeEach(() => {
  vi.mocked(client.getCompany).mockResolvedValue({ company_id: "e", name: "Evergreen", industry: "" });
  vi.mocked(k.getKnowledge).mockResolvedValue(data);
  vi.stubGlobal("ResizeObserver", RO);
  resize.length = 0; calls.width.length = 0; calls.made = 0;
});
afterEach(() => { vi.unstubAllGlobals(); document.body.style.overflow = ""; });

test("Expand map fills the window and locks the page; Collapse map and Esc bring it back with view and selection kept; the atlas resizes", async () => {
  const { container } = render(<MemoryRouter initialEntries={["/v3/knowledge?tab=more"]}><KnowledgePage /></MemoryRouter>);
  await screen.findByRole("heading", { name: "How Evergreen works" });
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  expect(calls.made).toBe(1);
  const body = () => container.querySelector(".kg-body")!;

  fireEvent.click(screen.getByRole("button", { name: "Expand map" }));
  expect(body()).toHaveClass("kg-big");
  expect(screen.getByRole("dialog", { name: "Knowledge map, expanded" })).toBeInTheDocument();
  expect(document.body.style.overflow).toBe("hidden");
  expect(screen.getAllByRole("searchbox", { name: "Search knowledge" })).toHaveLength(1);
  const before = calls.width.length;
  act(() => resize.forEach((f) => f()));  // the stage changed size: the canvas follows it
  expect(calls.width.length).toBeGreaterThan(before);
  expect(calls.made).toBe(1);  // the same graph, so the zoom is kept

  fireEvent.click(screen.getByRole("button", { name: "Network" }));
  fireEvent.click(screen.getByRole("button", { name: "Figure: Cash" }));
  fireEvent.click(screen.getByRole("button", { name: "Collapse map" }));
  expect(body()).not.toHaveClass("kg-big");
  expect(document.body.style.overflow).toBe("");
  expect(screen.getByRole("button", { name: "Network" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", { name: "Figure: Cash" })).toHaveAttribute("aria-pressed", "true");

  fireEvent.click(screen.getByRole("button", { name: "Expand map" }));
  expect(document.body.style.overflow).toBe("hidden");
  fireEvent.keyDown(document, { key: "Escape" });
  expect(body()).not.toHaveClass("kg-big");
  expect(document.body.style.overflow).toBe("");
  expect(screen.getByRole("button", { name: "Expand map" })).toHaveAttribute("aria-pressed", "false");
});
