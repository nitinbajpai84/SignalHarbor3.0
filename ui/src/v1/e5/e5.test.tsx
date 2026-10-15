import type { ReactElement } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import BriefPage from "./BriefPage";
import TodayPage from "./TodayPage";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

// REAL response shapes: E5a items() via /pulse2/items and E5b brief()/explain() (see tests/v1/test_e5a.py, test_e5b.py).
const card = { id: "p1", key: "exc:e1:cio", kind: "exception", role: "cio", headline: "Manager-reported valuation revised: Evergreen Growth I, 180,000.00 USD",
  text: "x", status_word: "Revised · manager final", urgency: "needs_me", action_type: "open_case", action: "Open case", as_of: "2026-09-30",
  received: "2026-10-09T00:00:00+00:00", effect: "USD 180,000", owner: null, due: null, link: "/centre/desk/e1", exception_id: "e1", rank: 1,
  generated_at: "2026-10-09T08:00:00+00:00", delivery_status: "pending", acknowledged_at: null, outcome: null };
const other = { ...card, id: "p2", headline: "Statement due", urgency: "worth_a_look", kind: "statement", exception_id: null, link: null };
const brief = { report_version_id: "rv1", report_name: "September investment report", period_end: "2026-09-30", issued_at: "2026-10-03T18:30:00+08:00",
  cutoff_at: "2026-10-03T18:00:00+08:00", version_status: "issued", currency: "USD", currencies: ["USD", "SGD"], currency_message: null,
  banner: "1 line below shows a manager-reported valuation that is revised. Open case: CASE-0001 (x).",
  lines: [{ line_key: "holding_value|p|i1", label: "Evergreen Growth I", issued: "10000000", known_now: "10180000", difference: "180000", currency: "USD", status: "revised", instrument_id: "i1", case_id: "e1" },
    { line_key: "holding_value|p|i2", label: "Evergreen Growth II", issued: "6400000.00", known_now: "6400000.00", difference: "0", currency: "USD", status: "official", instrument_id: "i2", case_id: null }],
  open_cases: [{ id: "e1", number: "CASE-0001" }], partial: false };
const explained = { refused: false, answer: "The manager-reported valuation of Evergreen Growth I changed by 180,000.00 USD.",
  evidence: [{ label: "manager estimate", value: "10000000", currency: "USD", as_of: "2026-09-30", source: "Fund A statement, page 2, line 14", state: "superseded" }],
  sources: [{ document_id: "d2", title: "Fund A amended statement", document_status: "final", page: 2, line: 14 }],
  caveats: [], next_action: "Review the case.", approver: "Raj" };

function mock(sent: string[]) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Chen", company_id: "evergreen", roles: ["decision_maker"] });
    if (init?.method && init.method !== "GET") sent.push(`${init.method} ${url} ${String(init.body ?? "")}`);
    if (url.includes("/dismiss") || url.includes("/take")) return json(200, {});
    if (url.startsWith("/api/v1/pulse2/items")) return json(200, { role: "cio", roles: ["cio", "operations"], items: [card, other] });
    if (url.endsWith("/explain")) return json(200, explained);
    if (url.startsWith("/api/v1/comments?")) { asks.push(url); return json(200, { kind: "brief_line", id: "company/x", count: 3, comments: [] }); }
    if (url.startsWith("/api/v1/brief/rv1")) return json(200, brief);
    return json(404, { error: "not_found", message: "Not found." });
  }));
}
const asks: string[] = [];
const wrap = (el: ReactElement, path: string, at: string) => render(<MemoryRouter initialEntries={[at]}><ThemeProvider><SessionProvider>
  <Routes><Route path={path} element={el} /></Routes></SessionProvider></ThemeProvider></MemoryRouter>);

test("Pulse shows Needs me first, switches to Worth a look, and dismisses only with a reason", async () => {
  const sent: string[] = [];
  mock(sent);
  wrap(<TodayPage />, "/centre/today", "/centre/today");
  expect(await screen.findByText(/Manager-reported valuation revised/)).toBeInTheDocument();
  expect(screen.queryByText(/Viewing as/)).toBeNull(); // ROLE1: the seat switch is gone
  expect(screen.getByText("Revised · manager final")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open case" })).toHaveAttribute("href", "/centre/desk/e1");
  expect(screen.getByText(/a change of USD 180,000 in the manager-reported valuation/)).toBeInTheDocument();
  expect(screen.queryByText("Statement due")).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Not for me" }));
  expect(screen.getByRole("button", { name: "Dismiss with reason" })).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Reason for dismissing"), "already handled");
  await userEvent.click(screen.getByRole("button", { name: "Dismiss with reason" }));
  expect(sent[0]).toMatch(/^POST \/api\/v1\/pulse2\/items\/p1\/dismiss .*already handled/);
  await userEvent.click(screen.getByRole("button", { name: "Worth a look" }));
  expect(await screen.findByText("Statement due")).toBeInTheDocument();
});

test("Brief shows the banner and the table, and Why did this move? shows sources as chips", async () => {
  mock([]);
  wrap(<BriefPage />, "/centre/brief/:reportVersionId", "/centre/brief/rv1");
  expect(await screen.findByText(/manager-reported valuation that is revised/)).toBeInTheDocument();
  expect(screen.getByText("USD 10,180,000")).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "Why did this move?" })).toHaveLength(1);
  await userEvent.click(screen.getByRole("button", { name: "Why did this move?" }));
  expect(await screen.findByText(/changed by 180,000.00 USD/)).toBeInTheDocument();
  expect(screen.getByText("Fund A amended statement, page 2")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "SGD" }));
  const asked = (fetch as unknown as { mock: { calls: string[][] } }).mock.calls.map((c) => c[0]);
  expect(asked.some((u) => u?.includes("currency=SGD"))).toBe(true);
});

test("Brief hides the currency switch and says why when there is no signed exchange rate", async () => {
  mock([]);
  const base = fetch as unknown as (u: string, i?: RequestInit) => Promise<Response>;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => url.startsWith("/api/v1/brief/rv1") && !url.endsWith("/explain")
    ? json(200, { ...brief, currencies: ["USD"], currency_message: "No signed exchange rate for USD to SGD is available yet, so figures are shown in USD only." })
    : base(url, init)));
  wrap(<BriefPage />, "/centre/brief/:reportVersionId", "/centre/brief/rv1");
  expect(await screen.findByText(/No signed exchange rate/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "SGD" })).toBeNull();
});

test("Brief: one banner with no Draft word on an issued report, and the issue time and data cutoff (a1.6, a1.7)", async () => {
  mock([]);
  wrap(<BriefPage />, "/centre/brief/:reportVersionId", "/centre/brief/rv1");
  expect(await screen.findByText(/manager-reported valuation that is revised/)).toBeInTheDocument();
  expect(screen.queryByText(/Draft/)).toBeNull();
  expect(screen.getByText("Issued 3 Oct 2026, 18:30 (UTC+08:00) · Data cutoff 3 Oct 2026, 18:00 (UTC+08:00)")).toBeInTheDocument();
});

test("CL1: each Brief line carries a collapsed comment thread with its count", async () => {
  asks.length = 0; mock([]);
  wrap(<BriefPage />, "/centre/brief/:reportVersionId", "/centre/brief/rv1");
  expect((await screen.findAllByRole("button", { name: "3 comments" })).length).toBeGreaterThan(0);
  expect(screen.queryByText("No comments yet.")).toBeNull();
  expect(asks.every((u) => u.includes("kind=brief_line") && u.includes("id=company%2F"))).toBe(true);  // no portfolio on the line yet: company-wide key
});
