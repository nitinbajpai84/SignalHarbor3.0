import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import { routes } from "./routes";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

const card = { id: "p1", key: "k", kind: "exception", role: "cio", headline: "Valuation revised: Evergreen Growth I", text: "x", status_word: "Revised · manager final",
  urgency: "needs_me", action: "Open case", as_of: "2026-09-30", received: "2026-10-09T00:00:00+00:00", effect: "USD 180,000", link: "/centre/desk/e1", exception_id: "e1" };
const kase = { id: "e1", number: "CASE-0001", title: "Investigate the difference", materiality: "high", due: null, state: "assigned", amount: 180000, currency: "USD",
  maker_name: "Mei Tan", checker_name: "Raj Iyer", proposal: null, affects: [], history: [], can: {} };
const run = { recon_code: "cash_by_entity", as_of_date: "2026-09-30", ran_at: "2026-10-09T08:00:00+00:00", checked: 4, breaks: 1, opened: ["e1"], skipped: [], tolerance_rule_version_id: "rv7" };

const doc = (id: string, fund: string) => ({ id, title: `${fund} statement`, instrument_name: fund, valuation_date: "2026-09-30", received_at: "2026-10-09", label: "Current" });
let DOCS: ReturnType<typeof doc>[] = [];
beforeEach(() => { DOCS = []; });

function mock(roles: string[], sent: string[]) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Mei", company_id: "evergreen", roles });
    if (init?.method && init.method !== "GET") { sent.push(`${init.method} ${url} ${String(init.body ?? "")}`); return json(200, { ...run, breaks: 0, opened: [] }); }
    if (url.startsWith("/api/v1/pulse2/items")) return json(200, { role: "cio", roles: ["cio"], items: [card] });
    if (url === "/api/v1/action/landing") return json(200, { viewer: "Mei Chen", counts: {}, assigned_to_me: [], assigned_by_me: [], waiting_approval: [] });
    if (url === "/api/v1/cases") return json(200, { cases: [kase] });
    if (url === "/api/v1/cases/e1") return json(200, kase);
    if (url === "/api/v1/documents" || url.startsWith("/api/v1/evidence")) return json(200, { documents: DOCS });
    if (url === "/api/v1/recon/runs") return json(200, [run]);
    return json(404, { error: "not_found", message: "Not found." });
  }));
}
const Where = () => <p data-testid="where">{useLocation().pathname}</p>;
function open(at: string) {
  render(<MemoryRouter initialEntries={[at]}><ThemeProvider><SessionProvider><Routes>
    {routes.map((r) => <Route key={r.path} path={`/centre/${r.path}`} element={r.element} />)}</Routes><Where /></SessionProvider></ThemeProvider></MemoryRouter>);
}

test("ACT1: Action is one page with the groups, count chips and no tabs; the case Tally opened is a line with one primary button", async () => {
  mock(["sponsor"], []);
  open("/centre/action");
  expect(await screen.findByRole("heading", { name: /Good (morning|afternoon|evening), Mei\. 1 thing needs you today\./ })).toBeInTheDocument();
  expect(screen.queryByRole("navigation", { name: "Action tabs" })).toBeNull();
  const chips = within(screen.getByRole("navigation", { name: "Jump to a group" })).getAllByRole("link").map((x) => x.getAttribute("href"));
  expect(chips).toEqual(["#cases", "#recon", "#chase", "#confirm", "#approve"]);
  // the cash break is a Reconciliations line; its case is not repeated under Cases
  const recon = screen.getByRole("region", { name: /Reconciliations to clear/ });
  expect(await within(recon).findByRole("link", { name: "Open the case" })).toHaveAttribute("href", "/centre/action/cases/e1");
  expect(within(screen.getByRole("region", { name: /Cases to handle/ })).getByText("Nothing to clear.")).toBeInTheDocument();
  expect(screen.getByText("Done today · 0")).toBeInTheDocument();
});

test("a case link stays inside the Action centre and the case page carries the evidence region", async () => {
  mock(["decision_maker"], []);
  open("/centre/action/cases");
  await userEvent.click(await screen.findByRole("link", { name: "CASE-0001" }));
  await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("/centre/action/cases/e1"));
  expect(await screen.findByRole("region", { name: "Evidence" })).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "Where is this from?" }).length).toBeGreaterThan(0);
});

