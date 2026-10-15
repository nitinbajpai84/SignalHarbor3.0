import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { routes as cxui } from "../cxui/routes";
import { routes as k11 } from "../k11/routes";
import DeliveriesSection from "./DeliveriesSection";
import fixture from "./k10.fixture.json";
import { routes } from "./routes";

// The fixture is the real response of sh_platform/v1/k10_routes.py for the Evergreen story on 9 Oct 2026 (synthetic data, figures as in docs/test/10UC-ANSWER-KEY.md).
const F = fixture as Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

interface Opts { shared?: unknown; fail?: string; library?: unknown; projects?: unknown; sections?: unknown; signals?: unknown }
function mock(seen: string[] = [], o: Opts = {}) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    seen.push(url);
    const u = new URL(url, "http://x"), q = u.searchParams;
    if (o.fail && url.includes(o.fail)) return json(500, { message: "The service is busy. Please try again." });
    if (u.pathname === "/api/v1/consume/today") return json(200, F.today[q.get("currency") ?? "USD"]);
    if (u.pathname === "/api/v1/consume/health") return json(200, F.health[q.get("currency") ?? "USD"]);
    if (u.pathname === "/api/v1/consume/note") return json(200, F.note[q.get("currency") ?? "USD"]);
    if (u.pathname === "/api/v1/consume/signals") return json(200, o.signals ?? F.signals[q.get("period") ?? "month"]);
    if (u.pathname === "/api/v1/consume/league") return json(200, F.league[q.get("rank") ?? "alpha"]);
    if (u.pathname === "/api/v1/consume/reports") return json(200, o.library ?? F.library);
    if (u.pathname === "/api/v1/consume/email-note") return json(200, F.email);
    if (u.pathname === "/api/v1/consume/index-map") return json(200, { signed: false, signed_by: null, signed_at: null, version: 0, can_sign: false, funds: [], choices: [] });
    if (u.pathname === "/api/v1/consume/delivery-lines") return o.sections ? json(200, { lines: o.sections }) : json(404, { message: "no" });
    if (u.pathname === "/api/v1/consume/shared") return json(200, o.shared ?? { dashboards: [{ id: "dash-5a5a5a5a", title: "Board pack", project_title: "Monthly investment report", shared_by: "Nitin", shared_at: "2026-10-09T22:36:10+00:00", project_id: "EV-0003", tiles: 2, link: "/centre/consume/d/dash-5a5a5a5a" }],
      brief: { report_version_id: "rv-1", title: "Monthly report", link: "/centre/consume/brief/rv-1" } });
    if (u.pathname === "/api/v1/projects") return json(200, o.projects ?? { projects: [{ id: "EV-0003", title: "Monthly investment report", stage: "live", department: "Finance" }] });
    if (u.pathname === "/api/v1/comments") return json(200, { kind: "dashboard", id: "x", count: 3, comments: [] });
    return json(404, { message: "no" });
  }));
  return seen;
}
const all = [...cxui, ...routes, ...k11, { path: "operations", element: <Where /> }];
function Where() { const l = useLocation(); return <p>Operations at {l.pathname}{l.hash}</p>; }
const at = (path: string) => render(
  <ThemeProvider><MemoryRouter initialEntries={[path]}><Routes>{all.map((r) => <Route key={r.path} path={`/centre/${r.path}`} element={r.element} />)}</Routes></MemoryRouter></ThemeProvider>,
);
beforeEach(() => { localStorage.clear(); sessionStorage.clear(); });

// ---- Today --------------------------------------------------------------------------------------------------------------------

