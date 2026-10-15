import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { readFileSync } from "node:fs";
import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import { routes } from "./routes";

// Cycle 2, package P5: Action Centre UI fixes. Ticket ids are on each test.
const css = readFileSync(`${process.cwd()}/src/styles/design.css`, "utf-8");
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

const me = (roles: string[]) => json({ display_name: "Mei", company_id: "evergreen", roles });
const at = (path: string) => render(<MemoryRouter initialEntries={[path]}><ThemeProvider><SessionProvider><Routes>
  {routes.map((r) => <Route key={r.path} path={`/centre/${r.path}`} element={r.element} />)}</Routes></SessionProvider></ThemeProvider></MemoryRouter>);

const base = { as_of_date: "2026-10-08", ran_at: "2026-10-09T08:00:00+00:00", skipped: [], tolerance_rule_version_id: null };
const limits = { ...base, recon_code: "limits", checked: 4, breaks: 2, opened: [],
  rule_words: ["The Harborview Semiconductor share of the Evergreen Liquid portfolio must be at most 5%."],
  causes: [{ title: "Limit breached · Harborview Semiconductor · Evergreen Liquid portfolio · 2026-10-09", cause: "real breach" },
    { title: "Limit breached · Cedarpoint Ventures · Entity B operating portfolio · 2026-10-09", cause: "stale data" }],
  results: [
    { words: "Harborview Semiconductor, Evergreen Liquid portfolio: 2,368,000 USD = 5.75% against a maximum of 5%.", breached: true, case_id: "c8", over_by: "308000.00" },
    { words: "Within range, Evergreen Liquid portfolio: 1,000 USD = 1.00% against a maximum of 5%.", breached: false },
    { words: "Cedarpoint Ventures, Entity B operating portfolio: 12,925,000 USD = 56.50% against a maximum of 55%.", breached: true, case_id: "c7" }] };

test("UC5-C2-01, 02, 09, analyst-uc8-06: each breach line says cause and over-by and has its own trail; a signed limit is not an allowance", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => url === "/api/auth/me" ? me(["participant"]) : url === "/api/v1/recon/runs" ? json([limits]) : json({}, 404)));
  at("/centre/action/reconciliations");
  expect(await screen.findByText(/5.75% against a maximum of 5%. Outside the limit; real breach, over by 308,000\./)).toBeInTheDocument();
  expect(screen.getByText(/56.50% against a maximum of 55%. Outside the limit; stale data\./)).toBeInTheDocument();
  expect(screen.queryByText(/Limit breached · Cedarpoint Ventures .*: stale data/)).toBeNull();   // no second copy of the cause under the lines
  expect(screen.getByText(/Signed limit: The Harborview/)).toBeInTheDocument();
  expect(screen.queryByText(/Allowance: The Harborview/)).toBeNull();
  const card = screen.getByText("Limits").closest("li")!;
  expect(within(card).getAllByRole("button", { name: "Where is this from?" })).toHaveLength(2);   // one per breached line, none for the whole card
});

test("analyst-uc2-07, analyst-uc8-07: no access shows only the access sentence", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => url === "/api/auth/me" ? me(["owner"])
    : url === "/api/v1/recon/runs" ? json({ error: "not_allowed", message: "You do not have access to this. Ask your administrator." }, 403) : json({}, 404)));
  at("/centre/action/reconciliations");
  expect(await screen.findByText("You do not have access to this. Ask your administrator.")).toBeInTheDocument();
  expect(screen.queryByText("This check has not been run yet.")).toBeNull();
  expect(screen.queryByText("Limits")).toBeNull();
});

const theCase = { id: "c9", number: "CASE-0009", title: "Agree the definition of benchmark EG-OFFICE-BLEND", exception_type: "policy_question", materiality: "medium",
  due: null, state: "new", amount: null, currency: null, maker_name: null, checker_name: null, proposal: null, affects: [], history: [{ at: "2026-10-09T00:00:00+00:00", by: null, text: "Opened." }], can: {} };
const comment = { id: "k1", parent_id: null, by: "Mei Chen", at: "2026-10-10T00:06:00+00:00", text: "Who agrees this?", edited: false, edited_at: null, deleted: false,
  deleted_by: null, history: [], mentions: [], case: null, ticket: null, may: { reply: true, edit: false, delete: false, raise: false } };
const trail = { kind: "case", id: "c9", title: theCase.title, figure: null, steps: [{ key: "source", label: "Source", state: "done", what: "Benchmark rules.", who: "Mei Chen", when: "2026-10-09T23:46:00+00:00", refs: [] }] };
function caseServer() {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url === "/api/auth/me") return me(["analyst"]);
    if (url === "/api/v1/cases") return json({ cases: [theCase] });
    if (url.startsWith("/api/v1/cases/c9")) return url.endsWith("/tally?quick=1") || url.endsWith("/tally") ? json({}, 404) : json(theCase);
    if (url.startsWith("/api/v1/comments/people")) return json([{ name: "Raj Patel" }]);
    if (url.startsWith("/api/v1/comments?")) return json({ kind: "case", id: "c9", count: 1, comments: [comment] });
    if (url.startsWith("/api/v1/trail")) return json(trail);
    if (url.startsWith("/api/v1/documents")) return json({ documents: [] });
    return json({}, 404);
  }));
}

test("analyst-uc4-05, analyst-uc8-05: the cases list names the kind and its table scrolls inside its own box", async () => {
  caseServer();
  const { container } = at("/centre/action/cases");
  expect(await screen.findByText("Policy question")).toBeInTheDocument();
  expect(container.querySelector(".ds-table-wrap > table.ds-table")).not.toBeNull();
});

test("analyst-uc2-05, UC5-C2-05, UC6-05, analyst-uc8-08, UC1-C2-08, MAPA-04: the case page has its kind, a trail and comments in company time", async () => {
  caseServer();
  at("/centre/action/cases/c9");
  expect(await screen.findByText(/Policy question · Medium/)).toBeInTheDocument();
  fireEvent.click(await screen.findByRole("button", { name: "1 comment" }));
  expect(await screen.findByText("Who agrees this?")).toBeInTheDocument();
  expect(screen.getByText("10 Oct 2026, 08:06")).toBeInTheDocument();                // 00:06 UTC is 08:06 in Singapore
  fireEvent.click(screen.getByRole("button", { name: "Where is this from?" }));
  const panel = await screen.findByRole("region", { name: "Where this is from" });
  expect(await within(panel).findByText("Benchmark rules.")).toBeInTheDocument();
  expect(within(panel).getByText(/Mei Chen · 10 Oct 2026/)).toBeInTheDocument();       // not the UTC day, 9 Oct
  expect(await within(panel).findByRole("button", { name: "1 comment" })).toBeInTheDocument();   // CM1 line 6
});

test("JA-001, AUC3-03, analyst-uc2-04, UC5-C2-07, UC9-10: no empty column height; the switch keeps its small track", () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => url === "/api/auth/me" ? me(["analyst"]) : json({}, 404)));
  at("/centre/action/cases");
  const narrow = css.slice(css.indexOf("@media (max-width: 900px)"));
  expect(narrow).toMatch(/\.ds-frame__aside, \.ds-frame__main \{[^}]*flex: 0 1 auto/);
  expect(css).toMatch(/#root \[role="switch"\]\.ms-track \{ min-height: 22px/);
});
