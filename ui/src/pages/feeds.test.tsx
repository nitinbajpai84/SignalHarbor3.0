import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import FeedsPage from "./FeedsPage";

const trend = [1, 2, 3, 9].map((value, i) => ({ period: `2026-0${i + 1}`, value }));
const FEEDS = { measures: [
  { code: "NAV", name: "Net asset value", owner: "Mei Tan", latest: trend[3], trend, range_break: true, may_see: true, mine: true },
  { code: "FEE", name: "Fee income", owner: "Wei Chen", latest: null, trend: [], range_break: false, may_see: false, mine: false },
] };

function load(body: unknown = FEEDS) {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } })));
  render(<MemoryRouter><FeedsPage /></MemoryRouter>);
}

it("shows a card with its value, a sparkline, the owner and the range warning", async () => {
  load();
  expect(await screen.findByText("Net asset value")).toBeInTheDocument();
  expect(screen.getByText("9")).toBeInTheDocument();
  expect(screen.getByRole("img", { name: "Trend" })).toBeInTheDocument();
  expect(screen.getByText("Owner: Mei Tan")).toBeInTheDocument();
  expect(screen.getByText("Outside its usual range")).toBeInTheDocument();
});

it("names a restricted measure and who to ask, without a value", async () => {
  load();
  await waitFor(() => expect(screen.getByText("Fee income")).toBeInTheDocument());
  expect(screen.getByText("Restricted: ask Wei Chen")).toBeInTheDocument();
});

it("puts the governed measures first and marks the ones not governed yet", async () => {
  const mart = { code: "CASH", name: "CASH", owner: null, latest: trend[3], trend, range_break: false, may_see: true, mine: false, governed: false, restricted: null };
  load({ measures: [mart, ...FEEDS.measures] });
  const list = await screen.findByRole("region", { name: "Feeds" });
  const cards = within(list).getAllByRole("link");
  expect(cards.map((c) => c.getAttribute("href"))).toEqual(["/centre/consume/feeds/NAV", "/centre/consume/feeds/FEE", "/centre/consume/feeds/CASH"]);
  expect(within(cards[2]!).getByText("Not governed yet")).toBeInTheDocument();
});

it("says all inside the usual range only when no visible measure breaks, else names the measure in amber", async () => {
  load({ measures: [{ ...FEEDS.measures[0]!, range_break: false }] });
  expect(await screen.findByText(/all inside the usual range/)).toBeInTheDocument();
});

it("names the measure that is outside its usual range", async () => {
  load();
  const line = await screen.findByText("NAV outside its usual range");
  expect(line).toHaveClass("ds-warn");
});
