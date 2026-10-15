import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { SourceMapTab } from "./SourceMapTab";

// B37: the source map tab. fetch is stubbed with synthetic data.

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const checks = (ok: boolean[]) => ["arrival", "owner", "fields", "class"].map((key, i) => ({ key, ok: ok[i], trace: `catalogue sources S0: ${key}` }));
const src = (id: string, name: string, zone: string, strategic: boolean, mark: "guessed" | "stated") => ({
  id, name, restricted: false, silhouette: false, zone,
  impact: { count: 2, must: 1, should: 1, score: 0, measures: [{ id: "K1", name: "Headroom", priority: "must" }, { id: "K2", name: "Coverage", priority: "should" }] },
  readiness: { count: 4, of: 4, score: 1, checks: checks([true, true, true, true]) },
  classification: { strategic, reason: "It feeds Must or Should measures and is ready to scan.", mark, by: mark === "stated" ? "Katie" : "Lens", at: mark === "stated" ? "2026-10-07T09:00:00Z" : null, moved_since: false },
});
const DATA = (can = true) => ({
  available: true, written: true, can_confirm: can, left_out: 1, restricted: 1, thresholds: { full: 4, high_from: 2, ready_from: 2 },
  sources: [src("S01", "Performance workbook", "p1", true, "guessed"), src("S02", "Custodian file", "p1", true, "stated"),
    { id: "restricted-1", name: "A restricted source", restricted: true, silhouette: true }],
});

const posts: { url: string; body: Record<string, unknown> }[] = [];
function mock(body: unknown, status = 200) {
  posts.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") { posts.push({ url, body: JSON.parse(String(init.body)) }); return json(200, DATA()); }
    return json(status, body);
  }));
}
afterEach(() => vi.unstubAllGlobals());

test("shows the zone, the traced counts, the guess and the confirmation, and the restricted silhouette", async () => {
  mock(DATA());
  render(<SourceMapTab intentId="ini-1" />);
  expect((await screen.findAllByText("Performance workbook")).length).toBeGreaterThan(0);
  expect(screen.getAllByText(/Feeds 1 Must and 1 Should measures/).length).toBe(2);
  expect(screen.getAllByText(/catalogue sources S0: owner/).length).toBeGreaterThan(0);
  expect(screen.getByText(/Lens's draft, a guess, not yet confirmed/)).toBeInTheDocument();
  expect(screen.getByText(/Confirmed by Katie/)).toBeInTheDocument();
  expect(screen.getAllByText("A restricted source").length).toBeGreaterThan(0);
  expect(screen.queryByText("restricted-1")).toBeNull();
  expect(screen.getByText(/2 sources placed, 1 confirmed by a person, 1 restricted, 1 left out/)).toBeInTheDocument();
});

test("a confirmation needs a reason, then goes to the server with it", async () => {
  mock(DATA());
  render(<SourceMapTab intentId="ini-1" />);
  await screen.findAllByText("Performance workbook");
  fireEvent.click(screen.getAllByText("Confirm as not strategic")[0]!);
  expect(await screen.findByText("Please give a reason, in a sentence.")).toBeInTheDocument();
  expect(posts).toHaveLength(0);
  fireEvent.change(screen.getAllByLabelText("Reason (a sentence)")[0]!, { target: { value: "Only used once a year." } });
  fireEvent.click(screen.getAllByText("Confirm as not strategic")[0]!);
  await waitFor(() => expect(posts).toHaveLength(1));
  expect(posts[0]!.url).toBe("/api/intents/sources/map?intent_id=ini-1");
  expect(posts[0]!.body).toEqual({ source_id: "S01", strategic: false, reason: "Only used once a year." });
});

test("a person who may not confirm sees no buttons; no baseline says what is missing", async () => {
  mock(DATA(false));
  const { unmount } = render(<SourceMapTab intentId="ini-1" />);
  await screen.findAllByText("Performance workbook");
  expect(screen.queryByText("Confirm as strategic")).toBeNull();
  expect(screen.queryByText("Ask Lens to draft")).toBeNull();
  unmount();
  mock({ available: false, sources: [], missing: "x" });
  render(<SourceMapTab intentId="ini-1" />);
  expect(await screen.findByText(/Not available yet. This Initiative has no baseline catalogue/)).toBeInTheDocument();
});
