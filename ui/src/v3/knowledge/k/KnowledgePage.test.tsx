import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import * as client from "../../../api/client";
import KnowledgePage from "../KnowledgePage";
import * as k from "./api";

vi.mock("../../Frame", () => ({ default: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));
vi.mock("../../../api/client", () => ({ getCompany: vi.fn() }));
vi.mock("./api", () => ({ getKnowledge: vi.fn() }));
vi.mock("3d-force-graph", () => ({ default: class { constructor() { throw new Error("no WebGL in tests"); } } }));

const m = vi.mocked(k);
const at = () => render(<MemoryRouter><KnowledgePage /></MemoryRouter>);
const data = (over: Partial<k.Knowledge> = {}): k.Knowledge => ({
  nodes: [
    { id: "person:1", kind: "person", label: "Anita Rao", facts: [{ text: "Role: head of data", source: "Accounts", at: "" }] },
    { id: "usecase:1", kind: "usecase", label: "Capital calls", stage: "live", facts: [] },
    { id: "figure:cash", kind: "figure", label: "Cash", facts: [{ text: "Latest 4.14m", source: "Note of Capital calls", at: "2026-10-13" }] },
  ],
  edges: [{ from: "person:1", to: "usecase:1", label: "decides" }, { from: "usecase:1", to: "figure:cash", label: "uses" }],
  processes: [{ title: "Capital calls", lanes: ["Data team"], steps: [{ lane: "Data team", text: "Collect statements" }] }],
  things: [{ name: "People", count: 1, new: false }, { name: "Figures", count: 1, new: true }], empty: false, ...over,
});
beforeEach(() => { vi.resetAllMocks(); vi.mocked(client.getCompany).mockResolvedValue({ company_id: "evergreen", name: "Evergreen", industry: "" }); });

test("the map shows the company, labelled edges and a selected box with its facts; search dims the rest; the views switch", async () => {
  m.getKnowledge.mockResolvedValue(data());
  at();
  expect(screen.getByRole("status")).toHaveTextContent("Reading what the office knows");
  expect(await screen.findByRole("heading", { name: "How Evergreen works" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Columns" }));  // the original graph is one view of the map now
  expect(screen.getByText("decides")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Figure: Cash" }));
  expect(screen.getByText("Latest 4.14m")).toBeInTheDocument();
  expect(screen.getByText("Note of Capital calls, 2026-10-13")).toBeInTheDocument();
  fireEvent.change(screen.getByRole("searchbox", { name: "Search knowledge" }), { target: { value: "anita" } });
  expect(screen.getByRole("button", { name: "Person: Anita Rao" }).getAttribute("opacity")).toBe("1");
  expect(screen.getByRole("button", { name: "Figure: Cash" }).getAttribute("opacity")).toBe("0.2");
  fireEvent.click(screen.getByRole("button", { name: "Processes" }));
  expect(screen.getByText("Collect statements")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Things we track" }));
  expect(screen.getByText(/new this month/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Runs and proof" })).toHaveAttribute("href", "/v3/trust/proof");
});

test("an empty company says so, and a failed read offers another try", async () => {
  m.getKnowledge.mockResolvedValueOnce(data({ nodes: [], edges: [], empty: true }));
  const { unmount } = at();
  expect(await screen.findByText(/Nothing to show yet/)).toBeInTheDocument();
  unmount();
  m.getKnowledge.mockRejectedValueOnce(new Error("I could not read what the office knows just now.")).mockResolvedValueOnce(data());
  at();
  expect(await screen.findByRole("alert")).toHaveTextContent("I could not read");
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  fireEvent.click(await screen.findByRole("button", { name: "Columns" }));
  expect(await screen.findByRole("button", { name: "Figure: Cash" })).toBeInTheDocument();
});
