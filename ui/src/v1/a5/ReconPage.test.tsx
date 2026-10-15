import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import { routes } from "./routes";

// K6: shapes are what e3_recon.run_detail writes to recon_runs.jsonl for the two new checks.
const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

const base = { as_of_date: "2026-10-08", cutoff: "2026-10-09T08:00:00+00:00", ran_at: "2026-10-09T08:00:00+00:00", skipped: [] };
const limits = { ...base, recon_code: "limits", checked: 4, breaks: 2, opened: ["c1", "c2"], tolerance_rule_version_id: null,
  rule_words: ["The private equity share must be between 0% and 30% of each portfolio."],
  causes: [{ title: "Limit breached · private equity · Entity B portfolio · 2026-10-08", cause: "real breach" },
    { title: "Limit breached · hedge fund · Entity B portfolio · 2026-10-08", cause: "stale data" }],
  limit_rule_version_ids: ["rv9"] };
const trades = { ...base, recon_code: "trade_vs_admin", checked: 6, breaks: 3, opened: ["c3", "c4", "c5"], tolerance_rule_version_id: "rv7",
  rule_words: ["Trades from the last 30 days must match by trade id, or by instrument, date and amount within 5,000 USD."] };

test("Reconciliations shows the limits and trade checks with the signed rule in words", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url === "/api/auth/me") return json({ display_name: "Mei", company_id: "evergreen", roles: ["analyst"] });
    if (url === "/api/v1/recon/runs") return json([limits, trades]);
    return new Response("{}", { status: 404 });
  }));
  render(<MemoryRouter initialEntries={["/centre/action/reconciliations"]}><ThemeProvider><SessionProvider><Routes>
    {routes.map((r) => <Route key={r.path} path={`/centre/${r.path}`} element={r.element} />)}</Routes></SessionProvider></ThemeProvider></MemoryRouter>);
  expect(await screen.findByText("Limits")).toBeInTheDocument();
  expect(screen.getByText("Trades against the administrator")).toBeInTheDocument();
  expect(screen.getByText("2 limits breached")).toBeInTheDocument();
  expect(screen.getByText("3 differences to look at")).toBeInTheDocument();
  expect(screen.getByText(/private equity share must be between 0% and 30%/)).toBeInTheDocument();
  expect(screen.getByText(/within 5,000 USD/)).toBeInTheDocument();
  expect(screen.getByText(/Entity B portfolio · 2026-10-08: stale data/)).toBeInTheDocument();
});

// Cycle 1 (P3): a2.0, a2.2, a2.8/a5.11, a5.5, a5.7, a8.0, a8.6, j-uc2a.1
const cashOld = { ...base, recon_code: "cash_by_entity", checked: 3, breaks: 1, opened: [], tolerance_rule_version_id: "rv7",
  results: [{ words: "Entity B cash, administrator against trading export: 880,400 against 868,000 USD, a difference of 12,400 USD.", breached: true, case_id: "c9" },
    { words: "Evergreen Family Trust cash, administrator against trading export: 1,150,000 against 1,148,200 USD, a difference of 1,800 USD.", breached: false }] };
const cashEmpty = { ...base, recon_code: "cash_by_entity", as_of_date: "2026-10-09", ran_at: "2026-10-09T09:00:00+00:00", checked: 0, breaks: 0, opened: [],
  skipped: ["Nothing was reported on either side for 2026-10-09, so there was nothing to compare. Pick a day the files cover."], results: [] };
const limitsRerun = { ...limits, opened: [], results: [{ words: "Harborview Semiconductor, Evergreen Liquid portfolio: 2,368,000 USD = 5.75% against a maximum of 5%.", breached: true, case_id: "c1" }],
  questions: [{ instrument: "Pacific Rim Convertible 2029", portfolio: "Evergreen Liquid portfolio", status: "Needs a class", value: "1122000.00", currency: "USD", exposure_pct: "2.72" }] };
const tradesList = { ...trades, checked: 13, matched: 4, opened: [],
  results: [{ words: "Trade not matched · Harborview Semiconductor · 2026-10-06 · T-20261006-005: ...", breached: true, case_id: "c5" },
    { words: "Northwind Logistics · 2026-10-01 · T-20261001-001: matched, buy 1,000 at 10 = 10,000 USD.", breached: false }] };

test("cycle 1: empty day keeps the last result, every card lists its lines with case links and a trail, inside the page frame", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url === "/api/auth/me") return json({ display_name: "Mei", company_id: "evergreen", roles: ["analyst"] });
    if (url === "/api/v1/recon/runs") return json([cashEmpty, limitsRerun, tradesList, cashOld]);
    return new Response("{}", { status: 404 });
  }));
  const { container } = render(<MemoryRouter initialEntries={["/centre/action/reconciliations"]}><ThemeProvider><SessionProvider><Routes>
    {routes.map((r) => <Route key={r.path} path={`/centre/${r.path}`} element={r.element} />)}</Routes></SessionProvider></ThemeProvider></MemoryRouter>);
  expect(await screen.findByText("Nothing to compare")).toBeInTheDocument();                       // a2.0
  expect(screen.queryByText("Everything matches")).toBeNull();
  expect(screen.getByText("1 difference to look at")).toBeInTheDocument();                         // the 8 Oct break stays in view
  expect(screen.getByText(/Entity B cash.*12,400 USD/)).toBeInTheDocument();                        // a2.2 per entity
  expect(screen.getByText(/Evergreen Family Trust cash/)).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "Where is this from?" })).toHaveLength(3);         // a2.2, a5.5, j-uc2a.1: reruns keep the trail
  expect(screen.getAllByRole("link", { name: "Open the case" }).map((a) => a.getAttribute("href")))
    .toEqual(expect.arrayContaining(["/centre/action/cases/c9", "/centre/action/cases/c1", "/centre/action/cases/c5"]));
  expect(screen.getByText(/1,122,000 USD \(2.72% of the portfolio\)/)).toBeInTheDocument();       // a5.7
  expect(screen.getByText(/13 compared, 4 matched/)).toBeInTheDocument();                           // a8.0
  expect(screen.getByText(/T-20261001-001: matched/)).toBeInTheDocument();                         // a8.6
  expect(container.querySelector("section[aria-label='Reconciliations']")?.closest(".ds-frame")).not.toBeNull();  // a2.8, a5.11
});