test("ROLE1: Action for the business owner has no reconciliations or figures to confirm, and does not ask for them", async () => {
  mock(["owner"], []);
  open("/centre/action");
  await screen.findByRole("heading", { name: /Good (morning|afternoon|evening), Mei\./ });
  const chips = within(screen.getByRole("navigation", { name: "Jump to a group" })).getAllByRole("link").map((x) => x.getAttribute("href"));
  expect(chips).toEqual(["#cases", "#chase", "#approve"]);
  expect(screen.queryByRole("region", { name: /Reconciliations to clear/ })).toBeNull();
  expect((vi.mocked(fetch).mock.calls as unknown[][]).map((c) => String(c[0]))).not.toContain("/api/v1/recon/runs");
});

test("Reconciliations lists each check with its last run; Run now only for permitted roles", async () => {
  const sent: string[] = [];
  mock(["analyst"], sent);
  open("/centre/action/reconciliations");
  expect(await screen.findByText("Cash by entity")).toBeInTheDocument();
  expect(screen.getByText("1 difference to look at")).toBeInTheDocument();
  expect(screen.getByText(/Allowance: not stated/)).toBeInTheDocument();
  expect(screen.getByText("NAV against investments")).toBeInTheDocument();
  await userEvent.click(screen.getAllByRole("button", { name: "Run now" })[0]!);
  await waitFor(() => expect(sent[0]).toMatch(/^POST \/api\/v1\/recon\/cash_by_entity\/run .*as_of_date/));
});

test("a person without a run permission sees no Run now", async () => {
  mock(["decision_maker"], []);
  open("/centre/action/reconciliations");
  expect(await screen.findByText("Cash by entity")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Run now" })).toBeNull();
});

test("a case that names no fund shows no statements", async () => {
  mock(["decision_maker"], []);
  DOCS = [doc("d1", "Evergreen Growth I")];
  open("/centre/action/cases/e1");
  expect(await screen.findByText("No statements are linked to this case.")).toBeInTheDocument();
});

test("the case page lists only the statements of the fund the case is about", async () => {
  mock(["decision_maker"], []);
  DOCS = [doc("d1", "Evergreen Growth I"), doc("d2", "Other Fund II")];
  const base = globalThis.fetch;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => url === "/api/v1/cases/e1" ? json(200, { ...kase, title: "Revision on Evergreen Growth I" }) : base(url, init)));
  open("/centre/action/cases/e1");
  expect(await screen.findByRole("link", { name: "Evergreen Growth I statement" })).toHaveAttribute("href", "/centre/action/evidence/d1");
  expect(screen.queryByRole("link", { name: "Other Fund II statement" })).toBeNull();
});

test("ACT1: the old tab routes still open as deep links, with a way back to today; evidence still opens", async () => {
  mock(["decision_maker"], []);
  open("/centre/action/cases");
  expect(await screen.findByRole("link", { name: "CASE-0001" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Back to today" })).toHaveAttribute("href", "/centre/action");
  expect(screen.queryByRole("navigation", { name: "Action tabs" })).toBeNull();
  for (const gone of ["Projects today", "Evidence", "Office view and CIO Brief"]) expect(screen.queryByRole("link", { name: gone })).toBeNull();
});

test("NU-21: a dashboard shared with the person this fortnight shows under Since yesterday, linked into Consume", async () => {
  mock(["participant"], []);
  const fetch0 = globalThis.fetch;
  const recent = new Date(Date.now() - 864e5).toISOString(), old = "2025-01-01T00:00:00+00:00";
  const row = (id: string, title: string, at: string) => ({ id, title, project_title: "Monthly investment report", shared_by: "Daniel Foo", shared_at: at, tiles: 3, link: `/centre/consume/d/${id}` });
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => url === "/api/v1/consume/shared"
    ? json(200, { dashboards: [row("dash-1", "Holdings by entity", recent), row("dash-0", "Last year's pack", old)], brief: null }) : fetch0(url, init)));
  open("/centre/action");
  const box = await screen.findByRole("region", { name: "Since yesterday" });
  expect(within(box).getByRole("link", { name: "Holdings by entity" })).toHaveAttribute("href", "/centre/consume/d/dash-1");
  expect(box).toHaveTextContent("shared by Daniel Foo");
  expect(within(box).queryByText("Last year's pack")).toBeNull();
});

test("NU-21: nothing shared, Since yesterday says so", async () => {
  mock(["participant"], []);
  open("/centre/action");
  expect(await within(await screen.findByRole("region", { name: "Since yesterday" })).findByText("Nothing new since yesterday.")).toBeInTheDocument();
});
