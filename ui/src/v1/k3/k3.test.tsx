import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import MapPage from "./MapPage";
import OperationsPage from "./OperationsPage";
import { routes } from "./routes";
import fx from "./fixtures.json";

let roles: string[] = ["analyst"];
vi.mock("../../useSession", () => ({ useSession: () => ({ user: { roles } }), useSessionIfAny: () => ({ user: { roles } }) }));

// K3 screens against k3_routes. fixtures.json is real output of the handlers on a seeded company (test_k3.py checks its keys against the
// handlers), so these tests read the shapes the server really sends. fetch is stubbed per route.
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const stub = (over: Record<string, unknown | number> = {}) => vi.stubGlobal("fetch", vi.fn(async (url: string) => {
  const routes: Record<string, unknown> = {
    "/api/v1/centre-map/flow": fx.flow, "/api/v1/centre-map/processes": fx.processes, "/api/v1/centre-map/definitions": fx.definitions,
    "/api/v1/centre-map/health": fx.health, ...over,
    "/api/v1/ops/pipelines": { pipelines: [{ source: "admin", title: "Monthly investment report", owner: "Leela Raman", last_run: { started: "2026-10-12T06:00:00+00:00", status: "ok", rules: [{ passed: true }, { passed: true }] } }] },
  };
  const hit = routes[url];
  return typeof hit === "number" ? json(hit, { message: "Not allowed" }) : hit === undefined ? json(404, {}) : json(200, hit);
}));
afterEach(() => { vi.unstubAllGlobals(); roles = ["analyst"]; });
const openOps = () => render(<ThemeProvider><MemoryRouter initialEntries={["/centre/operations"]}><OperationsPage /></MemoryRouter></ThemeProvider>);
const open = (at = "/centre/map") => render(<ThemeProvider><MemoryRouter initialEntries={[at]}><MapPage /></MemoryRouter></ThemeProvider>);

test("a refused or failed load says so in words", async () => {
  stub({ "/api/v1/centre-map/processes": 403 });
  open("/centre/map?tab=processes");
  expect(await screen.findByRole("alert")).toBeInTheDocument();
});

test("process maps: the signed swim lane is drawn with its lanes and a manual step flagged", async () => {
  stub();
  open("/centre/map?tab=processes");
  expect(await screen.findByRole("button", { name: "Step 1: Collect statements" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Step 2: Review" })).toBeInTheDocument();
  expect(screen.getByText("Manual")).toBeInTheDocument();
  expect(screen.getByText("Operations")).toBeInTheDocument();
  expect(screen.getByText(/Signed 1 Oct 2026/)).toBeInTheDocument();
});

test("process maps: a project the person may only preview shows no steps", async () => {
  const p = fx.processes.processes[0];
  stub({ "/api/v1/centre-map/processes": { processes: [{ ...p, locked: true, process: { steps: [], handovers: [] } }] } });
  open("/centre/map?tab=processes");
  expect(await screen.findByText(/Its steps are for the project team/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Step 1/ })).toBeNull();
});

test("definitions: the concept with each owner's wording", async () => {
  stub();
  open("/centre/map?tab=definitions");
  expect(await screen.findByRole("heading", { name: "Net worth" })).toBeInTheDocument();
  expect(screen.getAllByText(/Assets minus liabilities/).length).toBeGreaterThan(0);
  expect(screen.getAllByText(/Assets less fees/).length).toBeGreaterThan(0);
});

test("operations: late by days, files turned away, and values that cannot be counted read Not available yet, never zero", async () => {
  stub();
  openOps();
  const row = (await screen.findByText("Fund administrator")).closest("tr") as HTMLElement;
  expect(within(row).getByText("Late by 3 days")).toBeInTheDocument();
  const mgr = screen.getByText("Manager statements by email").closest("tr") as HTMLElement;
  expect(within(mgr).getByText("On time")).toBeInTheDocument();
  expect(within(mgr).getByText("3")).toBeInTheDocument(); // two files and one load turned away
});

test("operations: the four count tiles and the live pipelines", async () => {
  stub();
  openOps();
  await screen.findByText("Fund administrator");
  for (const t of ["Sources on time", "Files turned away", "Values older than 90 days"]) expect(screen.getAllByText(t).length).toBeGreaterThan(0);
  const pipes = await screen.findByRole("region", { name: "Pipelines" });
  expect(within(pipes).getByText("Monthly investment report")).toBeInTheDocument();
  expect(within(pipes).getByText("2 of 2")).toBeInTheDocument();
  expect(within(pipes).getByText("Healthy")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Projects" })).toHaveAttribute("href", "/centre/build");   // Build's sub-navigation
});

test("operations: a person with no portfolio sees Not available yet for warehouse counts", async () => {
  stub({ "/api/v1/centre-map/health": fx.health_none });
  openOps();
  const row = (await screen.findByText("Fund administrator")).closest("tr") as HTMLElement;
  expect(within(row).getAllByText("Not available yet")).toHaveLength(3); // older values, unverified, open breaks: never zero. Last received is a date
});

test("operations is the data team's: anyone else is told so", async () => {
  stub({ "/api/v1/centre-map/health": fx.health_refused });
  openOps();
  expect(await screen.findByText("Source health is for the data team.")).toBeInTheDocument();
});

test("the old Health address opens Operations; the old Data flow and Conversations addresses open the ontology", async () => {
  stub();
  const Where = () => <p data-testid="where">{useLocation().pathname}{useLocation().search}</p>;
  const go = (at: string) => render(<ThemeProvider><MemoryRouter initialEntries={[at]}><Routes>
    {routes.map((r) => <Route key={r.path} path={`/centre/${r.path}`} element={r.element} />)}</Routes><Where /></MemoryRouter></ThemeProvider>);
  const a = go("/centre/map?tab=health");
  await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("/centre/operations"));
  a.unmount();
  const b = go("/centre/map?tab=flow&focus=source%3Aadministrator");
  await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("/centre/map?focus=source%3Aadministrator"));
  b.unmount();
  go("/centre/map?tab=conversations");
  await waitFor(() => expect(screen.getByTestId("where").textContent).toBe("/centre/map"));
});

test("Operations lists runs with a TEST or PRODUCTION badge and opens a run's steps", async () => {
  const run = { run_id: "run-20261012-131500-ab12", kind: "pipeline", mode: "test", trigger: "manual", who: "Asha", started: "2026-10-12T13:15:00+00:00", seconds: 3, status: "ok" };
  stub({ "/api/v1/ops/runs": { runs: [run, { ...run, run_id: "run-2", mode: "production", trigger: "schedule" }] },
    [`/api/v1/ops/runs/${run.run_id}`]: { ...run, steps: [{ name: "gold_t_total", layer: "gold", target: "gold_t_total", rows_in: null, inserted: 1, rejected: 0, checks_passed: 1, checks_failed: 0, error: null }] } });
  openOps();
  expect(await screen.findByText("TEST")).toBeInTheDocument();
  expect(screen.getByText("PRODUCTION")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: run.run_id }));
  expect(await screen.findByRole("table", { name: `Steps of ${run.run_id}` })).toBeInTheDocument();
  expect(screen.getByText("1 passed, 0 failed")).toBeInTheDocument();
});
