import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { ThemeProvider } from "../theme";
import { HypothesisRegions } from "./HypothesisRegions";
import { RadarThresholdsCard } from "./RadarThresholdsCard";
import { RadarView, type RadarOpp } from "./RadarView";

// Spec 57 screens A, C and D. fetch is stubbed with synthetic data.
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const opp = (o: Partial<RadarOpp> = {}): RadarOpp => ({
  id: "opp-1", title: "Idle cash above policy", state: "proposed", belief: "Cash above the stated floor could earn more.", lens: "new_revenue", href: "/centre/intent/backlog?opportunity=opp-1",
  measure: { id: "K01", name: "Idle cash share" }, baseline: { value: 12, unit: "%", periods: ["2026-09"] }, target: null, expected_uplift: null, uplift_missing: "no target",
  confidence: "fairly_sure", evidence_mix: { data: 2, document: 1, voice: 4 }, theme: null, ...o,
});
const radar = (extra: Record<string, unknown> = {}) => ({ opportunities: [opp(), opp({ id: "opp-2", title: "Same wish on two walls", lens: "retention", theme: { voices: 7 }, measure: null, baseline: null, state: "noticed" })], rejected: [], hidden_below_confidence: 0, areas: [{ id: "a1", name: "Operations" }], scan: null, ...extra });
const wrap = (ui: React.ReactNode, at = "/centre/intent?view=radar") => render(<ThemeProvider><MemoryRouter initialEntries={[at]}>{ui}</MemoryRouter></ThemeProvider>);
afterEach(() => vi.unstubAllGlobals());

test("radar: four lens columns with counts, evidence mix, theme chip, Not available yet and a dashed proposed card", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(radar())));
  wrap(<RadarView />);
  expect(await screen.findByText("What the records suggest")).toBeInTheDocument();
  expect(await screen.findByText("New revenue (1)")).toBeInTheDocument();
  expect(screen.getByText("Process cost (0)")).toBeInTheDocument();
  expect(screen.getByText("Retention (1)")).toBeInTheDocument();
  expect(screen.getByText("Risk (0)")).toBeInTheDocument();
  expect(screen.getAllByText(/2 data, 1 document, 4 voices/)).toHaveLength(2);
  expect(screen.getByText("Theme, 7 voices")).toBeInTheDocument();
  expect(screen.getAllByText(/Not available yet/).length).toBeGreaterThan(0);
  expect(screen.getByRole("link", { name: /Idle cash above policy/ }).getAttribute("style")).toContain("dashed");
  expect(screen.getByText("Nothing has been set aside yet.")).toBeInTheDocument();
  expect(screen.getByText(/The radar has not run yet/)).toBeInTheDocument();
});

test("radar: empty line for my line of work, the thresholds notice only for the company admin, and a retry on failure", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(radar({ opportunities: [], can_set_thresholds: true, scan: { last_at: null, read: null, schedule: null, thresholds: { total: 6, missing: ["drift_periods", "window_days"] } } }))));
  wrap(<RadarView />);
  expect(await screen.findByText("Nothing on the radar touches your work yet.")).toBeInTheDocument();
  expect(screen.getByText(/2 of 6 radar thresholds are not set/)).toBeInTheDocument();
  vi.stubGlobal("fetch", vi.fn(async () => { throw new Error("down"); }));
  wrap(<RadarView />);
  expect(await screen.findByRole("alert")).toHaveTextContent("The radar could not be read");
});

test("radar: the area tab asks for the right scope", async () => {
  const f = vi.fn(async (_u: string) => json(radar()));
  vi.stubGlobal("fetch", f);
  wrap(<RadarView />, "/centre/intent?view=radar&tab=areas&focus=a1");
  await screen.findByText("New revenue (1)");
  expect(f.mock.calls.some((c) => String(c[0]) === "/api/intents/radar?scope=area&area=a1")).toBe(true);
});

