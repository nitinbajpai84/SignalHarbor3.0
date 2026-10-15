import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import type { Plan } from "../b6/api";
import { InStepper } from "../b9/context";
import ArchitectureRoom from "./ArchitectureRoom";
import DashboardsRoom from "./DashboardsRoom";
import PipelinesRoom from "./PipelinesRoom";
import { lastSlot, nextSlot, stages } from "./stages";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

const PLAN: Plan = {
  project_id: "EV-0003", version: 2, model_changes: null, state: "live", proposed_by: "Priya", approved_by: "Anna", approved_at: null, reason: null,
  sources: [{ code: "admin_export", kind: "structured", files: [{ name: "positions.xlsx", state: "Loaded" }], owner: "Mei" }],
  tables: [
    { name: "bronze_admin_positions", layer: "bronze", purpose: "Rows as landed", columns: [{ name: "isin", type: "varchar" }], sql: "select 1", depends_on: [] },
    { name: "gold_ev_holdings", layer: "gold", purpose: "Holdings by month", columns: [{ name: "month", type: "date" }], sql: "select 2", depends_on: ["bronze_admin_positions"] },
  ],
  lineage: [{ from: "bronze_admin_positions", to: "gold_ev_holdings" }], schedule: { freq: "daily", at: "06:00", day: null },
  can: { run_sandbox: true, go_live: true, schedule: true },
};
const NOW = new Date();
const RUN = { run_id: "r1", plan_version: 2, started: new Date(NOW.getTime() - 60000).toISOString(), finished: new Date(NOW.getTime() - 30000).toISOString(), status: "ok", mode: "live",
  steps: [{ table: "gold_ev_holdings", rows: 4, ms: 3, status: "ok" }] };

let RUNS = [RUN];
afterEach(() => { RUNS = [RUN]; });
function mock() {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Anna", company_id: "evergreen", roles: ["analyst"] });
    if (url === "/api/v1/build/p/EV-0003/plan") return json(200, PLAN);
    if (url === "/api/v1/build/p/EV-0003/runs") return json(200, { runs: RUNS });
    if (url === "/api/v1/build/p/EV-0003/chat") return json(200, { turns: [], pending: [] });
    if (url === "/api/v1/build/p/EV-0003/studio") return json(200, { can_make: true, dashboards: [
      { id: "d1", title: "Board pack", status: "published", version: 1, tiles: 3, created_by: "f6e3ecb18b334d86984729adf4ff898a", made_by: "Mei Chen", approved_by: "Priya", updated_at: "", waiting_for_you: false },
      { id: "d2", title: "Fee view", status: "submitted", version: 1, tiles: 1, created_by: "f6e3", made_by: "Mei Chen", updated_at: "", waiting_for_you: true },
      { id: "d3", title: "Old pack", status: "published", version: 1, tiles: 3, created_by: "f6e4", made_by: "Leo Park", approved_by: null, updated_at: "", waiting_for_you: false }] });
    if (url === "/api/v1/model/projects/EV-0003/tables") return json(200, { bronze: ["bronze_admin_positions"], silver: ["position", "entity"], gold: ["gold_ev_holdings"] });
    if (url === "/api/v1/model/layers") return json(200, { bronze: [], silver: { tables: 2 }, gold: [] });
    if (url === "/api/v1/model/tables/position") return json(200, { name: "position", note: "One holding", columns: [{ name: "qty", type: "decimal" }], refs: [{ from: { table: "position", column: "entity_id" }, to: { table: "entity", column: "id" } }] });
    if (url.includes("/diagram")) return json(200, { nodes: [], edges: [], state: "live" });
    return json(404, { error: "not_found", message: "Not found." });
  }));
}
const page = (el: React.ReactElement, path: string) => render(<ThemeProvider><MemoryRouter initialEntries={[`/centre/build/p/EV-0003/${path}`]}><SessionProvider>
  <Routes><Route path="/centre/build/p/:projectId/*" element={el} /></Routes></SessionProvider></MemoryRouter></ThemeProvider>);

describe("stages", () => {
  it("reads a live, on-time project as ok and a missed slot as late", () => {
    expect(stages(PLAN, [RUN as never], NOW).map((s) => s.state)).toEqual(["ok", "ok", "ok", "ok"]);
    const old = { ...RUN, finished: "2020-01-01T00:00:00Z", started: "2020-01-01T00:00:00Z" };
    expect(stages(PLAN, [old as never], NOW).map((s) => s.state)).toEqual(["late", "late", "late", "late"]);
  });
  it("shows new, approved, running and failed", () => {
    expect(stages({ ...PLAN, state: "proposed" }, [], NOW)[3]?.state).toBe("new");
    expect(stages({ ...PLAN, state: "approved" }, [], NOW)[3]?.state).toBe("approved");
    expect(stages(PLAN, [{ ...RUN, status: "running" } as never], NOW)[3]?.state).toBe("running");
    expect(stages(PLAN, [{ ...RUN, status: "failed", steps: [{ table: "gold_ev_holdings", rows: 0, ms: 1, status: "failed" }] } as never], NOW)[3]?.state).toBe("failed");
  });
  it("W2: the Silver card lists the core tables this project's gold reads, never the first tables of the company model", () => {
    const plan: Plan = { ...PLAN, tables: [PLAN.tables[0]!, { ...PLAN.tables[1]!, depends_on: ["position_snapshots", "portfolios"] }],
      lineage: [{ from: "bronze_admin_positions", to: "position_snapshots" }, { from: "position_snapshots", to: "gold_ev_holdings" }, { from: "portfolios", to: "gold_ev_holdings" }] };
    const silver = stages(plan, [], NOW, { silver: ["accounts", "audit_log", "benchmarks", "cash_flows"] })[2]!;
    expect(silver.items).toEqual(["position_snapshots", "portfolios"]);
    expect(stages(PLAN, [], NOW, { silver: ["accounts"] })[2]!.items).toEqual([]); // nothing read: an empty card, not the model
  });
  it("finds the last and next daily slot", () => {
    const now = new Date(2026, 9, 10, 8, 0), s = PLAN.schedule;
    expect(lastSlot(s, now)?.getDate()).toBe(10);
    expect(nextSlot(s, now)?.getDate()).toBe(11);
    expect(lastSlot({ ...s, freq: "on_arrival" }, now)).toBeNull();
  });
});

