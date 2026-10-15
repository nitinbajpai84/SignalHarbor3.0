import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import { routes } from "./routes";

// ACT1: each group of the one-page Action centre is built from the existing calls, and the primary button does the existing real action.
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

const today = new Date().toISOString();
const k = (id: string, over: object = {}) => ({ id, number: `CASE-${id}`, title: `Case ${id}`, materiality: "high", due: null, state: "new", amount: 5, currency: "USD", exception_type: "limit_breach", ...over });
const run = { recon_code: "cash_by_entity", as_of_date: "2026-09-30", ran_at: today, checked: 4, breaks: 1, opened: ["b1"], skipped: [], rule_words: [],
  results: [{ words: "Entity B cash differs by 12,400", breached: true, case_id: "b1", cause: "A timing difference that clears today." }] };
const fund = { fund_id: "f1", fund_name: "Fund One", manager: "Mgr", currency: "USD", cadence: "monthly", period_end: "2026-06-30", due: "2026-07-14", state: "late", state_word: "Late",
  received_on: null, days_late: 63, revised_count: 0, revisions_total: 0, last_value: null, statements: [] };
const inbox = { as_of: "2026-10-12", due_rule_signed: true, rule_note: null, can_draft: true, managers: [
  { manager_id: "m1", name: "Manager One", funds: [fund], counts: { expected: 1, received: 0, late: 1, revised: 0 } },
  { manager_id: "m2", name: "Manager Two", funds: [], counts: { expected: 0, received: 0, late: 0, revised: 0 } }] };
const ext = { doc_id: "d1", file: "inbox/kestrel.pdf", intent_id: "i1", type: "t", type_name: "Manager statement", version: 1, values: { NAV: { value: "7,320,000", raw: "", line: 1, by: "rules" } },
  checks: [{ kind: "parses", field: "date", detail: "", ok: false, why: "The date line does not parse." }], status: "review", lines: [] };

function mock(sent: string[], over: { cases?: object[]; inbox?: object; queue?: object[]; runs?: object[] } = {}) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Mei Chen", company_id: "x", roles: ["analyst"] });
    if (init?.method && init.method !== "GET") { sent.push(`${init.method} ${url} ${String(init.body ?? "")}`); return json(200, url.includes("followup") ? { manager: "Manager One", draft: "Dear team", sent: false, note: "Not sent." } : {}); }
    if (url === "/api/v1/action/landing") return json(200, { viewer: "Mei Chen", counts: {}, assigned_to_me: [], assigned_by_me: [], waiting_approval: [
      { kind: "dashboard", title: "Dashboard: Scorecard", project: "P1", from: "Leo Park", since: "2026-10-11", link: "/centre/build/p/p1/dashboards" }] });
    if (url === "/api/v1/cases") return json(200, { cases: over.cases ?? [k("a1"), k("old", { state: "resolved", closed_today: true }), k("older", { state: "resolved", closed_today: false })] });
    if (url === "/api/v1/cases/b1") return json(200, { ...k("b1"), can: { dismiss: true }, maker_name: null, checker_name: null, proposal: null, affects: [], history: [] });
    if (url === "/api/v1/recon/runs") return json(200, over.runs ?? [run]);
    if (url.startsWith("/api/v1/managers/inbox")) return json(200, over.inbox ?? inbox);
    if (url === "/api/v1/extract/queue") return json(200, { count: 1, line: "", items: over.queue ?? [{ doc_id: "d1", file: "inbox/kestrel.pdf", type: "t", intent_id: "i1", failed: [] }] });
    if (url === "/api/v1/extract/d1") return json(200, ext);
    if (url.startsWith("/api/v1/tickets")) return json(200, { tickets: [{ id: "T-1", title: "Footer total missing", assigned_name: "Data team", state: "open" }], stages: {} });
    if (url.startsWith("/api/v1/pulse2/items")) return json(200, { role: "analyst", roles: ["analyst"], items: [] });
    if (url === "/api/v1/consume/shared") return json(200, { dashboards: [], brief: null });
    return json(404, { error: "not_found", message: "Not found." });
  }));
}
function open() {
  render(<MemoryRouter initialEntries={["/centre/action"]}><ThemeProvider><SessionProvider><Routes>
    {routes.map((r) => <Route key={r.path} path={`/centre/${r.path}`} element={r.element} />)}</Routes></SessionProvider></ThemeProvider></MemoryRouter>);
}

test("every group lists its lines, counts add up, and Done today holds what was closed today", async () => {
  mock([]);
  open();
  expect(await screen.findByRole("heading", { name: /5 things need you today\./ })).toBeInTheDocument();   // case, break, late statement, figure, approval
  expect(await within(screen.getByRole("region", { name: /Cases to handle/ })).findByText("Case a1")).toBeInTheDocument();
  expect(await within(screen.getByRole("region", { name: /Statements to chase/ })).findByText(/Manager One · 63 business days late/i)).toBeInTheDocument();
  expect(await screen.findByText(/Only late ones\. 1 of 2 managers are on time/)).toBeInTheDocument();
  expect(within(screen.getByRole("region", { name: /Waiting for my approval/ })).getByRole("link", { name: "Review and approve" })).toHaveAttribute("href", "/centre/build/p/p1/dashboards");
  expect(await within(screen.getByRole("region", { name: "My tickets" })).findByText(/Footer total missing/)).toBeInTheDocument();
  expect(await screen.findByText("Done today · 1")).toBeInTheDocument();
});

test("the primary buttons perform the existing actions: take a case, close a break as timing, draft a follow-up, confirm a figure", async () => {
  const sent: string[] = [];
  mock(sent);
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Take the case" }));
  await waitFor(() => expect(sent).toContain("POST /api/v1/cases/a1/take {}"));
  await userEvent.click(await screen.findByRole("button", { name: "Close as timing" }));
  await waitFor(() => expect(sent.some((s) => s.startsWith("POST /api/v1/cases/b1/dismiss") && s.includes("timing"))).toBe(true));
  await userEvent.click(screen.getByRole("button", { name: "Draft a follow-up" }));
  expect(await screen.findByDisplayValue("Dear team")).toBeInTheDocument();
  expect(sent).toContain('POST /api/v1/managers/m1/followup {"fund_id":"f1"}');
  await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
  await waitFor(() => expect(sent).toContain('POST /api/v1/extract/d1/accept {"values":{}}'));
});

test("a group with nothing shows one quiet line, not an empty box", async () => {
  mock([], { cases: [], runs: [], queue: [], inbox: { ...inbox, managers: [] } });
  open();
  expect(await screen.findByRole("heading", { name: /1 thing needs you today\./ })).toBeInTheDocument();
  for (const g of [/Cases to handle/, /Reconciliations to clear/, /Statements to chase/, /Figures to confirm/]) expect(within(screen.getByRole("region", { name: g })).getByText("Nothing to clear.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Confirm" })).toBeNull();
});

test("a break whose cause is not timing opens the case instead of offering Close as timing", async () => {
  mock([], { runs: [{ ...run, results: [{ ...run.results[0], cause: "Tally cannot explain it from the files.", words: "Quantity differs by 1,800" }] }] });
  open();
  const recon = await screen.findByRole("region", { name: /Reconciliations to clear/ });
  expect(await within(recon).findByRole("link", { name: "Open the case" })).toHaveAttribute("href", "/centre/action/cases/b1");
  expect(within(recon).queryByRole("button", { name: "Close as timing" })).toBeNull();
});
