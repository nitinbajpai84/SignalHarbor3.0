import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

import MemoryOpening from "./MemoryOpening";
import PackSuggestions from "./PackSuggestions";

// Pack suggestions (spec 49) and North's opening line from memory (spec 46). fetch is stubbed with synthetic data.

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const ITEM = { suggestion_id: "a", type: "initiative", title: "Report to the family on one page", purpose: "One set of numbers", why: "Rebuilt by hand each quarter",
  start_answers: { i1: "x" }, company_areas: ["finance"], label: "x" };
const DATA = { label: "Suggested from what others in the industry usually do", pack: { label: "Family office", version: 1 }, items: [ITEM], dismissed_count: 0, dismissed_ids: [], may_start: true };
const calls: string[] = [];
function stub(data: unknown, opening: unknown = { line: null }) {
  calls.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push(`${init?.method ?? "GET"} ${url}${init?.body ? ` ${init.body}` : ""}`);
    if (url === "/api/intents/suggestions") return json(200, data);
    if (url === "/api/intents/opening-line") return json(200, opening);
    if (url === "/api/intents") return json(201, { id: "ini-1" });
    return json(200, { ok: true });
  }));
}
function Where() { const l = useLocation(); return <p data-testid="where">{l.pathname + l.search}</p>; }
const view = (el: React.ReactNode) => render(<MemoryRouter><Routes><Route path="*" element={<>{el}<Where /></>} /></Routes></MemoryRouter>);

describe("Pack suggestions strip", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows labelled dashed cards and Start this writes a pre-filled draft, marks it picked up and opens the questions", async () => {
    stub(DATA);
    view(<PackSuggestions />);
    expect(await screen.findByText("Report to the family on one page")).toBeInTheDocument();
    expect(screen.getByText(DATA.label, { exact: false })).toBeInTheDocument();
    expect(screen.getByText("Pack: Family office, version 1")).toBeInTheDocument();
    expect(screen.getByText("Why others start here: Rebuilt by hand each quarter")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Start this"));
    await waitFor(() => expect(screen.getByTestId("where").textContent).toBe("/centre/intent/new?type=initiative&draft=ini-1"));
    expect(calls.find((c) => c.startsWith("POST /api/intents "))).toContain('"title":"Report to the family on one page"');
    expect(calls).toContain('POST /api/intents/suggestions/a/picked-up {"intent_id":"ini-1"}');
  });

  it("Not for us is sent to the server and the dismissed ones can be shown again", async () => {
    stub(DATA);
    view(<PackSuggestions />);
    fireEvent.click(await screen.findByText("Not for us"));
    await waitFor(() => expect(calls).toContain("POST /api/intents/suggestions/a/dismiss"));
    stub({ ...DATA, items: [], dismissed_count: 2, dismissed_ids: ["a", "b"] });
    view(<PackSuggestions />);
    fireEvent.click(await screen.findByText("Show 2 dismissed suggestions"));
    await waitFor(() => expect(calls).toContain("POST /api/intents/suggestions/b/restore"));
  });

  it("draws nothing for a person who may not start, or when nothing is left", async () => {
    stub({ ...DATA, items: [], may_start: false });
    const { container } = view(<PackSuggestions />);
    await waitFor(() => expect(calls.length).toBeGreaterThan(0));
    expect(container.querySelector("section")).toBeNull();
  });
});

describe("North's opening line from memory", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("says where the line came from and offers the same shape again", async () => {
    stub(DATA, { line: "Last time you ran a brainstorm with five people, from what North remembers about you.", type: "brainstorm", preference: "You prefer to finish a brainstorm inside the time box." });
    view(<MemoryOpening />);
    expect(await screen.findByText(/Last time you ran a brainstorm with five people/)).toBeInTheDocument();
    expect(screen.getByText("Memory")).toHaveAttribute("href", "/centre/memory");
    fireEvent.click(screen.getByText("Same shape again"));
    await waitFor(() => expect(screen.getByTestId("where").textContent).toBe("/centre/intent/new?type=brainstorm&draft=ini-1"));
  });

  it("says nothing about memory when there is nothing remembered", async () => {
    stub(DATA, { line: null });
    const { container } = view(<MemoryOpening />);
    await waitFor(() => expect(calls).toContain("GET /api/intents/opening-line"));
    expect(container.textContent).toBe("/");
  });
});
