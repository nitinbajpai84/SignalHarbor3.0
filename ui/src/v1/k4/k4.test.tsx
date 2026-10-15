import type { ReactElement } from "react";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import fixture from "./office.fixture.json";
import OfficePage from "./OfficePage";
import { routes } from "./routes";

// The fixture is the real response of sh_platform/v1/k4_routes.py for the Evergreen story (generated from tests/v1/test_k4.py's data).
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

function mock(seen: string[], over: Record<string, unknown> = {}) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    seen.push(url);
    if (url === "/api/auth/me") return json(200, { display_name: "Chen", company_id: "evergreen", roles: ["decision_maker"] });
    if (url.startsWith("/api/v1/comments?")) return json(200, { kind: "office_line", id: "x", count: 3, comments: [] });
    const part = (url.split("?")[0] ?? "").split("/").pop() ?? "";
    const key = ({ holdings: "holdings", issued: "issued", "nav-bridge": "bridge", liquidity: "liquidity", "why-moved": "why" } as Record<string, string>)[part];
    if (key && key in over) return over[key] instanceof Response ? (over[key] as Response) : json(200, over[key]);
    if (key) return json(200, (fixture as Record<string, unknown>)[key]);
    return json(404, { error: "not_found", message: "Not found." });
  }));
}
const wrap = (el: ReactElement) => render(<MemoryRouter><ThemeProvider><SessionProvider>{el}</SessionProvider></ThemeProvider></MemoryRouter>);

test("holdings show a status word and a source on every line, and answer where a figure is from", async () => {
  mock([]);
  wrap(<OfficePage />);
  const section = await screen.findByRole("region", { name: "Holdings" });
  expect(await within(section).findByText("Evergreen Holdings")).toBeInTheDocument();
  expect(within(section).getByText("Revised")).toBeInTheDocument();
  expect(within(section).getAllByText("Official").length).toBeGreaterThan(0);
  expect(within(section).getByText(/page 2, line 14/)).toBeInTheDocument();
  expect(within(section).getAllByText(/USD 57,780,000/).length).toBeGreaterThan(0);
  await userEvent.click(within(section).getByRole("button", { name: "Evergreen Growth I: Where is this from?" }));
  expect(await within(section).findByRole("link", { name: "Open the statement" })).toHaveAttribute("href", expect.stringContaining("/centre/evidence/"));
});

test("the SGD switch asks the server again in SGD", async () => {
  const seen: string[] = [];
  mock(seen);
  wrap(<OfficePage />);
  await screen.findByRole("region", { name: "Holdings" });
  await userEvent.click(screen.getByRole("button", { name: "SGD" }));
  await vi.waitFor(() => expect(seen.some((u) => u.startsWith("/api/v1/office/holdings?currency=SGD"))).toBe(true));
  expect(seen.some((u) => u.startsWith("/api/v1/office/nav-bridge?currency=SGD"))).toBe(true);
});

test("issued versus known now shows the revision and links to the CIO Brief under Consume", async () => {
  mock([]);
  wrap(<OfficePage />);
  const section = await screen.findByRole("region", { name: "Issued versus known now" });
  expect(await within(section).findByText("September investment report")).toBeInTheDocument();
  expect(within(section).getByText("Revised")).toBeInTheDocument();
  expect(within(section).getByText(/1 line below shows a manager-reported valuation/)).toBeInTheDocument();
  expect(within(section).queryByText(/Draft/)).toBeNull();
  expect(within(section).getByRole("link", { name: "Open the CIO Brief" }).getAttribute("href")).toMatch(/^\/centre\/consume\/brief\/.+/);
});

test("the NAV bridge splits the difference into four parts and shows the evidence on request", async () => {
  mock([]);
  wrap(<OfficePage />);
  const section = await screen.findByRole("region", { name: "Investment total against administrator NAV" });
  expect(await within(section).findByText(/Difference USD 180,000/)).toBeInTheDocument();
  for (const part of ["Revisions", "Timing (valuation date)", "Exchange rates", "Unexplained"]) expect(within(section).getByText(part)).toBeInTheDocument();
  await userEvent.click(within(section).getAllByRole("button", { name: "Where is this from?" })[0] as HTMLElement);
  expect(await within(section).findByText(/Fund A amended statement/)).toBeInTheDocument();
});

