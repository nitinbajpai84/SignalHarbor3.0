import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { ThemeProvider } from "../theme";
import ProvingPanel, { ProvingChip, ProvingRulesCard } from "./ProvingPanel";
import type { Proving, Report } from "./provingCopy";

// Spec 58. fetch is stubbed with synthetic data.
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const report = (o: Partial<Report> = {}): Report => ({
  week_key: "2026-10-09", drafted_at: "2026-10-09T01:00:00+00:00", state: "drafted", figures: true,
  before: { value: 12, unit: "days", periods: 6, trace: { kind: "hypothesis", ref: "charter v2" } }, now: { value: 8, unit: "days", period: "2026-09" }, target: { value: 6, unit: "days", by: "2026-12-31" },
  series: [{ period: "2026-07", value: 12 }, { period: "2026-08", value: 10 }, { period: "2026-09", value: 8 }], normal_range: { low: 11, high: 13, periods: 6 },
  notes: [], verdict: "partly", verdict_word: "Partly", confidence_word: "Fairly sure", missing: [], rule: "The latest period is outside the usual range towards the target but not at it.", confidence: "fairly_sure",
  changed_verdict: null, confirmed_by: null, confirmed_at: null, start_period: "2026-08", can: { confirm: true, add_note: true }, ...o,
});
const proving = (o: Partial<Proving> = {}): Proving => ({
  state: "proving", title: "Treasury sweep", sponsor: "Daniel", organiser: "Janet", review_date: "2027-01-31",
  hypothesis: { belief: "A weekly sweep shortens settlement.", lens: "Process cost", measure: { id: "K01", name: "Settlement days" }, target: { value: 6, unit: "days" }, target_by: "2026-12-31", version: 2, href: "/centre/intent/backlog?opportunity=opp-1" },
  start: { at: "2026-08-01", from: "closure", who: null, changed: null }, measure: { code: "K01", name: "Settlement days", unit: "days", grain: "monthly" },
  reports: [{ week_key: "2026-10-09", state: "drafted", verdict_word: "Partly" }], latest: report(), rules: { proving_min_periods: 2, counter_periods: 6 },
  receipts: { named: 2, anonymous: 1 }, review: null, returned_to: null, can: { change_start: true, review: true, confirm_review: false }, ...o,
});
function mock(p: Proving | number, extra?: (url: string) => Response | undefined) {
  const posts: { url: string; body: Record<string, unknown> }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") { posts.push({ url, body: JSON.parse(String(init.body)) }); return json(200, {}); }
    const x = extra?.(url); if (x) return x;
    if (/\/proving$/.test(url)) return typeof p === "number" ? json(p, { detail: "No." }) : json(200, p);
    if (/\/proving\/reports\//.test(url)) return json(200, report());
    return json(200, {});
  }));
  return posts;
}
const wrap = (at: string, ui = <ProvingPanel intentId="ini-1" />) => render(<ThemeProvider><MemoryRouter initialEntries={[at]}>{ui}</MemoryRouter></ThemeProvider>);
afterEach(() => vi.unstubAllGlobals());

test("panel: hypothesis strip, start line, latest report and the rule text", async () => {
  mock(proving());
  wrap("/x");
  expect(await screen.findByText("A weekly sweep shortens settlement.")).toBeInTheDocument();
  expect(screen.getByText(/Frozen at charter v2/)).toBeInTheDocument();
  expect(screen.getByText(/Live since 1 Aug 2026, from the closure on 1 Aug 2026/)).toBeInTheDocument();
  expect(screen.getAllByText("12 days").length).toBeGreaterThan(0);
  expect(screen.getByRole("button", { name: "Change the start date" })).toBeInTheDocument();
  expect(screen.getByText(/A verdict needs 2 periods/)).toBeInTheDocument();
  expect(screen.getByText(/2 named voices, 1 anonymous voice/)).toBeInTheDocument();
});

test("hidden when there is no Proving record", async () => {
  mock(404);
  const { container } = wrap("/x");
  await waitFor(() => expect(fetch).toHaveBeenCalled());
  await waitFor(() => expect(container.textContent).toBe(""));
});