test("Today: one sentence, four key numbers, and a figure that is not computable says so instead of a number", async () => {
  mock(); at("/centre/consume");
  expect(await screen.findByRole("heading", { name: /The office is worth USD 103\.41 million\. The liquid book rose 1\.65 million in September and beat its benchmark by 1\.46 points\./ })).toBeInTheDocument();
  expect(screen.getByText(/MORNING NOTE · FRIDAY 9 OCTOBER/)).toBeInTheDocument();
  expect(within(screen.getByRole("article", { name: "Net asset value, today" })).getByText("103.41M")).toBeInTheDocument();
  const day = screen.getByRole("article", { name: "P&L, yesterday" });
  expect(within(day).getByText("Not available yet")).toBeInTheDocument();
  expect(within(day).getByText("Waits for the daily price file.")).toBeInTheDocument();
  expect(within(screen.getByRole("article", { name: "P&L, September" })).getByText("+1,648,000")).toBeInTheDocument();
  expect(within(screen.getByRole("article", { name: "Against the benchmark" })).getByText("+1.46 pts")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Net asset value, today: Where is this from?" }));
  expect(screen.getByText(/Latest value of every holding/)).toBeInTheDocument();
});

test("Today: what moved, the markets in one line with its source, and nothing Action or Reports already has", async () => {
  mock(); at("/centre/consume");
  const moved = await screen.findByRole("region", { name: "What moved" });
  expect(within(moved).getByText("Largest contributor: Northwind Logistics")).toBeInTheDocument();
  expect(within(moved).getByText("+132,000")).toBeInTheDocument();
  expect(within(moved).getByText("Saltmarsh Infrastructure Fund II")).toBeInTheDocument();
  expect(within(moved).getByRole("link", { name: "See every portfolio and fund" })).toHaveAttribute("href", "/centre/consume/health");
  const mk = screen.getByRole("region", { name: "Markets in one line" });
  expect(within(mk).getByText(/Equity \+3\.50%/)).toBeInTheDocument();
  expect(within(mk).getAllByText(/Market data file \(demo data\)/).length).toBeGreaterThan(0);
  expect(within(mk).getAllByText("FILE").length).toBeGreaterThan(0);
  expect(within(mk).getByRole("link", { name: "Open Markets" })).toHaveAttribute("href", "/centre/consume/markets");
  expect(screen.queryByRole("region", { name: "Needs you today" })).toBeNull();
  expect(screen.queryByRole("region", { name: "Reports" })).toBeNull();
  expect(screen.getByRole("heading", { name: "Comments on today's note" })).toBeInTheDocument();
  expect(screen.getAllByRole("region", { name: "Talk to Lumen" })).toHaveLength(1);
});

test("Today carries the sections that approved Delivery channels add, and works without them", async () => {
  mock([], { sections: [{ title: "Monthly investment report", lines: ["Net worth: 54,968,000"] }] }); at("/centre/consume");
  const sec = await screen.findByRole("region", { name: "Monthly investment report" });
  expect(within(sec).getByText("Net worth: 54,968,000")).toBeInTheDocument();
});

test("the five tabs, with the current one marked, and one currency switch that asks again in SGD and is kept between pages", async () => {
  const seen = mock(); at("/centre/consume");
  const nav = screen.getByRole("navigation", { name: "Consume tabs" });
  expect(within(nav).getAllByRole("link").map((a) => [a.textContent, a.getAttribute("href")])).toEqual([
    ["Today", "/centre/consume"], ["Financial health", "/centre/consume/health"], ["Markets", "/centre/consume/markets"], ["Reports", "/centre/consume/reports"], ["What if", "/centre/consume/what-if"]]);
  expect(within(nav).getByRole("link", { name: "Today" })).toHaveAttribute("aria-current", "page");
  await screen.findByRole("region", { name: "What moved" });
  fireEvent.click(within(screen.getByRole("group", { name: "Currency" })).getByRole("button", { name: "SGD" }));
  await waitFor(() => expect(seen.some((u) => u.includes("/consume/today?currency=SGD"))).toBe(true));
  fireEvent.click(within(nav).getByRole("link", { name: "Financial health" }));
  await waitFor(() => expect(seen.some((u) => u.includes("/consume/health?currency=SGD"))).toBe(true));
  expect(within(screen.getByRole("group", { name: "Currency" })).getByRole("button", { name: "SGD" })).toHaveAttribute("aria-pressed", "true");
});

test("Today says plainly when it cannot be loaded", async () => {
  mock([], { fail: "/consume/today" }); at("/centre/consume");
  expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong on our side. Try again in a moment.");
});

// ---- Financial health ---------------------------------------------------------------------------------------------------------

test("Financial health: each portfolio with value, P&L, return, lead over its benchmark and trust; the total and the three counts", async () => {
  mock(); at("/centre/consume/health");
  const by = await screen.findByRole("region", { name: "By portfolio" });
  const rows = within(by).getAllByRole("row").map((r) => r.textContent ?? "");
  expect(rows.some((r) => /Evergreen Liquid portfolio.*41,200,000\+1,648,0004\.17%\+1\.46Official/.test(r))).toBe(true);
  expect(rows.some((r) => /Evergreen Growth portfolio.*16,580,000.*Revised.*Evergreen Growth I/.test(r))).toBe(true);
  expect(rows.some((r) => /All 4 portfolios103,405,000\+3,547,000.*Unexplained 0/.test(r))).toBe(true);
  expect(within(by).getAllByRole("button", { name: /Where is this from\?/ })).toHaveLength(4);
  const counts = screen.getByRole("region", { name: "Funds needing attention" });
  expect(within(counts).getByText("3 of 9")).toBeInTheDocument();
  expect(within(counts).getByText("Plus 1 revised to final")).toBeInTheDocument();
  expect(within(counts).getByText(/Cedarpoint Ventures ×2/)).toBeInTheDocument();
});

test("Financial health: the same table by entity, and by fund is the fund league with its ranking switch", async () => {
  const seen = mock(); at("/centre/consume/health");
  await screen.findByRole("region", { name: "By portfolio" });
  fireEvent.click(screen.getByRole("button", { name: "By entity" }));
  const ent = screen.getByRole("region", { name: "By entity" });
  expect(within(ent).getAllByRole("row").some((r) => /Evergreen Family Trust.*63,950,000\+1,853,000/.test(r.textContent ?? ""))).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "By fund" }));
  const rows = (await screen.findAllByRole("row")).map((r) => r.textContent ?? "");
  await waitFor(() => expect(seen.some((u) => u.includes("/consume/league"))).toBe(true));
  expect(rows.length).toBeGreaterThan(5);
  fireEvent.click(await screen.findByRole("button", { name: "Value" }));
  await waitFor(() => expect(seen.some((u) => u.includes("rank=value"))).toBe(true));
  expect(await screen.findByText(/Cedarpoint Opportunities II cannot be ranked fairly/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "See the follow-up in Action" })).toHaveAttribute("href", "/centre/action/managers");
});

