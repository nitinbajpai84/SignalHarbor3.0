import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import ConsumeCentre from "./ConsumeCentre";

const trend = [{ period: "2026-08", value: 1 }, { period: "2026-09", value: 9 }];
const BODIES: Record<string, unknown> = {
  "/api/company/feeds": { measures: [{ code: "K09", name: "Single-name exposure", owner: "Mei Tan", latest: trend[1], trend, range_break: true, may_see: true }] },
  "/api/company/market": { briefs: [{}] },
  "/api/company/whatif/scenarios": { scenarios: [] },
};

afterEach(() => vi.unstubAllGlobals());

it("reads the artboard heading and lights only the rooms that have data", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify(BODIES[url]), { status: 200, headers: { "Content-Type": "application/json" } })));
  render(<MemoryRouter><ConsumeCentre /></MemoryRouter>);
  expect(screen.getByRole("heading", { name: "Use the numbers to look ahead." })).toBeInTheDocument();
  expect(screen.getByText("from: live measures, the wall")).toBeInTheDocument();
  expect(await screen.findByText("1 with a value")).toBeInTheDocument();
  expect(screen.getByText("K09 outside its usual range")).toHaveClass("ds-room__count--amber");
  expect(await screen.findByText("1 brief")).toBeInTheDocument();
  const rooms = screen.getByRole("region", { name: "Tools" });
  expect(within(rooms).getByText("Market forces").closest(".ds-room")).toHaveClass("ds-room--open");
  expect(within(rooms).getByText("Feeds").closest(".ds-room")).toHaveClass("ds-room--open");
  expect(within(rooms).getByRole("link", { name: "Open Feeds" })).toHaveAttribute("href", "/centre/consume/feeds");
});
