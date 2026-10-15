import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import fixture from "./benchmark.fixture.json";
import { routes } from "./routes";

// The fixture has the shape of sh_platform/v1/k7_routes.py, with the Evergreen September 2026 figures of docs/test/10UC-UNIVERSE.md.
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

function mock(seen: string[], over: Record<string, Response> = {}) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    seen.push(url);
    if (url === "/api/auth/me") return json(200, { display_name: "Chen", company_id: "evergreen", roles: ["approver"] });
    for (const [k, v] of Object.entries(over)) if (url.startsWith(k)) return v;
    if (url === "/api/v1/benchmarks") return json(200, fixture.definitions);
    if (url.startsWith("/api/v1/benchmarks/comparison")) return json(200, fixture.comparison);
    return json(404, { error: "not_found", message: "Not found." });
  }));
}
function open(at: string) {
  render(<MemoryRouter initialEntries={[at]}><ThemeProvider><SessionProvider><Routes>
    {routes.map((r) => <Route key={r.path} path={`/centre/${r.path}`} element={r.element} />)}</Routes></SessionProvider></ThemeProvider></MemoryRouter>);
}

it("shows the in-progress notice and the policy question, and a table per month", async () => {
  const seen: string[] = [];
  mock(seen);
  open("/centre/consume/benchmark?portfolio=EG-LIQUID&code=EG-OFFICE-BLEND&start=2026-09&end=2026-09");
  const note = await screen.findByRole("region", { name: /version 2/ });
  expect(within(note).getByText("In progress: not used for certified figures.")).toBeInTheDocument();
  expect(within(note).getByText(/Who decides what this benchmark contains/)).toBeInTheDocument();
  const row = (await screen.findByText("September 2026")).closest("tr") as HTMLElement;
  expect(within(row).getByText("4.1667%")).toBeInTheDocument();
  expect(within(row).getByText("2.7072%")).toBeInTheDocument();
  expect(within(row).getByText("+1.4595 pts")).toBeInTheDocument();
  expect(within(row).getByText("Against the liquid sleeve: +1.9065 pts")).toBeInTheDocument();
  // a4.5: sleeve names and shares, not series codes and decimals
  expect(within(row).getByText("Private-markets sleeve (equity index + 300 bps a year), 30%: 3.7502%")).toBeInTheDocument();
  expect(within(row).getByText("Equity index, 42%: 3.5002%")).toBeInTheDocument();
  expect(within(row).queryByText(/IDX\.EQ/)).toBeNull();
  // a4.1: the open question is a link the approver can follow
  expect(within(note).getByRole("link", { name: /Open the question/ })).toHaveAttribute("href", "/centre/action/cases/c1");
  // a4.6: the month boxes use the themed input style
  expect(screen.getByLabelText("From")).toHaveClass("ds-input");
  await userEvent.click(screen.getByText("Where is this from?"));
  expect(screen.getByText(/version 1 \(approved\), in force from/)).toBeInTheDocument();
  expect(within(row).getByText("Certified")).toBeInTheDocument();
  expect(seen).toContain("/api/v1/benchmarks/comparison?portfolio=EG-LIQUID&code=EG-OFFICE-BLEND&start=2026-09&end=2026-09");
});

it("asks for a portfolio before showing anything, and speaks plainly when the server refuses", async () => {
  mock([], { "/api/v1/benchmarks/comparison": json(404, { error: "not_found", message: "That portfolio was not found." }) });
  open("/centre/consume/benchmark");
  const show = await screen.findByRole("button", { name: "Show" });
  expect(show).toBeDisabled();
  await userEvent.type(await screen.findByPlaceholderText("Portfolio code"), "NOPE");
  await userEvent.click(show);
  expect(await screen.findByRole("alert")).toHaveTextContent("That portfolio was not found.");
});

it("says so when no benchmark exists", async () => {
  mock([], { "/api/v1/benchmarks": json(200, { definitions: [] }) });
  open("/centre/consume/benchmark");
  expect(await screen.findByText("No benchmark has been defined yet.")).toBeInTheDocument();
});

it("offers the portfolios the person may see instead of a typed code", async () => {
  const seen: string[] = [];
  mock(seen, { "/api/v1/office/holdings": json(200, { entities: [{ entity_id: "e", entity_name: "E", portfolios: [{ portfolio_id: "pid-1", portfolio_name: "Evergreen Liquid" }] }] }) });
  open("/centre/consume/benchmark");
  const pick = await screen.findByLabelText(/Portfolio/);
  await screen.findByRole("option", { name: "Evergreen Liquid" });
  await userEvent.selectOptions(pick, "pid-1");
  await userEvent.click(screen.getByRole("button", { name: "Show" }));
  await screen.findByText("September 2026");
  expect(seen.some((u) => u.startsWith("/api/v1/benchmarks/comparison?portfolio=pid-1&"))).toBe(true);
});

it("opened from a link with the portfolio code, the list shows the portfolio's name, not the code (a4.5)", async () => {
  mock([], { "/api/v1/office/holdings": json(200, { entities: [{ entity_id: "e", entity_name: "E", portfolios: [{ portfolio_id: "p1", portfolio_name: "Evergreen Liquid portfolio" }] }] }) });
  open("/centre/consume/benchmark?portfolio=EG-LIQUID&code=EG-OFFICE-BLEND&start=2026-09&end=2026-09");
  await screen.findByText("September 2026");
  await screen.findByRole("option", { name: "Evergreen Liquid portfolio" });
  expect(screen.queryByRole("option", { name: "EG-LIQUID" })).toBeNull();
  expect((screen.getByLabelText(/Portfolio/) as HTMLSelectElement).value).toBe("p1");
});

it("shows a portfolio picker while the list loads and retries once, never a typed id; the table scrolls in its own box (JUC4A-02, analyst-uc4-02)", async () => {
  let n = 0;
  const pfs = { entities: [{ entity_id: "e", entity_name: "E", portfolios: [{ portfolio_id: "p1", portfolio_name: "Evergreen Liquid portfolio" }] }] };
  const base = vi.fn(async (url: string) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Raj", company_id: "evergreen", roles: ["approver"] });
    if (url.startsWith("/api/v1/office/holdings")) return (n += 1) === 1 ? json(503, { error: "busy", message: "Busy." }) : json(200, pfs);
    if (url === "/api/v1/benchmarks") return json(200, fixture.definitions);
    if (url.startsWith("/api/v1/benchmarks/comparison")) return json(200, fixture.comparison);
    return json(404, {});
  });
  vi.stubGlobal("fetch", base);
  open("/centre/consume/benchmark");
  await screen.findByRole("option", { name: "Evergreen Liquid portfolio" });
  expect(screen.queryByPlaceholderText("Portfolio code")).toBeNull();
  await userEvent.selectOptions(screen.getByLabelText(/Portfolio/), "p1");
  await userEvent.click(screen.getByRole("button", { name: "Show" }));
  await screen.findByText("September 2026");
  expect(screen.getByRole("table").parentElement).toHaveClass("ds-table-wrap");
});