// ---- Markets ------------------------------------------------------------------------------------------------------------------

test("Markets: every outside line says its source, its date and whether it is a file or a live API", async () => {
  mock(); at("/centre/consume/markets");
  const mk = await screen.findByRole("region", { name: "The market" });
  const rows = within(mk).getAllByRole("row").map((r) => r.textContent ?? "");
  expect(rows.some((r) => /Global equity index.*1,074\.56\+3\.50%FILE Market data file \(demo data\) · 30 Sep 2026/.test(r))).toBe(true);
  expect(rows.some((r) => /US dollar in Singapore dollars.*1\.3388\+1\.12%FILE Market data file \(demo data\) · 8 Oct 2026/.test(r))).toBe(true);
  expect(rows.some((r) => /Private markets proxy.*Calculated\+3\.75% Calculated from the equity index/.test(r))).toBe(true);
  expect(rows.some((r) => /Regional equity \(Asia ex-Japan\).*Not available yet.*No feed is loaded/.test(r))).toBe(true);
  expect(screen.getByText(/never the source of them/)).toBeInTheDocument();
});

test("Markets: a live API series and a live headline carry the LIVE API tag; a yield changes in points", async () => {
  const month = F.signals.month;
  const yld = { series_key: "YLD:US10Y:FRED", name: "US 10-year Treasury yield, percent", kind: "yield", outside: true, source: null, latest: { date: "2026-10-08", level: "4.10" },
    provenance: { label: "FRED (St. Louis Fed)", tag: "LIVE API", date: "2026-10-08", demo: false }, direction: null, trail_id: "k10:market:y", where: { text: "levels" },
    periods: { month: { change_abs: "0.20", change_pct: "5.00", start_level: "4.00", end_level: "4.20" }, ytd: {}, inception: {} } };
  mock([], { signals: { ...month, indexes: [...month.indexes, yld], headlines: [{ title: "Rates held", source: "Finnhub · Wire", date: "2026-10-08", tag: "LIVE API", outside: true, trail_id: "k10:headline:1" }] } });
  at("/centre/consume/markets");
  const mk = await screen.findByRole("region", { name: "The market" });
  expect(within(mk).getAllByRole("row").some((r) => /US 10-year Treasury yield.*4\.10\+0\.20 ptsLIVE API FRED \(St\. Louis Fed\) · 8 Oct 2026/.test(r.textContent ?? ""))).toBe(true);
  const watch = screen.getByRole("region", { name: "To watch" });
  expect(within(watch).getByText("Rates held")).toBeInTheDocument();
  expect(within(watch).getByText(/FINNHUB · WIRE · 8 OCT 2026/)).toBeInTheDocument();
  expect(within(watch).getAllByText("LIVE API")).toHaveLength(1);
});

