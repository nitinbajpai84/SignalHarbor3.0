import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../theme";
import ReviewView from "./views/ReviewView";

// Weekly check-in review (spec 40). fetch is stubbed with synthetic data.

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const item = (id: string, kind: string, text: string, extra = {}) => ({ id, kind, text, severity: "stopped", count: null, amount: null, ref: "Custody", topic: null, people_count: 1, seen_weeks: 1, fate: null, fate_reason: null, fate_ref: null, by_name: "Aaron Lyle", ...extra });
const week = (over = {}) => ({
  week_key: "2026-09-28", title: "Operations", state: "ready", participants_count: 6, responded_count: 5, read_only: false, clock: null, session: null, closure: null,
  items: [item("1", "broke", "Custody file late", { seen_weeks: 3 }), item("2", "ran", "Month end on time", { ref: "Close" })], broke_open: ["1"],
  digest: { groups: [{ kind: "broke", ref: "Custody", item_ids: ["1"], line: "1 person said: Custody file late Seen 3 weeks.", source_item_ids: ["1"] }, { kind: "ran", ref: "Close", item_ids: ["2"], line: "1 person said: Month end on time", source_item_ids: ["2"] }],
    repeats: [{ item_id: "1", seen_in: ["2026-09-14", "2026-09-21"], split: false }], summary_line: "5 of 6 answered. 2 items." },
  viewer: { is_reviewer: true, can_decide: true, can_close: true }, ...over,
});
function mock(w = week()) {
  const posts: { url: string; body: Record<string, unknown> }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") { posts.push({ url, body: JSON.parse(String(init.body)) }); return json(200, { ok: true }); }
    if (url.includes("/trends")) return json(200, { available: false, closed_weeks: 2, reason: "Not available yet: trends need four closed weeks. This series has 2." });
    if (url.includes("/weeks/")) return json(200, w);
    return json(200, {});
  }));
  return posts;
}
const view = (q = "week=2026-09-28") => render(<ThemeProvider><MemoryRouter initialEntries={[`/centre/intent/i1/review?${q}`]}><Routes><Route path="/centre/intent/:intentId/review" element={<ReviewView />} /></Routes></MemoryRouter></ThemeProvider>);
afterEach(() => vi.unstubAllGlobals());

test("broke item shows repeat chip, needs a decision, and close is disabled until it has one", async () => {
  mock(); view();
  expect(await screen.findByText("Seen 3 weeks")).toBeTruthy();
  expect(screen.getByText("Needs a decision")).toBeTruthy();
  expect((screen.getAllByRole("button", { name: "Close the week" })[0] as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getAllByText("1 broke item still needs a decision").length).toBeGreaterThan(0);
});

test("a fate needs a reason, then saves with the fate_ref", async () => {
  const posts = mock(); view();
  fireEvent.click(await screen.findByRole("button", { name: "Already handled" }));
  fireEvent.click(screen.getByRole("button", { name: "Save decision" }));
  expect(await screen.findByText("Please say why.")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Why? Say it in a line."), { target: { value: "Covered by the vendor review" } });
  fireEvent.change(screen.getByLabelText("Link to what handled it"), { target: { value: "/centre/intent/p9" } });
  fireEvent.click(screen.getByRole("button", { name: "Save decision" }));
  await waitFor(() => expect(posts[0]?.url).toBe("/api/intents/i1/weeks/2026-09-28/items/1/fate"));
  expect(posts[0]?.body).toEqual({ fate: "handled", reason: "Covered by the vendor review", fate_ref: "/centre/intent/p9" });
});

test("a Problem fate opens a pre-filled panel and Create sends the title and areas with the fate (F30)", async () => {
  const posts = mock(week({ areas: ["Operations"] })); view();
  fireEvent.click(await screen.findByRole("button", { name: "Becomes a Problem" }));
  expect((screen.getByLabelText("Title") as HTMLInputElement).value).toBe("Custody file late");
  expect(screen.getByRole("checkbox", { name: "Operations" })).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Why? Say it in a line."), { target: { value: "Third week" } });
  fireEvent.click(screen.getByRole("button", { name: "Create the Problem draft" }));
  await waitFor(() => expect(posts[0]?.body).toMatchObject({ fate: "problem", reason: "Third week", create: { title: "Custody file late", areas: ["Operations"] } }));
});

test("severity reads as labelled counts, the title has no doubled Check-in, and the draft is labelled (F30)", async () => {
  mock(week({ title: "Check-in: Operations", severity_summary: { items: { stopped: 2, slowed: 1, cost: 0, not_marked: 1 }, times: 3, amounts: [] } })); view();
  expect(await screen.findByText(/Stopped us 2, Slowed us 1, Cost money 0, Not marked 1/)).toBeTruthy();
  expect(screen.getByText(/^Check-in: Operations, week of/)).toBeTruthy();
  expect(screen.getAllByText("North's draft, yours to edit").length).toBeGreaterThan(0);
});

test("a person who cannot decide sees no decision control; trends say Not available yet", async () => {
  mock(week({ viewer: { is_reviewer: false, can_decide: false, can_close: false } })); view();
  await screen.findByText("Seen 3 weeks");
  expect(screen.queryByRole("button", { name: "Nothing" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Start review session" })).toBeNull();
});

test("trends below four weeks", async () => {
  mock(); view("view=trends");
  expect(await screen.findAllByText("Not available yet: trends need four closed weeks. This series has 2.")).not.toHaveLength(0);
});