test("liquidity says commitments are not loaded when the server says so, and shows calls and unconfirmed flags when it can", async () => {
  mock([], { liquidity: { available: false, currency: "USD", as_of: "2026-10-09", message: "Commitments and capital calls are not loaded yet, so there is no liquidity forecast." } });
  wrap(<OfficePage />);
  const none = await screen.findByRole("region", { name: "Liquidity" });
  expect(await within(none).findByText(/not loaded yet/)).toBeInTheDocument();
});

test("liquidity with a call due: cash after the call and the not-confirmed flag", async () => {
  mock([]);
  wrap(<OfficePage />);
  const section = await screen.findByRole("region", { name: "Liquidity" });
  expect(await within(section).findByText(/Available cash USD 2,000,000/)).toBeInTheDocument();
  expect(within(section).getAllByText(/USD 1,250,000/, { selector: "td" }).length).toBeGreaterThan(0);
  expect(within(section).getByText(/Not confirmed yet:/)).toBeInTheDocument();
  expect(within(section).getByText(/Harbour Private Equity USD 750,000 due 20 Oct 2026/)).toBeInTheDocument();
});

test("an error in one section does not hide the others", async () => {
  mock([], { holdings: json(503, { error: "unavailable", message: "The figures are not ready yet, so nothing is shown." }) });
  wrap(<OfficePage />);
  expect((await screen.findAllByRole("alert")).length).toBe(1);
  expect(await screen.findByText("September investment report")).toBeInTheDocument();
});

test("routes: the Office view and the brief are reachable under Consume", () => {
  expect(routes.map((r) => r.path)).toEqual(["consume/office", "consume/brief/:reportVersionId"]);
});

test("why did this move shows start, end, change and lists the forward as a trade", async () => {
  const seen: string[] = [];
  mock(seen);
  wrap(<OfficePage />);
  const section = await screen.findByRole("region", { name: "Why did this move" });
  expect(await within(section).findByText(/Change USD 1,648,000 \(\+4.1667%\)/)).toBeInTheDocument();
  expect(within(section).getByText(/Fx forward of FX forward FXF-2026-001/)).toBeInTheDocument();
  expect(within(section).queryByText(/no trades/i)).toBeNull();
  expect(seen.some((u) => u.startsWith("/api/v1/office/why-moved?start="))).toBe(true);
});

test("an instrument with no asset class reads Needs a class", async () => {
  const h = JSON.parse(JSON.stringify(fixture.holdings));
  h.entities[0].portfolios[0].lines[0].status = "Needs a class";
  h.entities[0].portfolios[0].lines[0].asset_class = null;
  mock([], { holdings: h });
  wrap(<OfficePage />);
  const section = await screen.findByRole("region", { name: "Holdings" });
  expect(await within(section).findByText("Needs a class")).toBeInTheDocument();
  expect(within(section).getByText("Not set")).toBeInTheDocument();
});

test("why did this move: picking a portfolio and a month asks the server for that portfolio and that month", async () => {
  const seen: string[] = [];
  mock(seen);
  wrap(<OfficePage />);
  const section = await screen.findByRole("region", { name: "Why did this move" });
  const pf = fixture.holdings.entities[0]!.portfolios[0]!;
  await within(section).findByRole("option", { name: pf.portfolio_name });
  await userEvent.selectOptions(within(section).getByLabelText(/Portfolio/), pf.portfolio_id);
  const month = within(section).getByLabelText(/Month/);
  await userEvent.clear(month);
  await userEvent.type(month, "2026-09");
  expect(seen.some((u) => u.includes("start=2026-08-31&end=2026-09-30") && u.includes(`portfolio_id=${pf.portfolio_id}`) && !u.includes("book="))).toBe(true);
});

