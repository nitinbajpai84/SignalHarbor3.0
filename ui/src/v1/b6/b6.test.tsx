import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import type { Plan } from "./api";
import BuildPage from "./BuildPage";
import ProjectsPage from "./ProjectsPage";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

const PLAN: Plan = {
  project_id: "EV-0003", version: 1, model_changes: null, state: "proposed", proposed_by: "Priya", approved_by: null, approved_at: null, reason: null,
  sources: [{ code: "admin_export", kind: "structured", files: [{ name: "positions.xlsx", state: "Loaded" }], owner: "Mei" }, { code: "statements", kind: "unstructured", files: [], owner: "" }],
  tables: [
    { name: "bronze_admin_export_positions", layer: "bronze", purpose: "Rows as landed", columns: [{ name: "isin", type: "varchar" }], sql: "create table bronze_admin_export_positions as select 1", depends_on: [] },
    { name: "gold_ev_holdings_monthly", layer: "gold", purpose: "Holdings by month", columns: [{ name: "month", type: "date" }], sql: "create table gold_ev_holdings_monthly as select 2", depends_on: ["bronze_admin_export_positions"], is_new: true },
  ],
  lineage: [], schedule: { freq: "daily", at: "06:00", day: null },
};

function mock(can: Plan["can"], sent: string[], opts: { empty?: boolean; pending?: unknown[] } = {}) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Anna", company_id: "evergreen", roles: ["analyst"] });
    if (init?.method && init.method !== "GET") { sent.push(`${init.method} ${url} ${String(init.body ?? "")}`); return json(200, { ...PLAN, can }); }
    if (url === "/api/v1/build/projects") return json(200, { projects: [
      { id: "EV-0003", title: "Monthly investment report", owner: "Priya", stage: "build", plan_state: "proposed" },
      { id: "EV-0004", title: "Fee review", owner: null, stage: "intent", plan_state: null }] });
    if (url === "/api/v1/build/p/EV-0003/plan") {
      return json(200, opts.empty ? { project_id: "EV-0003", title: "Monthly", intent_signed: true, versions: [], can, changes: [], log: [], plan: null, state: null } : { ...PLAN, can });
    }
    if (url === "/api/v1/build/p/EV-0003/runs") return json(200, { runs: [] });
    if (url === "/api/v1/build/p/EV-0003/chat") return json(200, { turns: [], pending: opts.pending ?? [] });
    if (url.includes("/diagram")) return json(200, { nodes: [], edges: [], state: "proposed" });
    return json(404, { error: "not_found", message: "Not found." });
  }));
}
const wrap = (at: string) => render(<MemoryRouter initialEntries={[at]}><ThemeProvider><SessionProvider><Routes>
  <Route path="/centre/build" element={<ProjectsPage />} /><Route path="/centre/build/p/:projectId" element={<BuildPage />} /></Routes></SessionProvider></ThemeProvider></MemoryRouter>);

