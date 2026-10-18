import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

import * as client from "../../api/client";
import KnowledgePage from "./KnowledgePage";
import * as k from "./k/api";
import ThingPage, { impact } from "./ThingPage";

vi.mock("../Frame", () => ({ default: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));
vi.mock("../../api/client", () => ({ getCompany: vi.fn() }));
vi.mock("./k/api", () => ({ getKnowledge: vi.fn(), getThing: vi.fn() }));
vi.mock("3d-force-graph", () => ({ default: class { constructor() { throw new Error("no WebGL in tests"); } } }));

const m = vi.mocked(k);
const node = (id: string, kind: k.Kind, label: string, extra: Partial<k.KNode> = {}): k.KNode => ({ id, kind, label, facts: [], ...extra });
const cash = node("figure:cash", "figure", "Cash after calls", { versions: 2, status: "verified", facts: [{ text: "Latest 4.14m", source: "Note of Capital calls", at: "2026-10-13" }] });
const bank = node("source:bank", "source", "Bank statements"), file = node("file:s1", "file", "stmt1.csv");
const uc = node("usecase:th-1", "usecase", "Capital calls", { stage: "live" });
const people = Array.from({ length: 12 }, (_, i) => node(`person:${i}`, "person", `Person ${String(i).padStart(2, "0")}`));
const sig = node("signal:late", "signal", "Late statement");
const hop = (n: k.KNode, h: number): k.Hop => ({ id: n.id, kind: n.kind, label: n.label, hop: h });
const edge = (from: k.KNode, to: k.KNode, label: string, up: k.KNode, why = ""): k.KEdge => ({ from: from.id, to: to.id, label, up: up.id, why });

/** What the endpoint answers for `up`/`down` steps around the cash figure: bank (1) <- stmt1.csv (2); cash -> capital calls (1) -> 12 people + a signal (2). */
const answer = (id: string, up: number, down: number): k.Thing1 => {
  const rests = [hop(bank, -1), hop(file, -2)], feeds = [hop(uc, 1), ...people.map((p) => hop(p, 2)), hop(sig, 2)];
  const keep = [...rests.filter((h) => -h.hop <= up), ...feeds.filter((h) => h.hop <= down)];
  const edges = [edge(bank, cash, "feeds", bank, "Bank statements feed Cash after calls"), edge(file, bank, "feeds", file), edge(uc, cash, "uses", cash, "Capital calls uses this figure"), ...people.map((p) => edge(p, uc, "reads", uc)), edge(sig, uc, "feeds", sig)];
  const ids = new Set([cash.id, ...keep.map((h) => h.id)]);
  const all = [bank, file, uc, ...people, sig];
  return { node: id === cash.id ? cash : all.find((n) => n.id === id) as k.KNode, nodes: [{ ...cash, hop: 0 }, ...keep.map((h) => ({ ...(all.find((n) => n.id === h.id) as k.KNode), hop: h.hop }))],
    edges: edges.filter((e) => ids.has(e.from) && ids.has(e.to)), rests_on: rests, feeds, up_steps: 2, down_steps: 2 };
};
const Where = () => <p data-testid="where">{useLocation().pathname}</p>;
const at = (path = "/v3/knowledge/thing/figure:cash") => render(<MemoryRouter initialEntries={[path]}><Where /><Routes><Route path="/v3/knowledge/thing/:id" element={<ThingPage />} /></Routes></MemoryRouter>);
beforeEach(() => { vi.resetAllMocks(); vi.mocked(client.getCompany).mockResolvedValue({ company_id: "e", name: "Evergreen", industry: "" }); m.getThing.mockImplementation(async (id, up, down) => answer(id, up, down)); });

test("the page names the thing, shows facts with receipts, status and detail link, and starts at one step each way", async () => {
  at();
  expect(await screen.findByRole("heading", { name: "Cash after calls · figure" })).toBeInTheDocument();
  expect(screen.getByText("Latest 4.14m")).toBeInTheDocument();
  expect(screen.getByText("Note of Capital calls, 2026-10-13")).toBeInTheDocument();
  expect(screen.getByText("Checked")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open the figure page" })).toHaveAttribute("href", "/v3/knowledge/figures/fig-cash");
  expect(m.getThing).toHaveBeenLastCalledWith("figure:cash", 1, 1);
  const map = screen.getByRole("group", { name: "Map of this thing and its neighbours" });
  expect(within(map).getByRole("button", { name: "Source: Bank statements" })).toBeInTheDocument();
  expect(within(map).queryByRole("button", { name: "File: stmt1.csv" })).toBeNull();
  expect(within(map).getByRole("button", { name: "Link: Bank statements feeds Cash after calls: Bank statements feed Cash after calls" })).toBeInTheDocument();  // the reason of a link
});

test("show one more step expands hop by hop on each side and collapses back", async () => {
  at();
  await screen.findByRole("heading", { name: /Cash after calls/ });
  fireEvent.click(screen.getByRole("button", { name: "Show one more step upstream" }));
  expect(await screen.findByRole("button", { name: "File: stmt1.csv" })).toBeInTheDocument();
  expect(m.getThing).toHaveBeenLastCalledWith("figure:cash", 2, 1);
  expect(screen.queryByRole("button", { name: "Show one more step upstream" })).toBeNull();  // the whole chain is drawn
  fireEvent.click(screen.getByRole("button", { name: "Show one more step downstream" }));
  expect(await screen.findByRole("button", { name: "Signal: Late statement" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Back to one step upstream" }));
  await waitFor(() => expect(screen.queryByRole("button", { name: "File: stmt1.csv" })).toBeNull());
  expect(screen.getByRole("button", { name: "Signal: Late statement" })).toBeInTheDocument();
});

test("clicking another box re-centres the page on it: a new address, and the steps start again at one", async () => {
  at();
  fireEvent.click(await screen.findByRole("button", { name: "Show one more step upstream" }));
  fireEvent.click(await screen.findByRole("button", { name: "Source: Bank statements" }));
  await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("/v3/knowledge/thing/source:bank"));
  await waitFor(() => expect(m.getThing).toHaveBeenLastCalledWith("source:bank", 1, 1));
  expect(await screen.findByRole("heading", { name: "Bank statements · source" })).toBeInTheDocument();
});

test("the impact line counts the downstream chain; the lists group by kind, link to each page, and cut long groups at ten", async () => {
  at();
  expect(await screen.findByText("If this changes, 12 people, 1 signal and 1 use case are affected.")).toBeInTheDocument();
  const down = screen.getByRole("region", { name: "Everything that depends on it" });
  expect(within(down).getByRole("heading", { name: /People\s*12/ })).toBeInTheDocument();
  expect(within(down).getByRole("link", { name: "Person 00" })).toHaveAttribute("href", "/v3/knowledge/thing/person:0");
  expect(within(down).queryByRole("link", { name: "Person 10" })).toBeNull();
  fireEvent.click(within(down).getByRole("button", { name: "+2 more" }));
  expect(within(down).getByRole("link", { name: "Person 11" })).toBeInTheDocument();
  expect(within(screen.getByRole("region", { name: "Everything it rests on" })).getByRole("link", { name: "stmt1.csv" })).toBeInTheDocument();
});

test("impact words: none, one, several", () => {
  expect(impact([])).toBe("Nothing depends on this yet.");
  expect(impact([hop(sig, 1)])).toBe("If this changes, 1 signal is affected.");
  expect(impact([hop(cash, 1), hop(cash, 2), hop(sig, 1), ...people.slice(0, 4).map((p) => hop(p, 2))])).toBe("If this changes, 4 people, 2 figures and 1 signal are affected.");
});

test("a failed read offers another try", async () => {
  m.getThing.mockRejectedValueOnce(new Error("The office does not know that thing."));
  at();
  expect(await screen.findByRole("alert")).toHaveTextContent("does not know");
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByRole("heading", { name: /Cash after calls/ })).toBeInTheDocument();
});

test("Open full page: from search results, the Atlas panel and another view's selection", async () => {
  m.getKnowledge.mockResolvedValue({ nodes: [cash, uc], edges: [edge(uc, cash, "uses", cash)], processes: [], things: [], empty: false });
  render(<MemoryRouter><KnowledgePage /></MemoryRouter>);
  fireEvent.change(await screen.findByRole("searchbox", { name: "Search knowledge" }), { target: { value: "cash" } });
  expect(screen.getByRole("link", { name: "Open full page: Cash after calls" })).toHaveAttribute("href", "/v3/knowledge/thing/figure:cash");
  fireEvent.click(screen.getByRole("button", { name: "Figure: Cash after calls" }));  // the search hit selects the dot
  expect(screen.getByRole("link", { name: "Open full page" })).toHaveAttribute("href", "/v3/knowledge/thing/figure:cash");  // the panel
  fireEvent.click(screen.getByRole("button", { name: "Columns" }));
  fireEvent.click(screen.getByRole("button", { name: "Figure: Cash after calls" }));
  expect(screen.getByRole("link", { name: "Open full page" })).toHaveAttribute("href", "/v3/knowledge/thing/figure:cash");
});
