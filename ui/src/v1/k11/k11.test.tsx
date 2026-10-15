import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import fixture from "./attribution.fixture.json";
import { routes } from "./routes";

// The fixture has the shape of sh_platform/v1/k11_routes.py with Evergreen September 2026 headline figures (docs/test/10UC-ANSWER-KEY.md P14).
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

function mock(over: Record<string, Response> = {}) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Foo", company_id: "evergreen", roles: ["sponsor"] });
    for (const [k, v] of Object.entries(over)) if (url.startsWith(k)) return v;
    if (url === "/api/v1/benchmarks") return json(200, fixture.definitions);
    if (url.startsWith("/api/v1/office/holdings")) return json(200, fixture.portfolios);
    if (url.startsWith("/api/v1/attribution")) return json(200, fixture.attribution);
    return json(404, { error: "not_found", message: "Not found." });
  }));
}
function open(at: string) {
  render(<MemoryRouter initialEntries={[at]}><ThemeProvider><SessionProvider><Routes>
    {routes.map((r) => <Route key={r.path} path={`/centre/${r.path}`} element={r.element} />)}</Routes></SessionProvider></ThemeProvider></MemoryRouter>);
}

it("shows the active return, the sleeve table and a fund line with its trail buttons", async () => {
  mock();
  open("/centre/consume/what-if?portfolio=EG-LIQUID&code=EG-OFFICE-BLEND&month=2026-09");
  expect(await screen.findByText("+1.4595 pts", { selector: "strong" })).toBeInTheDocument();
  const sleeve = screen.getByText("Private markets").closest("tr") as HTMLElement;
  expect(within(sleeve).getByText("Not held")).toBeInTheDocument();
  expect(within(sleeve).getAllByText("-30.0000 pts").length).toBeGreaterThan(0);
  const fund = screen.getByText("Northwind Logistics").closest("tr") as HTMLElement;
  expect(within(fund).getAllByRole("button", { name: "Where is this from?" })).toHaveLength(2);
  expect(screen.getByText("A fund you may not see")).toBeInTheDocument();
  expect(screen.getByText(/No instrument carries a region attribute/)).toBeInTheDocument();
  expect(screen.getByText("Certified")).toBeInTheDocument();
});

it("speaks plainly when the server refuses", async () => {
  mock({ "/api/v1/attribution": json(404, { error: "not_found", message: "That portfolio was not found." }) });
  open("/centre/consume/what-if?portfolio=EG-NOPE&code=EG-OFFICE-BLEND&month=2026-09");
  expect(await screen.findByRole("alert")).toHaveTextContent("That portfolio was not found.");
});

it("masks a sleeve that holds a fund the viewer may not see and gives no portfolio total", async () => {
  const a = structuredClone(fixture.attribution) as typeof fixture.attribution & { totals: Record<string, unknown> };
  const eq = a.sleeves.find((s) => s.sleeve === "equity") as Record<string, unknown>;
  for (const k of ["portfolio_weight", "active_weight", "portfolio_return", "contribution", "allocation", "selection", "interaction", "total"]) eq[k] = null;
  Object.assign(eq, { masked: true, note: "Some funds in this sleeve are not visible to you", trail: [] });
  Object.assign(a.totals, { partial: true, note: "Some funds in this portfolio are not visible to you, so the totals cover only the sleeves shown.", portfolio_return: null, active_return: null, unexplained: null, reconciles: null });
  mock({ "/api/v1/attribution": json(200, a) });
  open("/centre/consume/what-if?portfolio=EG-LIQUID&code=EG-OFFICE-BLEND&month=2026-09");
  const row = (await screen.findByText("Some funds in this sleeve are not visible to you")).closest("tr") as HTMLElement;
  expect(within(row).getByText("Global equity")).toBeInTheDocument();
  expect(screen.getByText(/so the totals cover only the sleeves shown/)).toBeInTheDocument();
  expect(screen.queryByText("+1.4595 pts", { selector: "strong" })).toBeNull();
});