test("empty states: waiting for release, no hypothesis, rules not set, no reports", async () => {
  mock(proving({ state: "waiting", start: null, hypothesis: null, latest: null, reports: [], receipts: null, rules: { proving_min_periods: null, counter_periods: null } }));
  wrap("/x");
  expect((await screen.findAllByText(/Waiting for release: the measure Settlement days is not in a signed release yet\./)).length).toBeGreaterThan(0);
  expect(screen.getByText(/this Initiative carries no hypothesis/)).toBeInTheDocument();
  expect(screen.getByText(/so every verdict reads Too early/)).toBeInTheDocument();
  expect(screen.getByText("No reports yet.")).toBeInTheDocument();
  expect(screen.getByText(/no period of Settlement days has landed/)).toBeInTheDocument();
  expect(screen.getByText(/Nobody raised this from a voice/)).toBeInTheDocument();
});

test("a viewer without figures sees the verdict word and the plain line, no numbers", async () => {
  mock(proving({ latest: report({ figures: false, before: null, now: null, target: null, series: [] }), can: { change_start: false, review: false, confirm_review: false } }));
  wrap("/x");
  expect((await screen.findAllByText("Partly")).length).toBeGreaterThan(0);
  expect(screen.getAllByText("You cannot see this measure's figures.").length).toBeGreaterThan(0);
  expect(screen.queryByText("12 days")).toBeNull();
  expect(screen.queryByRole("button", { name: "Change the start date" })).toBeNull();
});

