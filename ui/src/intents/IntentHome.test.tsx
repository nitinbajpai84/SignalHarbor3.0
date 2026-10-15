import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

import { ThemeProvider } from "../theme";
import IntentHome, { type HomeData } from "./IntentHome";

// The Intent Centre home (spec 04) and first run (spec 18). fetch is stubbed with synthetic data.

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const FIRST: HomeData["first_run"] = {
  opening: "Welcome. Nothing has been started at Lakeside Test Co yet. Tell me what you intend to do and I will ask the right questions and keep the clock.",
  suggestions: { state: "ok", heading: "Suggested first, for a family office", strip: "Suggested from what others in the industry usually do",
    source: "Pack: Family office, version 1", items: [{ id: "s1", type: "decision", type_name: "Decision", title: "Decide whether to consolidate custodians", purpose: "One decision" }] },
  types: [{ type: "initiative", name: "Initiative", line: "Run a project or a new initiative, with a clear goal and the people behind it.", chip: "10 working days" }],
  earlier: null, admin_name: "Janet Shaw",
};
const VIEWER = { name: "Janet Shaw", first_name: "Janet", email: "janet@example.test", admin: true, may_start: true, governed: true, opportunities: true, areas: [{ id: "finance", name: "Finance" }] };
const CARD = { id: "i1", type: "problem", type_name: "Problem", title: "Late capital call notices", state: "closing", stage: "Fix", days: "2 days over",
  days_warn: true, organiser: "Janet Shaw", people: "4 people", your_role: "Owner", mine: true, extended: false, extended_note: "", areas: ["finance"], href: "/centre/intent/i1" };
const HOME: HomeData = {
  screen: "home", subline: "1 intent running in your areas, 0 closed this month", cards: [CARD],
  lanes: [{ id: "finance", name: "Finance", cards: [{ id: "i1", also_in: null }] }, { id: "company-wide", name: "Company-wide", cards: [] }],
  your_turn: [], past: [], past_total: 0,
  counters: [{ key: "M01", label: "Intents opened this month", value: "1", note: "This month. All intents", ids: ["i1"] },
    { key: "M02", label: "Closed inside the time box", value: "Not available yet", note: "Missing: nothing has closed", ids: [] }],
  viewer: VIEWER, first_run: FIRST,
};

function Where() { const l = useLocation(); return <p data-testid="where">{l.pathname + l.search}</p>; }
function mock(home: HomeData | "fail") {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/intents/home") return home === "fail" ? json(500, {}) : json(200, home);
    if (url === "/api/intents/waiting") return json(200, { lines: [], count: 0 });
    if (url === "/api/intents/suggestions") return json(200, { label: "Suggested from what others in the industry usually do", pack: { label: "Family office", version: 1 },
      items: [{ suggestion_id: "s1", type: "decision", title: "Decide whether to consolidate custodians", purpose: "One decision", why: "", start_answers: {}, company_areas: [], label: "x" }],
      dismissed_count: 0, dismissed_ids: [], may_start: true });
    if (url === "/api/intents" && init?.method === "POST") return json(201, { id: "dec-1" });
    if (String(url).includes("/picked-up")) return json(200, { ok: true });
    return json(403, { error: "forbidden" });
  }));
}
function view() {
  return render(
    <ThemeProvider><MemoryRouter initialEntries={["/centre/intent"]}>
      <Routes><Route path="/centre/intent/*" element={<><IntentHome /><Where /></>} /></Routes>
    </MemoryRouter></ThemeProvider>,
  );
}

describe("Intent Centre home", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("first run shows North's line, the pack suggestions labelled as suggestions, the five kinds and no counters", async () => {
    mock({ ...HOME, screen: "first_run", cards: [], counters: [] });
    view();
    expect(await screen.findByText("Start your first intent")).toBeInTheDocument();
    expect(await screen.findByText("Decide whether to consolidate custodians")).toBeInTheDocument();
    expect(screen.getByText(/Nothing has been started at Lakeside Test Co yet/)).toBeInTheDocument();
    expect(screen.getByText("Suggested first intents")).toBeInTheDocument();
    expect(screen.getByText("Suggestion")).toBeInTheDocument();
    expect(screen.getByText("Counters and lanes appear after the first intent is opened.")).toBeInTheDocument();
    expect(screen.queryByText("Intents opened this month")).toBeNull();
    fireEvent.click(screen.getByText("Start this"));
    await waitFor(() => expect(screen.getByTestId("where").textContent).toBe("/centre/intent/new?type=decision&draft=dec-1"));
  });

  it("Save and leave arrives with the toast, shown once", async () => {
    mock(HOME);
    render(<ThemeProvider><MemoryRouter initialEntries={[{ pathname: "/centre/intent", state: { toast: "Draft kept in Your drafts" } }]}>
      <Routes><Route path="/centre/intent/*" element={<IntentHome />} /></Routes></MemoryRouter></ThemeProvider>);
    expect(await screen.findByText("Draft kept in Your drafts")).toBeInTheDocument();
  });

  it("a person with no areas gets the copy request panel", async () => {
    mock({ ...HOME, screen: "no_areas", cards: [], viewer: { ...VIEWER, admin: false, may_start: false, name: "Aaron Lyle", first_name: "Aaron" } });
    view();
    expect(await screen.findByText(/Hello Aaron. I cannot show you any intents yet/)).toBeInTheDocument();
    expect(screen.getByText("Copy request")).toBeInTheDocument();
    expect(screen.getByText("Company admin: Janet Shaw")).toBeInTheDocument();
    expect(screen.getByText("Your company admin starts intents for now.")).toBeInTheDocument();
  });

  it("populated: lane, card with role and warn days, counters with Not available yet, Start an intent", async () => {
    mock(HOME);
    view();
    expect(await screen.findByRole("link", { name: "Late capital call notices, Problem, Fix, 2 days over" })).toBeInTheDocument();
    expect(screen.getByText("Owner")).toBeInTheDocument();
    expect(await screen.findByText(/Nothing waits for you/)).toBeInTheDocument();  // B27's strip owns the line
    expect(screen.queryByText("Nothing is running in Company-wide.")).toBeNull();  // a lane with nothing under it is not drawn
    expect(screen.getByText("Nothing has been closed yet. Closed intents will appear here with what came out of them.")).toBeInTheDocument();
    expect(screen.getByText("Missing: nothing has closed")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Start an intent"));
    await waitFor(() => expect(screen.getByTestId("where").textContent).toBe("/centre/intent/new"));
  });

  it("an affected person with no stronger role gets the Affects you chip on the card", async () => {
    mock({ ...HOME, cards: [{ ...CARD, your_role: null, affects_you: true }] });
    view();
    expect(await screen.findByText("Affects you")).toBeInTheDocument();
  });

  it("a failed load says so and offers Try again", async () => {
    mock("fail");
    view();
    expect(await screen.findByText("The centre could not load. Try again.")).toBeInTheDocument();
  });
});
