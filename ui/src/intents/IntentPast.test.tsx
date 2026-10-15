import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../theme";
import IntentBacklog from "./IntentBacklog";
import IntentChain, { chainSentence, type ChainDoc } from "./IntentChain";
import IntentPast, { type PastCard, type PastDoc } from "./IntentPast";

// Past (12), the chain (20) and the backlog (21). fetch is stubbed with synthetic data.

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const CARD: PastCard = {
  id: "bra-1", type: "brainstorm", title: "Custody ideas", purpose: "Lower fees", areas: ["Treasury"], state: "cancelled", opened: "2026-09-01T09:00:00Z",
  closed_at: "2026-09-12T09:00:00Z", closed_month: "2026-09", organiser: "Janet Shaw", people_count: 3, outcome_line: "", cancel_reason: "Overtaken by the audit.",
  next: [], rating: null, tier: "content", role: null, also_in: [], first: true,
};
const COUNTERS = { per_quarter: { "2026 Q3": { brainstorm: 1 } }, outcomes_used: { used: 0, closed: 0 }, targets: { running: 0, done: 0, total: 0 },
  cancelled: 1, closed_with_nothing: 0, average_rating: null, mine: 0, partial: true };
const PAST: PastDoc = {
  months: [{ month: "2026-09", count: 1, bands: [{ area: "Treasury", count: 1, cards: [CARD] }] }], older: false, count: 1, any: true,
  areas: [{ area: "Treasury", count: 1, mine: true }], all_count: 1, tagged: true,
  types: { initiative: 0, brainstorm: 1, pulse: 0, problem: 0, decision: 0 },
  outcomes: { initiative: 0, backlog: 0, problem: 0, nothing: 0, decision_made: 0, cancelled: 1 }, counters: COUNTERS, similar: null, running: [], mine_count: 0,
};
const EMPTY: PastDoc = { ...PAST, months: [], count: 0, any: false, areas: [], all_count: 0 };
const CHAIN: ChainDoc = {
  chain: [
    { id: "bra-1", type: "brainstorm", title: "Treasury ideas", state: "closed", date: "2026-03-06T09:00:00Z", organiser: "Janet Shaw", dir: "from", parent: null, tier: "card", cancel_reason: null, outcome_line: "", link: null },
    { id: "ini-1", type: "initiative", title: "Cash view", state: "closed", date: "2026-03-20T09:00:00Z", organiser: "Daniel Kerr", dir: "self", parent: "bra-1", tier: "content", cancel_reason: null, outcome_line: "",
      link: { kind: "initiative", by: "Janet Shaw", at: "2026-03-07T09:00:00Z", proposed_by: "north", item: null, private_item: true } },
  ],
  hidden: 1, build: null, branches: 0, capped: false,
};

function mock(routes: Record<string, unknown>) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const hit = Object.keys(routes).find((k) => url.startsWith(k));
    return hit ? json(200, routes[hit]) : json(404, { message: "We could not find that." });
  }));
}
function at(path: string, el: ReactElement, pattern: string) {
  return render(<ThemeProvider><MemoryRouter initialEntries={[path]}><Routes><Route path={pattern} element={el} /></Routes></MemoryRouter></ThemeProvider>);
}

