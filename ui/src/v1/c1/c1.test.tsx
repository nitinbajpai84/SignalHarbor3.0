import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import ConsumePage from "./ConsumePage";

const trend = [{ period: "2026-07", value: 4 }, { period: "2026-08", value: 5 }];
const BODY = { intents: [{ intent_id: "int-1", title: "Monthly portfolio pack", signature: { name: "Arjun Mehta", at: "2026-10-01" }, kpis: [
  { code: "K01", name: "Total return", unit: "%", owner: "Arjun Mehta", table: "gold.k01", latest: trend[1], trend, range_break: false, reason: null },
  { code: "K02", name: "Fee ratio", unit: "%", owner: null, table: "gold.k02", latest: null, trend: [], range_break: false, reason: "The scan found this partly available: missing fee schedule" },
] }] };
const FIG = { code: "K01", name: "Total return", period: "2026-08", value: 5, table: "gold.k01",
  runs: [{ source_id: "custodian_C1", run: { id: "run-c1-aug", status: "ok", rows: 17 } }], columns: ["period", "value"], rows: [{ period: "2026-08", value: 5 }] };

function load() {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify(String(url).includes("/K01") ? FIG : BODY),
    { status: 200, headers: { "Content-Type": "application/json" } })));
  render(<MemoryRouter><ConsumePage /></MemoryRouter>);
}

it("shows a loaded value, the scan's reason for one not loaded, and opens a figure to its run and rows", async () => {
  load();
  expect(await screen.findByText("5 %")).toBeInTheDocument();
  expect(screen.getByText("Not available yet")).toBeInTheDocument();
  expect(screen.getByText(/missing fee schedule/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Open Total return/ }));
  expect(await screen.findByText(/Loaded from custodian C1/)).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "Where this figure comes from" })).toBeInTheDocument();
});
