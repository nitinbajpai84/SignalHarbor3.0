import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import MeasurePage from "./MeasurePage";

const trend = [1, 2, 3, 9].map((value, i) => ({ period: `2026-0${i + 1}`, value }));
const head = { code: "NAV", name: "Net asset value", owner: "Mei Tan", links: { map: "/centre/intent/map/measure:NAV", register: "/centre/register" } };
const FULL = { ...head, may_see: true, restricted: null, trend, latest: trend[3], baseline_id: null,
  change: { previous_period: "2026-03", absolute: 6, percent: 200 }, range: { verdict: "Outside its usual range", outside: true, basis: "Basis text." },
  definition: { business: "Everything we own.", technical: [{ label: "Calculation", text: "holdings minus loans" }] },
  pipeline: { source: "custody", expected: "D+2 09:00", sla: "WD8", last_run: { status: "ok" } } };

function open(body: unknown) {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } })));
  render(<MemoryRouter initialEntries={["/centre/consume/feeds/NAV"]}><Routes><Route path="/centre/consume/feeds/:code" element={<MeasurePage />} /></Routes></MemoryRouter>);
}
afterEach(() => vi.unstubAllGlobals());

describe("measure page", () => {
  it("shows the chart, the period table and the definition", async () => {
    open(FULL);
    expect(await screen.findByRole("img", { name: "Trend over all periods" })).toBeTruthy();
    expect(within(screen.getByRole("region", { name: "Periods" })).getByRole("table").querySelectorAll("tbody tr")).toHaveLength(4);
    expect(screen.getByText("Everything we own.")).toBeTruthy();
    expect(screen.getByText(/Up 6/)).toBeTruthy();
  });
  it("keeps the Ask Lens card with a plain line when no baseline backs the measure", async () => {
    open(FULL);
    expect(await screen.findByText(/Lens answers once this measure has a signed definition/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Ask on the measure's page" })).toHaveAttribute("href", "/centre/intent/map/measure:NAV");
  });
  it("says restricted and shows no values", async () => {
    open({ ...head, may_see: false, restricted: "Restricted: ask Mei Tan" });
    expect(await screen.findByText("Restricted: ask Mei Tan")).toBeTruthy();
    expect(screen.queryByRole("img")).toBeNull();
    expect(screen.queryByRole("table")).toBeNull();
  });
  it("draws the chart with a label per period, the table newest first, the pipeline and Ask Lens", async () => {
    open({ ...FULL, baseline_id: "b1" });
    const chart = await screen.findByRole("img", { name: "Trend over all periods" });
    expect([...chart.querySelectorAll("text")].map((t) => t.textContent)).toEqual(["Jan 26", "Feb 26", "Mar 26", "Apr 26"]);
    const rows = within(screen.getByRole("region", { name: "Periods" })).getAllByRole("row").slice(1);
    expect(rows[0]?.textContent).toBe("Apr 20269");
    expect(screen.getByText(/Custody, expected D\+2 09:00, SLA WD8/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "See it on the map" })).toHaveAttribute("href", "/centre/intent/map/measure:NAV");
    expect(screen.getByRole("textbox", { name: "Ask Lens about this measure" })).toBeTruthy();
  });
  it("states the verdict once, shows the unit and the lowest and highest, and dates in words", async () => {
    open({ ...FULL, unit: "SGD", range: { verdict: "Within its usual range", outside: false, basis: "within 3 spreads of the mean" },
      pipeline: { source: "custodian_daily_file", expected: "Daily", sla: "Not stated", last_run: { status: "ok", ended: "2026-09-01T08:44:00+00:00" } } });
    expect((await screen.findAllByText("Within its usual range")).length).toBeGreaterThan(0);
    expect(screen.queryByText("Inside its usual range")).toBeNull();
    expect(screen.getByText("Lowest").parentElement?.textContent).toContain("1 SGDJan 2026");
    expect(screen.getByText("Highest").parentElement?.textContent).toContain("9 SGDApr 2026");
    expect(screen.getByText(/Custodian daily file, expected daily/).textContent).not.toContain("SLA");
    expect(screen.getByText(/Last run 1 Sept 2026/).textContent).not.toContain("T08");
  });
});