describe("Past intents", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows the month, the area band and a cancelled card with its reason", async () => {
    mock({ "/api/intents/past": PAST });
    at("/centre/intent/past", <IntentPast />, "/centre/intent/past");
    expect(await screen.findByText("September 2026")).toBeInTheDocument();
    expect(screen.getByText("Overtaken by the audit.")).toBeInTheDocument();
    expect(screen.getByText("Counted from the intents you can see.")).toBeInTheDocument();
    expect(screen.getByText("Everything the company has intended. Nothing is deleted.")).toBeInTheDocument();
  });

  it("filters by type through the address and the server", async () => {
    mock({ "/api/intents/past": PAST });
    at("/centre/intent/past", <IntentPast />, "/centre/intent/past");
    fireEvent.click(await screen.findByRole("button", { name: "Brainstorm 1" }));
    await waitFor(() => expect((fetch as unknown as { mock: { calls: string[][] } }).mock.calls.some((c) => String(c[0]).includes("type=brainstorm"))).toBe(true));
  });

  it("says so when nothing is in the past yet", async () => {
    mock({ "/api/intents/past": EMPTY });
    at("/centre/intent/past", <IntentPast />, "/centre/intent/past");
    expect(await screen.findByText("Nothing in the past yet.")).toBeInTheDocument();
  });

  it("gives the mine view its own empty state", async () => {
    mock({ "/api/intents/past": EMPTY });
    at("/centre/intent/past?mine=1", <IntentPast />, "/centre/intent/past");
    expect(await screen.findByText("You have not been in an intent yet.")).toBeInTheDocument();
  });
});

describe("The chain", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("draws the steps, marks where you are and counts hidden steps", async () => {
    mock({ "/api/intents/ini-1/chain": CHAIN });
    at("/centre/intent/past/ini-1/chain", <IntentChain />, "/centre/intent/past/:intentId/chain");
    expect((await screen.findAllByText("Treasury ideas")).length).toBe(2);  // the card and its map link
    expect(screen.getByText("Initiative · You are here")).toBeInTheDocument();
    expect(screen.getByText("1 step hidden")).toBeInTheDocument();
    expect(screen.getByText("From a private item")).toBeInTheDocument();
  });

  it("builds one sentence from the links", () => {
    expect(chainSentence(CHAIN)).toBe("This began as the brainstorm 'Treasury ideas' on 6 Mar, then the initiative 'Cash view' on 20 Mar.");
  });
});

describe("Turn this into", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows North's pick and the pre-filled goal, then creates the draft once", async () => {
    const proposal = {
      kinds: [{ kind: "initiative", why: "An idea was chosen in the session.", suggested: true, linked: null }, { kind: "backlog", why: "", suggested: false, linked: null }],
      source: { title: "Treasury ideas", type: "brainstorm", purpose: "Lower fees", version: 3 },
      draft: { kind: "initiative", title: "One checklist", start_answers: [{ n: "goal", answer: { value: { line: "One checklist", why: "" } } }], people: ["Janet Shaw"], areas: ["Operations"], private_item: false },
    };
    mock({ "/api/intents/ini-1/chain": { ...CHAIN, may_link: true, me: "Janet Shaw" }, "/api/intents/ini-1/links/proposal": proposal, "/api/intents/ini-1/links": { link_id: "lnk-1", target: { kind: "initiative", id: "ini-9" } } });
    at("/centre/intent/past/ini-1/chain", <IntentChain />, "/centre/intent/past/:intentId/chain");
    fireEvent.click(await screen.findByRole("button", { name: "Turn this into..." }));
    expect(await screen.findByText("Initiative · North suggests")).toBeInTheDocument();
    expect(screen.getAllByText("One checklist").length).toBeGreaterThan(0);
    expect(screen.getByText("From Treasury ideas")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Create draft" }));
    expect(await screen.findByText("Open the draft")).toHaveAttribute("href", "/centre/intent/new?type=initiative&from=ini-1&draft=ini-9");
  });
});

describe("The backlog", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows the empty state with a way to start a brainstorm", async () => {
    mock({ "/api/intents/backlog": { items: [], areas: [], kinds: { idea: 0, ops_problem: 0, request: 0 }, due: 0, counters: [], leadish: false, tagged: true, any: false, lead_note: "" } });
    at("/centre/intent/backlog", <IntentBacklog />, "/centre/intent/backlog");
    expect(await screen.findByText("Start a brainstorm")).toBeInTheDocument();
    expect(screen.getByText("Not available yet: no backlog items recorded.")).toBeInTheDocument();
  });
});