test("Markets: ours against it, the short read, manager letters with source and date, and the period switch", async () => {
  const seen = mock(); at("/centre/consume/markets");
  const pf = await screen.findByRole("region", { name: "Our portfolios against their benchmarks" });
  const rows = within(pf).getAllByRole("row").map((r) => r.textContent ?? "");
  expect(rows.some((r) => /Evergreen Liquid portfolio.*Office blend4\.17%2\.71%\+1\.46/.test(r))).toBe(true);
  expect(rows.some((r) => /Evergreen Liquid portfolio.*60\/40 equity and bond4\.17%2\.26%\+1\.91/.test(r))).toBe(true);
  expect(within(pf).getByText(/version 2 is still being agreed, so it is not used here/)).toBeInTheDocument();
  expect(within(pf).getByText(/returned 4\.17% while global equity index rose 3\.50%/)).toBeInTheDocument();
  const watch = screen.getByRole("region", { name: "To watch" });
  expect(within(watch).getByText(/MANAGER NEWSLETTER · KESTREL RIDGE ADVISORS · 28 SEP 2026/)).toBeInTheDocument();
  expect(within(watch).getByText(/Priya Nair is sole portfolio manager of the Macro Fund/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Offers" })).toHaveAttribute("href", "/centre/consume/offers");
  fireEvent.click(screen.getByRole("button", { name: "Year to date" }));
  await waitFor(() => expect(seen.some((u) => u.includes("period=ytd"))).toBe(true));
});

// ---- Reports (with Shared with you and the published dashboards folded in) ----------------------------------------------------

test("Reports: the signed report with its signer and a PDF, the live views, shared with you, published dashboards, and the older links", async () => {
  mock(); at("/centre/consume/reports");
  const card = await screen.findByRole("article", { name: "September investment report" });
  expect(within(card).getByText("Signed")).toBeInTheDocument();
  expect(within(card).getByText(/Version 1 · Daniel Foo/)).toBeInTheDocument();
  expect(within(card).getByRole("button", { name: "PDF" })).toBeInTheDocument();
  fireEvent.click(within(card).getByRole("button", { name: "Versions" }));
  expect(within(card).getByRole("link", { name: "Version 1" })).toBeInTheDocument();
  expect(within(screen.getByRole("article", { name: "Exposure and limits" })).getByText("2 limit cases open.")).toBeInTheDocument();
  const shared = await screen.findByRole("region", { name: "Shared with you" });
  expect(await within(shared).findByRole("link", { name: "CIO Brief" })).toHaveAttribute("href", "/centre/consume/brief/rv-1");
  expect(within(shared).getByText(/shared by Nitin, 10 Oct 2026, 2 tiles/)).toBeInTheDocument();
  const dash = screen.getByRole("region", { name: "Department and project reports" });
  expect(await within(dash).findByRole("heading", { name: "Finance" })).toBeInTheDocument();
  expect(within(dash).getByRole("link", { name: "Board pack" })).toHaveAttribute("href", "/centre/consume/d/dash-5a5a5a5a");
  expect(within(dash).getByRole("link", { name: "Shape what you see" })).toHaveAttribute("href", "/centre/consume/design");
  const hrefs = within(screen.getByRole("region", { name: "Company reports" })).getAllByRole("link").map((a) => a.getAttribute("href"));
  expect(hrefs).toEqual(["/centre/consume/office", "/centre/consume/managers", "/centre/consume/benchmark", "/centre/consume/figures", "/centre/action/evidence", "/centre/library"]);
  expect(screen.getByRole("link", { name: "See the email" })).toHaveAttribute("href", "/centre/operations#deliveries");
});

test("Reports: nothing shared and nothing published say so; a server that cannot make a PDF says so on the card", async () => {
  mock([], { library: { ...F.library, pdf_available: false }, shared: { dashboards: [], brief: null } }); at("/centre/consume/reports");
  const card = await screen.findByRole("article", { name: "September investment report" });
  expect(within(card).getByText("A PDF cannot be made on this server.")).toBeInTheDocument();
  expect(await screen.findByText("Nothing has been shared with you yet.")).toBeInTheDocument();
  expect(await screen.findByText("No dashboards have been published yet.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Awaiting signature · 0/ }));
  expect(screen.getByText("Nothing is waiting for a signature.")).toBeInTheDocument();
});

test("E5: a signed version offers PowerPoint beside the PDF, only when the server can make one", async () => {
  const lib = (on: boolean) => ({ ...F.library, pptx_available: on, reports: F.library.reports.map((r: any) => ({ ...r, pptx: r.pdf ? r.pdf.replace(/pdf$/, "pptx") : null })) }); // eslint-disable-line @typescript-eslint/no-explicit-any
  mock([], { library: lib(true) }); const { unmount } = at("/centre/consume/reports");
  expect((await screen.findAllByRole("button", { name: "PowerPoint" })).length).toBeGreaterThan(0);
  unmount();
  mock([], { library: lib(false) }); at("/centre/consume/reports");
  await screen.findAllByRole("button", { name: "PDF" });
  expect(screen.queryByRole("button", { name: "PowerPoint" })).toBeNull();
});

// ---- Old addresses, What if, Deliveries ----------------------------------------------------------------------------------------

test.each([
  ["/centre/consume/pnl", "Financial health"], ["/centre/consume/league", "Financial health"], ["/centre/consume/signals", "Markets: their trend next to ours"],
  ["/centre/consume/shared", "Reports"], ["/centre/consume/dashboards", "Reports"],
])("the old address %s lands on %s", async (from, heading) => {
  mock(); at(from);
  expect(await screen.findByRole("heading", { name: heading })).toBeInTheDocument();
});

test.each(["/centre/consume/email", "/centre/consume/slack"])("the old address %s lands on the Deliveries part of Operations", async (from) => {
  mock(); at(from);
  expect(await screen.findByText("Operations at /centre/operations#deliveries")).toBeInTheDocument();
});

test("What if is the old Attribution page, found at its new address, and the old one keeps its query", async () => {
  mock(); at("/centre/consume/analytics?portfolio=EG-LIQUID&code=EG-OFFICE-BLEND&month=2026-09");
  expect(await screen.findByRole("heading", { name: /What if/ })).toBeInTheDocument();
  expect(within(screen.getByRole("navigation", { name: "Consume tabs" })).getByRole("link", { name: "What if" })).toHaveAttribute("aria-current", "page");
});

test("Deliveries: the Morning Note by email in a sandboxed frame, then the Slack preview as Lumen posts it", async () => {
  mock();
  render(<ThemeProvider><MemoryRouter><DeliveriesSection /></MemoryRouter></ThemeProvider>);
  expect(await screen.findByText("Morning Note, 9 Oct: the office is worth USD 57.78 million")).toBeInTheDocument();
  const frame = screen.getByTitle("Morning Note email") as HTMLIFrameElement;
  expect(frame.getAttribute("sandbox")).toBe("");
  fireEvent.click(screen.getByRole("button", { name: "Slack" }));
  expect(await screen.findByRole("region", { name: "Slack preview" })).toBeInTheDocument();
  expect(screen.getByText("APP")).toBeInTheDocument();
});

import IndexMapPanel from "./IndexMapPanel";

describe("V6: the signed fund-to-index mapping", () => {
  const map = (over: Record<string, unknown> = {}) => ({
    signed: true, signed_by: "Anita Rao", signed_at: "2026-10-11T08:00:00+00:00", version: 2, can_sign: false,
    funds: [{ fund_id: "f1", fund: "Kestrel Ridge Macro Fund", series_key: "IDX:GLBD:SYN", proposed_series_key: "IDX:GLBD:SYN" }, { fund_id: "f2", fund: "Evergreen Growth I", series_key: null, proposed_series_key: "proxy" }],
    choices: [{ series_key: "IDX:GLEQ:SYN", name: "Global equity index" }, { series_key: "IDX:GLBD:SYN", name: "Global bond index" }, { series_key: "proxy", name: "Private markets proxy" }], ...over,
  });
  function world(m: unknown, sent: string[]) {
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST") { sent.push(`${url} ${String(init.body)}`); return json(200, map({ can_sign: true })); }
      if (url === "/api/v1/consume/index-map") return json(200, m);
      return json(404, { message: "no" });
    }));
    return render(<ThemeProvider><IndexMapPanel /></ThemeProvider>);
  }

  test("a reader sees who signed and the signed indexes, and has no way to sign", async () => {
    world(map(), []);
    expect(await screen.findByText(/Signed by Anita Rao on 11 Oct 2026, version 2\./)).toBeInTheDocument();
    expect(screen.getByText("Kestrel Ridge Macro Fund: Global bond index")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Sign the mapping" })).toBeNull();
  });

  test("the head of data picks an index per fund, starting from the proposal, and signs; a reader of an unsigned map is told nothing is compared", async () => {
    const sent: string[] = [];
    world(map({ can_sign: true }), sent);
    const growth = await screen.findByLabelText("Index for Evergreen Growth I");
    expect(growth).toHaveValue("proxy");   // the proposal, marked as one
    expect(screen.getByText("proposed")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Index for Kestrel Ridge Macro Fund"), { target: { value: "IDX:GLEQ:SYN" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign the mapping" }));
    await waitFor(() => expect(sent).toHaveLength(1));
    expect(JSON.parse(sent[0]!.split(" ").slice(1).join(" "))).toEqual({ rows: { f1: "IDX:GLEQ:SYN", f2: "proxy" } });
  });

  test("unsigned and not the head of data: the page says no fund is compared until it is signed", async () => {
    world(map({ signed: false, signed_by: null, signed_at: null, version: 0 }), []);
    expect(await screen.findByText(/Not signed yet\. No fund is compared with an index until the head of data signs/)).toBeInTheDocument();
  });
});