test("start date change needs a reason, then posts", async () => {
  const posts = mock(proving());
  wrap("/x");
  fireEvent.click(await screen.findByRole("button", { name: "Change the start date" }));
  fireEvent.click(screen.getByRole("button", { name: "Save the start date" }));
  expect(await screen.findByText("A date and a reason are needed.")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Why the start date moved"), { target: { value: "First sweep ran then" } });
  fireEvent.click(screen.getByRole("button", { name: "Save the start date" }));
  await waitFor(() => expect(posts[0]!.url).toBe("/api/intents/ini-1/proving/start"));
  expect(posts[0]!.body.reason).toBe("First sweep ran then");
});

test("weekly report: a changed verdict needs a different word and a reason", async () => {
  const posts = mock(proving());
  wrap("/x?week=2026-10-09");
  expect(await screen.findByText("Week of 9 Oct 2026")).toBeInTheDocument();
  expect(screen.getByText("North found nothing else that moved this measure.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Change the verdict" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirm with this verdict" }));
  expect(await screen.findByText("Choose a different verdict and give a reason.")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("New verdict"), { target: { value: "working" } });
  fireEvent.change(screen.getByLabelText("Why you are changing it"), { target: { value: "Segment moved" } });
  fireEvent.click(screen.getByRole("button", { name: "Confirm with this verdict" }));
  await waitFor(() => expect(posts[0]!.url).toBe("/api/intents/ini-1/proving/reports/2026-10-09/confirm"));
  expect(posts[0]!.body).toEqual({ verdict: "working", reason: "Segment moved" });
});

test("weekly report: plain confirm posts an empty body", async () => {
  const posts = mock(proving());
  wrap("/x?week=2026-10-09");
  fireEvent.click(await screen.findByRole("button", { name: "Confirm this report" }));
  await waitFor(() => expect(posts[0]!.body).toEqual({}));
});

test("weekly report: confirmed report hides the confirm buttons and shows who changed what", async () => {
  mock(proving(), (u) => (/reports\//.test(u) ? json(200, report({ state: "confirmed", confirmed_by: "Janet", confirmed_at: "2026-10-10T08:00:00+00:00", changed_verdict: { from: "partly", to: "working", reason: "Segment moved" } })) : undefined));
  wrap("/x?week=2026-10-09");
  expect(await screen.findByText("North said Partly. Janet changed it to Working: Segment moved.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Confirm this report" })).toBeNull();
});

test("no change report says nothing to confirm", async () => {
  mock(proving(), (u) => (/reports\//.test(u) ? json(200, report({ state: "no_change" })) : undefined));
  wrap("/x?week=2026-10-09");
  expect(await screen.findByText(/No new period of Settlement days since last week\. Nothing to confirm\./)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Confirm this report" })).toBeNull();
});

test("a note needs a record or the words No record", async () => {
  const posts = mock(proving());
  wrap("/x?week=2026-10-09");
  fireEvent.click(await screen.findByRole("button", { name: "Add a note" }));
  fireEvent.change(screen.getByLabelText("Note"), { target: { value: "A feed fix landed" } });
  fireEvent.click(screen.getByRole("button", { name: "Save the note" }));
  expect(await screen.findByText(/either a record or "No record"/)).toBeInTheDocument();
  fireEvent.click(screen.getByLabelText("No record"));
  fireEvent.click(screen.getByRole("button", { name: "Save the note" }));
  await waitFor(() => expect(posts[0]!.body).toEqual({ text: "A feed fix landed", trace: "No record" }));
});

test("review: send stays disabled until the choice is complete, then posts", async () => {
  const posts = mock(proving({ state: "reviewing", review: { summary: "Two reports, both partly.", verdicts: ["Partly", "Partly"], proposed: "send_back", learning: "Reader group B did not move.", sent: false, action: null, by: null, reason: null, review_date: null, returned: null, confirmed_by: null, confirmed_at: null } }));
  wrap("/x?focus=review");
  expect(await screen.findByText("Two reports, both partly.")).toBeInTheDocument();
  const send = screen.getByRole("button", { name: "Send to Daniel" });
  expect(send).toBeEnabled();
  fireEvent.click(screen.getByLabelText(/Give it more time/));
  expect(send).toBeDisabled();
  fireEvent.click(screen.getByLabelText(/Send back to the radar/));
  fireEvent.click(send);
  await waitFor(() => expect(posts[0]!.url).toBe("/api/intents/ini-1/proving/review"));
  expect(posts[0]!.body.action).toBe("send_back");
});

test("review: no confirmed report says North cannot propose; the sponsor returns with a reason", async () => {
  const sent = { action: "keep" as const, by: "Janet", reason: null, review_date: null };
  const posts = mock(proving({ state: "reviewing", can: { change_start: false, review: false, confirm_review: true }, review: { summary: null, verdicts: [], proposed: null, learning: null, sent: true, returned: null, confirmed_by: null, confirmed_at: null, ...sent } }));
  wrap("/x?focus=review");
  expect(await screen.findByText(/No report was confirmed\. North cannot propose an outcome/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Send back to Janet" }));
  expect(screen.getByRole("button", { name: "Send back to Janet" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Why it goes back"), { target: { value: "Check the segment" } });
  fireEvent.click(screen.getByRole("button", { name: "Send back to Janet" }));
  await waitFor(() => expect(posts[0]!.body).toEqual({ return: true, reason: "Check the segment" }));
});

test("chip words", () => {
  const { rerender } = render(<ProvingChip state="waiting" />);
  expect(screen.getByText("Waiting for release")).toBeInTheDocument();
  rerender(<ProvingChip state="returned" />);
  expect(screen.getByText("Sent back to the radar")).toBeInTheDocument();
  rerender(<ProvingChip state="proving" since="2026-08-01" />);
  expect(screen.getByText("Proving since 1 Aug 2026")).toBeInTheDocument();
});

test("rules card saves the periods a verdict needs", async () => {
  const puts: Record<string, unknown>[] = [];
  vi.stubGlobal("fetch", vi.fn(async (_u: string, init?: RequestInit) => {
    if (init?.method === "PUT") { puts.push(JSON.parse(String(init.body))); return json(200, {}); }
    return json(200, { proving: { proving_min_periods: null, counter_periods: 6, report_day: "fri" } });
  }));
  wrap("/x", <ProvingRulesCard />);
  expect(await screen.findByText("Not set: every verdict reads Too early")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Periods a verdict needs"), { target: { value: "2" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(puts[0]!).toEqual({ proving: { proving_min_periods: 2 } }));
});
