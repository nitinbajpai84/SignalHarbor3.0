import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

import { ThemeProvider } from "../theme";
import { OpportunitiesPanel, OpportunityDrawer, SuggestedCard, type Opportunity } from "./OpportunitiesPanel";

// Spec 56. fetch is stubbed with synthetic data.
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const NO_CAN = { raise: false, add_evidence: false, dispute: false, pick_up: false, park: false, dismiss: false, bring_back: false };
const opp = (o: Partial<Opportunity> = {}): Opportunity => ({
  id: "opp-0001", title: "Monday price file", state: "proposed", noticed_by: "The operations monitor", noticed_at: "2026-10-05T07:10:00+00:00", areas: [],
  touches: { measures: [{ id: "K12", name: "Stale-valuation share" }], processes: [], sources: ["custodian_prices"] },
  pattern: { text: "The price file arrived late on four Mondays.", periods: [], numbers: [{ label: "Late Monday arrivals", value: 4, unit: "runs", trace: { kind: "run", ref: "warehouse/runs.json#custodian_prices:Monday", at: "2026-10-05" } }] },
  evidence: [{ id: "e1", text: "Same manual override each Monday", kind: "supports", source: null, by: "Katie", at: "2026-10-05T10:00:00+00:00" }],
  judgement: { fits: true, why: "It crosses a source, a process step and a measure.", confidence: "fairly_sure", start_answers: { goal: { value: "Stop late files", mark: "guessed" } } },
  picked_up_by: null, became: null, parked: null, dismissed: null, history: [{ at: "2026-10-05T07:10:00+00:00", by: "The operations monitor", action: "noticed", note: null }],
  can: NO_CAN, href: "/centre/intent/backlog?opportunity=opp-0001", start_href: "/centre/intent/new?type=initiative&from=opp-0001", ...o,
});
const LIST = (list: Opportunity[], extra: Record<string, unknown> = {}) => ({ opportunities: list, counters: null, can_raise: false, thresholds: { set: true, missing: [], message: null }, ...extra });

function Where() { const l = useLocation(); return <p data-testid="where">{l.pathname + l.search}</p>; }
function mock(list: unknown, one?: Opportunity) {
  const posts: { url: string; body: Record<string, unknown> }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") { posts.push({ url, body: JSON.parse(String(init.body)) }); return json(200, one ?? {}); }
    if (url === "/api/intents/opportunities") return json(200, list);
    if (url.startsWith("/api/intents/opportunities/")) return json(200, one);
    if (url === "/api/intents/areas") return json(200, { areas: [{ id: "a1", name: "Operations" }] });
    return json(200, {});
  }));
  return posts;
}
const wrap = (ui: React.ReactNode) => render(<ThemeProvider><MemoryRouter initialEntries={["/x"]}><Routes><Route path="*" element={<>{ui}<Where /></>} /></Routes></MemoryRouter></ThemeProvider>);
afterEach(() => vi.unstubAllGlobals());

test("ops panel: empty line, and thresholds not set say so", async () => {
  mock(LIST([], { thresholds: { set: false, missing: ["late_arrivals"], message: "Not available yet." }, can_raise: true }));
  wrap(<OpportunitiesPanel variant="ops" />);
  expect(await screen.findByText(/Nothing noticed yet/)).toBeInTheDocument();
  expect(screen.getByText("Not available yet. Set the thresholds in the admin defaults.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Raise an opportunity" })).toBeInTheDocument();
  expect(screen.queryByText("See all on the backlog")).toBeNull();
});

test("home panel is not drawn when nothing is open, and the dashed card has the label and no state pill", async () => {
  mock(LIST([opp({ state: "dismissed" })]));
  const { container } = wrap(<OpportunitiesPanel variant="home" />);
  await waitFor(() => expect(globalThis.fetch).toHaveBeenCalled());
  expect(container.querySelector("details")).toBeNull();
  vi.unstubAllGlobals();
  mock({});
  wrap(<SuggestedCard o={opp()} />);
  const card = await screen.findByRole("link", { name: /Suggested by North from the records/ });
  expect(card.style.border).toContain("dashed");
  expect(screen.getByText("Fairly sure")).toBeInTheDocument();
  expect(screen.queryByText("Proposed")).toBeNull();
});