describe("rooms", () => {
  it("Pipelines: switcher with live counts, four stage cards, controls, Airflow fold and run log", async () => {
    mock(); page(<PipelinesRoom />, "pipelines");
    const nav = await screen.findByRole("navigation", { name: "Build rooms" });
    expect(nav.querySelectorAll("a")).toHaveLength(3);
    expect(nav.querySelector('[data-room="dashboards"]')?.getAttribute("href")).toBe("/centre/build/p/EV-0003/dashboards");
    expect(nav.querySelector('[data-room="pipelines"]')?.getAttribute("aria-current")).toBe("page");
    await screen.findByText("4 of 4 stages ok");
    expect(screen.getByText("2 published, 1 waiting, 0 draft")).toBeInTheDocument();
    expect(screen.getByText("4 tables in 3 layers")).toBeInTheDocument();
    for (const n of ["Sources", "Bronze", "Silver", "Gold"]) expect(screen.getByLabelText(new RegExp(`^${n}: `))).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Go live" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try it on a copy" })).toBeInTheDocument();
    expect(screen.getByText("For engineers")).toBeInTheDocument();
    expect(screen.getByText("Last runs")).toBeInTheDocument();
  });

  it("V6B: the builder comes first; the stage cards, run controls and control totals sit under a For engineers fold", async () => {
    mock(); page(<PipelinesRoom />, "pipelines");
    const fold = (await screen.findByText(/^For engineers: the stages/)).closest("details");
    expect(fold).not.toBeNull();
    expect(fold!.contains(screen.getByLabelText(/^Gold: /))).toBe(true);
    expect(fold!.contains(screen.getByRole("button", { name: "Go live" }))).toBe(true);
    const builder = document.querySelector('[aria-label="Span the builder"]');
    expect(builder === null || (builder.compareDocumentPosition(fold!) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0).toBe(true);
  });

  it("Dashboards: each dashboard with its state and who approved, linked into the studio", async () => {
    mock(); page(<DashboardsRoom />, "dashboards");
    await screen.findByText("Board pack");
    expect(screen.getAllByText("Published")).toHaveLength(2);
    expect(screen.getByText("Waiting for approval")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/approved by Priya/)).toBeInTheDocument());
    expect(screen.getByText(/made by Leo Park · published before approvals were needed/)).toBeInTheDocument();  // UC10-07: a name, never the account id
    expect(screen.queryByText(/f6e3ecb1|the approver/)).toBeNull();
    expect(screen.getByRole("link", { name: "Open the studio" }).getAttribute("href")).toBe("/centre/build/p/EV-0003/studio");
    expect(screen.getByRole("link", { name: "Board pack" }).getAttribute("href")).toContain("studio?d=d1");
  });

  it("Architecture: layers with tables, a table opens columns, relationships and lineage; Span is beside it", async () => {
    mock(); page(<ArchitectureRoom />, "architecture");
    await screen.findByRole("button", { name: "position" });
    expect(screen.getByRole("button", { name: "gold_ev_holdings" })).toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: "Ask Span about the model" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "position" }));
    const d = await screen.findByLabelText("Table position");
    expect(d).toHaveTextContent("qty");
    expect(d).toHaveTextContent("position.entity_id points to entity.id");
    await userEvent.click(screen.getByRole("button", { name: "gold_ev_holdings" }));
    expect(await screen.findByLabelText("Table gold_ev_holdings")).toHaveTextContent("bronze_admin_positions");
  });
});

describe("W3 gaps", () => {
  it("pages the run log five at a time, newest first", async () => {
    RUNS = Array.from({ length: 7 }, (_, i) => ({ ...RUN, run_id: `r${i}`, plan_version: 100 + i }));
    mock();
    page(<PipelinesRoom />, "pipelines");
    expect(await screen.findByText(/Runs 1 to 5 of 7/)).toBeInTheDocument();
    expect(screen.getByText(/plan version 104:/)).toBeInTheDocument();
    expect(screen.queryByText(/plan version 105:/)).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Older runs" }));
    expect(screen.getByText(/Runs 6 to 7 of 7/)).toBeInTheDocument();
    expect(screen.getByText(/plan version 105:/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Older runs" })).toBeDisabled();
  });

  it("does not repeat the All projects and Plan and Span links the step rail already shows", async () => {
    mock();
    render(<ThemeProvider><MemoryRouter initialEntries={["/centre/build/p/EV-0003/pipelines"]}><SessionProvider><InStepper.Provider value={true}>
      <Routes><Route path="/centre/build/p/:projectId/*" element={<PipelinesRoom />} /></Routes></InStepper.Provider></SessionProvider></MemoryRouter></ThemeProvider>);
    await screen.findByText(/Run it, schedule it/);
    expect(screen.queryByRole("link", { name: "Plan and Span" })).toBeNull();
    expect(screen.queryByRole("link", { name: "All projects" })).toBeNull();
  });
});