test("liquidity: shortfall in words, cash after confirmed calls only, as-of date and notices with their document (a6.7-a6.10)", async () => {
  const liq = JSON.parse(JSON.stringify(fixture.liquidity));
  const e = liq.entities[0];
  e.warnings = ["Shortfall: Entity B is short by 169,600.00 USD within 30 days if every call is paid."];
  e.unconfirmed_distributions = [{ ...e.unconfirmed[0], id: "d1", kind: "distribution", fund: "Evergreen Growth I", own_amount: "320000", due_date: "2026-11-16" }];
  e.buckets = [{ key: "overdue", label: "Past due, not marked paid", calls: "100", distributions: "0", cash_after_calls: null, cash_after_confirmed_calls: null,
    items: [{ ...e.unconfirmed[0], id: "old", fund: "Old Fund", due_date: "2025-07-31" }] },
  { key: "30", label: "Within 30 days", calls: "1050000", distributions: "0", cash_after_calls: "-169600", cash_after_confirmed_calls: "430400",
    items: [{ ...e.unconfirmed[0], id: "c1", document_id: "doc1", document_title: "Saltmarsh call notice", received_at: "2026-10-06T09:00:00+08:00", page: 1, line: 15 }] }];
  mock([], { liquidity: liq });
  wrap(<OfficePage />);
  const section = await screen.findByRole("region", { name: "Liquidity" });
  expect(await within(section).findByText(/Shortfall: Entity B is short by 169,600.00 USD/)).toBeInTheDocument();
  expect(within(section).getByText("USD 430,400", { selector: "td" })).toBeInTheDocument();
  expect(within(section).getByText("(shortfall)")).toBeInTheDocument();
  expect(within(section).getByText(/As of 9 Oct 2026/)).toBeInTheDocument();
  expect(within(section).getByText(/Distributions not confirmed yet:/)).toBeInTheDocument();
  await userEvent.click(within(section).getByRole("button", { name: "Where is this from?" }));
  expect(within(section).getByRole("link", { name: "Saltmarsh call notice" })).toHaveAttribute("href", "/centre/evidence/doc1");
  expect(within(section).getByText(/page 1, line 15/)).toBeInTheDocument();
  expect(within(section).queryByText(/Old Fund: capital call/)).toBeNull();
});

test("switching currency clears the old figures while the new ones load (a4.9)", async () => {
  let release: (r: Response) => void = () => undefined;
  const base = vi.fn(async (url: string) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Chen", company_id: "evergreen", roles: ["decision_maker"] });
    const part = (url.split("?")[0] ?? "").split("/").pop() ?? "";
    if (part === "liquidity" && url.includes("SGD")) return new Promise<Response>((r) => { release = r; });
    const key = ({ holdings: "holdings", issued: "issued", "nav-bridge": "bridge", liquidity: "liquidity", "why-moved": "why" } as Record<string, string>)[part];
    return key ? json(200, (fixture as Record<string, unknown>)[key]) : json(404, {});
  });
  vi.stubGlobal("fetch", base);
  wrap(<OfficePage />);
  const section = await screen.findByRole("region", { name: "Liquidity" });
  expect(await within(section).findByText(/Available cash USD 2,000,000/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "SGD" }));
  expect(await within(section).findByText("Loading the liquidity forecast.")).toBeInTheDocument();
  expect(within(section).queryByText(/Available cash USD/)).toBeNull();
  release(json(200, fixture.liquidity));
});

test("CL1: every holding line has a collapsed comment thread with its count", async () => {
  mock([]);
  wrap(<OfficePage />);
  const section = await screen.findByRole("region", { name: "Holdings" });
  expect((await within(section).findAllByRole("button", { name: "3 comments" })).length).toBeGreaterThan(1);
  expect(within(section).queryByText("No comments yet.")).toBeNull();
});

test("cycle 2: issue time and cutoff, the rate used, two decimals, no empty table or empty notice list", async () => {
  const f = fixture as Record<string, any>;
  const issued = { ...f.issued, lines: [], rate_note: "Converted from USD to SGD at 1.3412 (WMR_4PM fixing observed 30 Sep 2026).",
    report: { ...f.issued.report, when: "Issued 3 Oct 2026, 18:30 (UTC+08:00), data cutoff 3 Oct 2026, 18:00 (UTC+08:00)" } };
  const ent = f.liquidity.entities[0];
  const liquidity = { ...f.liquidity, entities: [{ ...ent, buckets: ent.buckets.map((b: any) => ({ ...b, items: [], calls: "2919253.4" })) }] };
  mock([], { issued, liquidity });
  wrap(<OfficePage />);
  const iss = await screen.findByRole("region", { name: "Issued versus known now" });
  expect(await within(iss).findByText(/18:30 \(UTC\+08:00\), data cutoff/)).toBeInTheDocument();                 // UC1-C2-10
  expect(within(iss).getByText(/at 1.3412/)).toBeInTheDocument();                                              // UC1-C2-07
  expect(within(iss).getByText(/not shown, because they belong to entities/)).toBeInTheDocument();             // UC1-C2-12 (e)
  const liq = await screen.findByRole("region", { name: "Liquidity" });
  expect((await within(liq).findAllByText(/2,919,253.40/)).length).toBeGreaterThan(0);                          // UC1-C2-12 (c)
  await userEvent.click(within(liq).getAllByRole("button", { name: "Where is this from?" })[0]!);
  expect(within(liq).getByText("No calls or distributions are due in the next 90 days.")).toBeInTheDocument();  // UC6-06
});