test("the project list shows each build state in words and filters by search", async () => {
  mock({}, []);
  wrap("/centre/build");
  expect(await screen.findByText("Waiting for the head of data")).toBeInTheDocument();
  expect(screen.getByText("No plan yet")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Monthly investment report" }).getAttribute("href")).toBe("/centre/build/p/EV-0003/overview");
  expect(screen.queryByText(/EV-000/)).toBeNull();  // UC10A-004: the title only, no internal id on screen
  await userEvent.type(screen.getByLabelText("Find a project"), "fee");
  expect(screen.queryByText("Monthly investment report")).toBeNull();
  expect(screen.getByText(/Fee review/)).toBeInTheDocument();
});

test("the build page shows sources, tables in layers and the SQL read-only under How it is calculated", async () => {
  mock({}, []);
  wrap("/centre/build/p/EV-0003");
  expect(await screen.findAllByText("1 Sources")).not.toHaveLength(0);
  expect(await screen.findByText("positions.xlsx: Loaded")).toBeInTheDocument();
  expect(screen.getByText("Structured")).toBeInTheDocument();
  expect(screen.getByText("Unstructured")).toBeInTheDocument();
  expect(screen.getByText("gold_ev_holdings_monthly (new)")).toBeInTheDocument();
  expect(screen.getByText("Check Span's plan, then approve it.")).toBeInTheDocument();
  expect(screen.getAllByText("3 Tables")).not.toHaveLength(0);
  expect(screen.getAllByText("How it is calculated")).toHaveLength(2);
  expect(screen.getByLabelText("SQL of gold_ev_holdings_monthly")).toHaveTextContent("select 2");
  expect(screen.queryByRole("textbox", { name: /SQL/ })).toBeNull();
});

test("only the head of data gets Approve and Send back; the reason is needed", async () => {
  const sent: string[] = [];
  mock({ approve: true, reject: true }, sent);
  wrap("/centre/build/p/EV-0003");
  const approve = await screen.findByRole("button", { name: "Approve the plan" });
  const back = screen.getByRole("button", { name: "Send back" });
  expect(approve).toBeDisabled();   // V6 (C2): nothing happens on one click; choose first
  expect(back).toBeDisabled();
  await userEvent.click(screen.getByRole("radio", { name: /Send back to the builder and Span with a note/ }));
  expect(back).toBeDisabled();   // the reason is needed
  await userEvent.type(screen.getByLabelText(/Reason for sending back/), "Add a cash table");
  await userEvent.click(back);
  await waitFor(() => expect(sent.some((s) => s.includes("/plan/reject") && s.includes("Add a cash table"))).toBe(true));
  await userEvent.click(screen.getByRole("radio", { name: /Approve the plan, the builder may try it on a copy/ }));
  await userEvent.clear(screen.getByLabelText(/Note for the builder/));
  await userEvent.type(screen.getByLabelText(/Note for the builder/), "Keep the raw copies shared");
  await userEvent.click(approve);
  await waitFor(() => expect(sent.some((s) => s.includes("/plan/approve") && s.includes("Keep the raw copies shared"))).toBe(true));
});

test("without permission there is no Approve and Go live stays disabled", async () => {
  mock({ run_sandbox: true }, []);
  wrap("/centre/build/p/EV-0003");
  expect(await screen.findByText("Only the head of data can approve this plan.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /^Approve/ })).toBeNull();
  expect(screen.getByRole("button", { name: "Go live" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Try it on a copy" })).toBeEnabled();
});

test("a project with no plan yet offers to ask Span, and does not crash", async () => {
  const sent: string[] = [];
  mock({ propose: true }, sent, { empty: true });
  wrap("/centre/build/p/EV-0003");
  expect(await screen.findByText("Span has not proposed a plan yet.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Ask Span to propose a plan" }));
  await waitFor(() => expect(sent.some((s) => s.startsWith("POST /api/v1/build/p/EV-0003/plan/propose"))).toBe(true));
});

test("a change Span proposes in the conversation has Accept and Not this buttons", async () => {
  const sent: string[] = [];
  mock({}, sent, { pending: [{ id: "ch-1", summary: "Add gold_ev_monthly_by_currency", status: "pending", tables: [], by: "Priya", at: "2026-10-09T01:00:00+00:00" }] });
  wrap("/centre/build/p/EV-0003");
  expect(await screen.findByText(/Add gold_ev_monthly_by_currency/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Accept" }));
  await waitFor(() => expect(sent.some((s) => s.includes("/plan/changes/ch-1/accept"))).toBe(true));
  await userEvent.click(screen.getByRole("button", { name: "Not this" }));
  await waitFor(() => expect(sent.some((s) => s.includes("/plan/changes/ch-1/reject"))).toBe(true));
});

test("NU-23: Go live stays disabled after a failed run of this plan and says why; a later clean run opens it again", async () => {
  const { Pipeline } = await import("./Steps");
  const plan: Plan = { ...PLAN, state: "approved", can: { run_sandbox: true, go_live: true, schedule: true } };
  const run = (status: string, at: string, failed = false) => ({ run_id: at, plan_version: 1, started: at, finished: at, status, mode: "sandbox",
    steps: [{ table: "gold_ev_holdings_monthly", rows: 0, ms: 1, status: failed ? "failed" : "ok" }] });
  const view = (runs: ReturnType<typeof run>[]) => render(<MemoryRouter><Pipeline plan={plan} runs={runs} busy={false} pid="EV-0003" onRun={() => undefined} onSchedule={() => undefined} /></MemoryRouter>);
  const a = view([run("failed", "2026-10-10T02:00:00Z", true), run("ok", "2026-10-09T02:00:00Z")]);
  expect(screen.getByRole("button", { name: "Go live" })).toBeDisabled();
  expect(screen.getByRole("status")).toHaveTextContent("failed at gold_ev_holdings_monthly");
  a.unmount();
  view([run("ok", "2026-10-10T03:00:00Z"), run("failed", "2026-10-10T02:00:00Z", true)]);
  expect(screen.getByRole("button", { name: "Go live" })).toBeEnabled();
});

test("UC10A-005: a choice not yet saved survives the plan being fetched again while a run is polled", async () => {
  const { Pipeline } = await import("./Steps");
  const plan: Plan = { ...PLAN, state: "live", can: { run_sandbox: true, go_live: true, schedule: true } };
  const saved: unknown[] = [];
  const el = (p: Plan) => <MemoryRouter><Pipeline plan={p} runs={[]} busy={false} pid="EV-0003" onRun={() => undefined} onSchedule={(x) => saved.push(x)} /></MemoryRouter>;
  const v = render(el(plan));
  await userEvent.selectOptions(screen.getByLabelText("Repeat"), "monthly");
  v.rerender(el({ ...plan, schedule: { ...plan.schedule } }));  // same values, a new object: the poll's refetch
  expect(screen.getByLabelText("Repeat")).toHaveValue("monthly");
  await userEvent.click(screen.getByRole("button", { name: "Save the schedule" }));
  expect(saved).toEqual([{ ...plan.schedule, freq: "monthly" }]);
});

test("OB-9: Span's chat bubbles on Build cards carry no legacy ground band", async () => {
  const { readFileSync } = await import("node:fs"); // vitest turns ?raw CSS imports into empty strings (see look.test.tsx)
  const css = readFileSync(`${process.cwd().replace(/\\/g, "/")}/src/styles/shell.css`, "utf-8");
  const rule = css.slice(css.indexOf(".wb-log .n-message .bubble"));
  expect(rule).toMatch(/^\.wb-log \.n-message \.bubble[^{]*\{ background: transparent;/);
});