test("home panel shows the first three open rows with North's one line, then Show all", async () => {
  mock(LIST([1, 2, 3, 4].map((n) => opp({ id: `opp-000${n}`, title: `T${n}` }))));
  wrap(<OpportunitiesPanel variant="home" />);
  expect(await screen.findByText("T1")).toBeInTheDocument();
  expect(screen.queryByText("T4")).toBeNull();
  expect(screen.getAllByText(/It crosses a source, a process step and a measure\./)).toHaveLength(3);
  expect(screen.getByText("Show all (4)")).toBeInTheDocument();
});

test("drawer: Pick it up for the ops manager opens the chooser with from=", async () => {
  const o = opp({ can: { ...NO_CAN, pick_up: true, park: true, dismiss: true, add_evidence: true } });
  const posts = mock({}, { ...o, state: "picked_up" });
  wrap(<OpportunityDrawer id="opp-0001" onClose={() => undefined} />);
  expect(await screen.findByText("It crosses a source, a process step and a measure.", { exact: false })).toBeInTheDocument();
  expect(screen.getByText(/Guessed by North/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Dispute" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Pick it up" }));
  await waitFor(() => expect(screen.getByTestId("where").textContent).toBe("/centre/intent/new?type=initiative&from=opp-0001"));
  expect(posts[0]).toEqual({ url: "/api/intents/opportunities/opp-0001/state", body: { action: "pick_up" } });
});

test("drawer: the analyst disputes with a reason; she cannot pick up, park or dismiss", async () => {
  const o = opp({ can: { ...NO_CAN, add_evidence: true, dispute: true } });
  const posts = mock({}, o);
  wrap(<OpportunityDrawer id="opp-0001" onClose={() => undefined} />);
  await screen.findByText("What was noticed");
  for (const n of ["Pick it up", "Park", "Dismiss"]) expect(screen.queryByRole("button", { name: n })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Dispute" }));
  fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "The file is already fixed" } });
  fireEvent.click(screen.getAllByRole("button", { name: "Dispute" }).pop() as HTMLElement);
  await waitFor(() => expect(posts).toHaveLength(1));
  expect(posts[0]?.url).toBe("/api/intents/opportunities/opp-0001/evidence");
  expect(posts[0]?.body).toMatchObject({ kind: "disputes", text: "The file is already fixed" });
});

test("drawer: parking asks for a reason and a review date; empty states are worded", async () => {
  const o = opp({ state: "noticed", judgement: null, evidence: [], pattern: { text: "", periods: [], numbers: [] }, touches: { measures: [], processes: [], sources: [] }, can: { ...NO_CAN, park: true, dismiss: true } });
  const posts = mock({}, { ...o, state: "parked" });
  wrap(<OpportunityDrawer id="opp-0001" onClose={() => undefined} />);
  expect(await screen.findByText(/North has not judged this yet/)).toBeInTheDocument();
  expect(screen.getByText(/No evidence yet\. Lens adds definitions/)).toBeInTheDocument();
  expect(screen.getByText("Nothing named yet")).toBeInTheDocument();
  expect(screen.getByText(/North drafts these when it judges Yes/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Park" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Park" }));
  fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "Wait for the renewal" } });
  fireEvent.change(screen.getByLabelText("Review date"), { target: { value: "2026-12-01" } });
  fireEvent.click(screen.getAllByRole("button", { name: "Park" }).pop() as HTMLElement);
  await waitFor(() => expect(posts).toHaveLength(1));
  expect(posts[0]?.body).toEqual({ action: "park", reason: "Wait for the renewal", review_date: "2026-12-01" });
});