const HYP = (verdict: "holds" | "broken" = "holds") => ({
  id: "hyp-1", state: "checked", versions: [{
    v: 2, at: "2026-10-06T08:00:00", by: "North", belief: "Idle cash could earn more.", lens: "new_revenue", measure: { id: "K01", name: "Idle cash share" },
    baseline: { value: 12, unit: "%" }, target: null, expected_uplift: null, uplift_missing: "no target", confidence: "not_sure", review_date: null,
    evidence: [
      { id: "e1", record_kind: "data", stance: "supports", text: "Balance feed", trace: null, by: "North" },
      { id: "e2", record_kind: "document", stance: "supports", text: null, trace: null, by: null, restricted: true },
      { id: "e3", record_kind: "voice", stance: "counters", text: "Said on a wall", trace: null, by: null, anonymous: true },
    ],
    counter_check: { looked_for: ["Later periods"], found: ["Held in August"], verdict, why: "It broke in August." }, theme: null,
  }],
});

test("drawer regions: hypothesis, evidence by kind (anonymous and restricted never shown), counter check, and a new version on save", async () => {
  const posts: Record<string, unknown>[] = [];
  vi.stubGlobal("fetch", vi.fn(async (_u: string, init?: RequestInit) => { if (init?.method === "POST") { posts.push(JSON.parse(String(init.body))); return json(HYP()); } return json(HYP()); }));
  wrap(<HypothesisRegions oppId="opp-1" hypothesisRef="hyp-1" canEdit />);
  expect(await screen.findByText(/Idle cash could earn more/)).toBeInTheDocument();
  expect(screen.getByText(/Not available yet: no target/)).toBeInTheDocument();
  expect(screen.getByText("A document you cannot open")).toBeInTheDocument();
  expect(screen.getByText(/Someone, anonymously/)).toBeInTheDocument();
  expect(screen.getByText(/Holds\./)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText(/^Target/), { target: { value: "8" } });
  fireEvent.change(screen.getByLabelText("By"), { target: { value: "2026-12-31" } });
  fireEvent.click(screen.getByRole("button", { name: "Save target" }));
  await waitFor(() => expect(posts).toEqual([{ target: { value: 8, by: "2026-12-31" } }]));
  expect(await screen.findByText("Saved as a new version.")).toBeInTheDocument();
});

test("drawer regions: no hypothesis yet says so; a reader cannot edit; a rejected one says why", async () => {
  wrap(<HypothesisRegions oppId="opp-1" hypothesisRef={null} canEdit />);
  expect(await screen.findByText(/North has not written a hypothesis yet/)).toBeInTheDocument();
  vi.stubGlobal("fetch", vi.fn(async () => json(HYP("broken"))));
  wrap(<HypothesisRegions oppId="opp-1" hypothesisRef="hyp-1" canEdit={false} rejected />);
  expect(await screen.findByText(/Rejected because/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Save target" })).toBeNull();
});

test("thresholds card: empty rows say not set, whole numbers only, saves under opportunity", async () => {
  const puts: Record<string, unknown>[] = [];
  vi.stubGlobal("fetch", vi.fn(async (_u: string, init?: RequestInit) => {
    if (init?.method === "PUT") { puts.push(JSON.parse(String(init.body))); return json({ opportunity: { drift_periods: 3 } }); }
    return json({ opportunity: { drift_periods: null } });
  }));
  wrap(<RadarThresholdsCard />);
  const box = await screen.findByLabelText("Periods of drift");
  expect(screen.getAllByText("Not set: this check stays silent")).toHaveLength(7);
  fireEvent.change(box, { target: { value: "0" } });
  expect(screen.getByRole("alert")).toHaveTextContent("whole number");
  fireEvent.change(box, { target: { value: "3" } });
  fireEvent.click(screen.getByRole("button", { name: "Save radar thresholds" }));
  await waitFor(() => expect(puts).toHaveLength(1));
  expect(((puts[0] as Record<string, Record<string, unknown>>).opportunity as Record<string, unknown>).drift_periods).toBe(3);
  expect(((puts[0] as Record<string, Record<string, unknown>>).opportunity as Record<string, unknown>).window_days).toBeNull();
});

it("says Not available yet once on a line", async () => {
  const { notYet } = await import("./radarCopy");
  expect(notYet("Not available yet: no target")).toBe("Not available yet: no target");
  expect(notYet("no target")).toBe("Not available yet: no target");
  expect(notYet()).toBe("Not available yet");
});
