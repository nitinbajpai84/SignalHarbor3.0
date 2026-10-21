import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { routes } from "./routes";
import Chart, { rateSpec } from "./Chart";

vi.mock("vega-embed", () => ({
  default: vi.fn(async (_el: unknown, spec: unknown) => {
    (globalThis as { __spec?: unknown }).__spec = spec;
    return { view: { finalize: () => undefined } };
  }),
}));

// C2, OP1 against C1's routes (synthetic data): picker, published tiles only (no build controls), tables drawer, share, Lumen's questions and its pointer to the studio, read-only view.
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const tile = (id: string, state: "proposed" | "accepted") => ({ id, title: `Net worth ${id}`, kpi: "net_worth", sql: "select 1", spec: { mark: "line" }, note: "", state });
const fresh = () => ({ id: "dash-0ad2b1c7", title: "September dashboard", project_id: "EV-0003", tiles: [tile("t-000001", "proposed"), tile("t-000002", "accepted")],
  audience: [] as string[], refresh: "same", audience_people: [] as { id: string; name: string; kind: string }[] });
let board = fresh();
let nothingShared = false;
const PEOPLE = [{ id: "u-fin", name: "Raj Patel", role: "Finance" }, { id: "u-cio", name: "Daniel Foo", role: "Chief Investment Officer" }];

// Response shapes are the ones cx_routes returns: summaries with a tile count, a tile from accept, {audience, refresh} from PUT, {reply, proposals} from ask.
function mock() {
  const calls: { method: string; url: string; body?: Record<string, unknown> }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method, url, body });
    if (url === "/api/v1/consume/shared") return json(200, nothingShared ? { dashboards: [], brief: null } : { dashboards: [{ id: "dash-5a5a5a5a", title: "Board pack", project_title: "Monthly investment report", shared_by: "Nitin", shared_at: "2026-10-09T22:36:10+00:00", project_id: "EV-0003", tiles: 2, link: "/centre/consume/d/dash-5a5a5a5a" }],
      brief: { report_version_id: "rv-1", title: "Monthly report", link: "/centre/consume/brief/rv-1" } });
    if (url.startsWith("/api/v1/comments?")) return json(200, { kind: "dashboard", id: "x", count: 3, comments: [] });
    if (url.startsWith("/api/v1/consume/daily")) return json(200, { not: "used" });
    if (url === "/api/v1/projects") return json(200, { projects: [{ id: "EV-0003", title: "Monthly investment report", stage: "live", department: "Finance" }] });
    if (url === "/api/v1/memory/me") return json(200, { items: [{ id: "m-1", agent: "lumen", text: "Prefers: blue for chart lines" }, { id: "m-2", agent: "north", text: "Reports to the council" }] });
    if (url.endsWith("/tables")) return json(200, { tables: [{ name: "gold_ev_holdings_monthly", columns: [{ name: "entity", type: "varchar" }], rows: 12, refreshed: "2026-10-08T09:00:00Z" }] });
    if (url.endsWith("/people")) return json(200, { people: PEOPLE });
    if (url.endsWith("/accept")) { board = { ...board, tiles: board.tiles.map((t) => (t.id === "t-000001" ? tile("t-000001", "accepted") : t)) }; return json(200, tile("t-000001", "accepted")); }
    if (url.endsWith("/audience")) {
      board = { ...board, audience: body!.audience as string[], refresh: body!.refresh as string,
        audience_people: PEOPLE.filter((p) => (body!.audience as string[]).includes(p.id)).map((p) => ({ id: p.id, name: p.name, kind: "user" })) };
      return json(200, { audience: board.audience_people, refresh: board.refresh });
    }
    if (url.endsWith("/ask") && body?.new_talk) return json(200, { reply: "A fresh talk.", proposals: [] });
    if (url.endsWith("/ask")) return /^(why|what|where)/i.test(String(body?.text))
      ? json(200, { reply: "Net worth is 54,968,000.", proposals: [] })
      : json(200, { reply: "Dashboards are built in Build › Dashboard studio. Open the studio for this project to build or change it.", proposals: [], link: "/centre/build/p/EV-0003/studio" });
    if (url.endsWith("/why")) return json(200, { answer: "Net worth is up by 2,632,000.", evidence: [{ period: "2026-08-01", value: "54,968,000" }, { split: "Evergreen Family Trust", change: "1,648,000" }], caveats: [] });
    if (url.endsWith("/data")) return json(200, { spec: { mark: "line", encoding: { x: { field: "report_month", type: "temporal" }, y: { field: "net_worth_usd", type: "quantitative" } } }, columns: ["m", "v"], rows: [{ m: "Sep", v: 1 }], capped: false, row_cap: 5000,
      data_used: { tables: ["gold_ev_holdings_monthly"], last_refresh: "2026-10-08T09:00:00Z" } });
    if (url.endsWith("/dashboards")) return json(200, { dashboards: [{ id: board.id, title: board.title, project_id: "EV-0003", refresh: "same", tiles: board.tiles.length, accepted: board.tiles.filter((t) => t.state === "accepted").length }] });
    if (url.includes("/dashboards/dash-0ad2b1c7")) return json(200, board);
    return json(404, { message: "no" });
  }));
  return calls;
}
const at = (path: string) => render(
  <ThemeProvider><MemoryRouter initialEntries={[path]}><Routes>{routes.map((r) => <Route key={r.path} path={`/centre/${r.path}`} element={r.element} />)}</Routes></MemoryRouter></ThemeProvider>,
);
beforeEach(() => { nothingShared = false; localStorage.clear(); board = fresh(); });
afterEach(() => vi.unstubAllGlobals());

// V5W-5: /centre/consume is the reading room (tests in ui/src/v1/k10/k10.test.tsx); the picker, "Shared with you" lines, link groups and
// department grouping that used to be tested here moved to its Dashboards, Shared with you, Reports and Market signals tabs.
test("V5W-5: /centre/consume is the reading room with its tabs and no list of projects", async () => {
  mock(); at("/centre/consume");
  expect(await screen.findByRole("navigation", { name: "Consume tabs" })).toBeInTheDocument();
  expect(screen.queryByText("Your projects")).toBeNull();
  expect(screen.queryByLabelText("Find a project")).toBeNull();
});

test("Lumen's chat head says what it remembers about the person, and only Lumen's lines", async () => {
  mock(); at("/centre/consume/p/EV-0003");
  expect(await screen.findByText(/Lumen remembers: blue for chart lines/)).toBeInTheDocument();
  expect(screen.queryByText(/Reports to the council/)).toBeNull();
  expect(screen.getByRole("link", { name: "Change this" })).toHaveAttribute("href", "/centre/settings/memory");
});

test("OP1: Consume shows the published tiles only, with no build controls; data used is shown", async () => {
  const calls = mock(); at("/centre/consume/p/EV-0003");
  expect(await screen.findByText("Net worth t-000002")).toBeInTheDocument();
  expect(screen.queryByText("Net worth t-000001")).toBeNull();   // a proposed tile is not shown, even if one came back
  for (const name of [/^Accept$/, /^Not this$/, /new dashboard/i, /Add a widget/, /Add a picture/, /Move (up|down)/, /Start a dashboard/, /Send for approval/]) expect(screen.queryByRole("button", { name })).toBeNull();
  expect(screen.queryByText("Proposed")).toBeNull();
  expect((await screen.findAllByText(/Last refreshed/)).length).toBeGreaterThan(0);
  expect(screen.getByRole("button", { name: "Why did this move" })).toBeInTheDocument();
  expect(calls.some((c) => c.method === "POST" && /\/(accept|reject)$/.test(c.url))).toBe(false);
  expect((globalThis as { __spec?: { data?: { values?: unknown[] } } }).__spec?.data?.values).toEqual([{ m: "Sep", v: 1 }]);
});

test("OP1: with nothing published, Consume says where dashboards are built and creates nothing", async () => {
  const calls = mock();
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ method: init?.method ?? "GET", url });
    if (url.endsWith("/tables")) return json(200, { tables: [] });
    if (url.endsWith("/dashboards")) return json(200, { dashboards: [] });
    if (url.endsWith("/people")) return json(403, { message: "no" });
    if (url === "/api/v1/memory/me") return json(200, { items: [] });
    if (url === "/api/v1/consume/chat") return json(200, { reply: "Dashboards are built in Build › Dashboard studio. Ask the project's analyst to build or change it.", link: null });
    return json(404, { message: "no" });
  }));
  at("/centre/consume/p/EV-0003");
  expect(await screen.findByText(/No dashboard has been published for this project yet/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Your message"), { target: { value: "add a bar chart of cash" } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  expect(await screen.findByText(/Ask the project's analyst/)).toBeInTheDocument();
  expect(calls.some((c) => c.method === "POST" && c.url.endsWith("/dashboards"))).toBe(false);
});

test("OP1: a question is answered, and a request to build points to the studio with a link", async () => {
  const calls = mock(); at("/centre/consume/p/EV-0003");
  await screen.findByText("Net worth t-000002");
  fireEvent.change(screen.getByLabelText("Your message"), { target: { value: "what is net worth now?" } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  expect(await screen.findByText("Net worth is 54,968,000.")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Your message"), { target: { value: "make it dots" } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  expect(await screen.findByText(/Dashboards are built in Build › Dashboard studio/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open the dashboard studio" })).toHaveAttribute("href", "/centre/build/p/EV-0003/studio");
  expect(calls.filter((c) => c.url.endsWith("/ask")).map((c) => c.body)).toEqual([{ text: "what is net worth now?" }, { text: "make it dots" }]);
});

test("tables drawer and share stay in Consume", async () => {
  const calls = mock(); at("/centre/consume/p/EV-0003");
  await screen.findByText("Net worth t-000002");
  expect(screen.getByText("gold_ev_holdings_monthly")).toBeInTheDocument();
  fireEvent.click(await screen.findByRole("checkbox", { name: /Raj Patel/ }));
  fireEvent.click(screen.getByRole("button", { name: "Share with these people" }));
  await waitFor(() => expect(calls.find((c) => c.url.endsWith("/audience"))).toMatchObject({ method: "PUT", body: { audience: ["u-fin"], refresh: "same" } }));
  expect(await screen.findByText(/Shared with: Raj Patel/)).toBeInTheDocument();
});

test("Why did this move calls the why route and shows the answer from the rows", async () => {
  const calls = mock(); at("/centre/consume/p/EV-0003");
  fireEvent.click(await screen.findByRole("button", { name: "Why did this move" }));
  expect(await screen.findByText(/Net worth is up by 2,632,000/)).toBeInTheDocument();
  expect(calls.some((c) => c.method === "GET" && c.url.endsWith("/tiles/t-000002/why"))).toBe(true);
  expect(calls.some((c) => c.url.endsWith("/ask"))).toBe(false);
});

test("the read-only view shows accepted tiles and no buttons to change them", async () => {
  mock(); at("/centre/consume/d/dash-0ad2b1c7");
  expect(await screen.findByText("Net worth t-000002")).toBeInTheDocument();
  expect(screen.queryByText("Net worth t-000001")).toBeNull();
  expect(screen.queryByRole("button", { name: "Accept" })).toBeNull();
});

test("a10.9: no ids or table names for business users, and plain axis titles", async () => {
  mock(); at("/centre/consume");
  await screen.findByRole("navigation", { name: "Consume tabs" });
  expect(screen.queryByText(/EV-0003/)).toBeNull();
  vi.unstubAllGlobals();
  board = { ...fresh(), tiles: [{ ...tile("t-000002", "accepted"), note: "From gold_ev_holdings_monthly." }] };
  mock(); at("/centre/consume/d/dash-0ad2b1c7");
  expect(await screen.findByText("The accepted tiles of this dashboard.")).toBeInTheDocument();
  expect(screen.queryByText(/EV-0003|Read only|gold_ev/)).toBeNull();
  await waitFor(() => expect((globalThis as { __spec?: { encoding?: Record<string, { title?: string }> } }).__spec?.encoding?.y?.title).toBe("Net worth USD"));
  expect((globalThis as { __spec?: { encoding?: Record<string, { title?: string }> } }).__spec?.encoding?.x?.title).toBe("Report month");
});

test("NU-18: a tile Lumen proposes as a table (usermeta.view) shows its rows and columns through TileCard, not an empty square", async () => {
  const TileCard = (await import("./TileCard")).default;
  const spec = { mark: "bar", usermeta: { view: "table" }, encoding: { x: { field: "manager_name" } } };
  const tile = { id: "t-16771c", title: "Business days late", kpi: "", sql: "select 1", spec, note: "", state: "accepted" as const };
  const data = { spec, columns: ["manager_name", "business_days_late"], rows: [{ manager_name: "Cedarpoint", business_days_late: 3 }, { manager_name: "Kestrel", business_days_late: null }],
    data_used: { tables: ["gold_x"], last_refresh: null } };
  render(<MemoryRouter><TileCard pid="p" did="d" tile={tile} load={async () => data} /></MemoryRouter>);
  const table = await screen.findByRole("table", { name: "Business days late" });
  expect(within(table).getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["Manager name", "Business days late"]);
  expect(table).toHaveTextContent("Cedarpoint3");
  expect(table).toHaveTextContent("KestrelNot available yet");
});

test("NU-22, H1-07: a reload shows the talk with Lumen, and a fresh talk empties it", async () => {
  board = { ...fresh(), talk: [{ by: "person", text: "I prefer blue lines" }, { by: "lumen", text: "Noted, blue lines." }] } as ReturnType<typeof fresh>;
  const calls = mock(); at("/centre/consume/p/EV-0003");
  expect(await screen.findByText("I prefer blue lines")).toBeInTheDocument();
  expect(screen.getByText("Noted, blue lines.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Start a fresh talk" }));
  await waitFor(() => expect(screen.queryByText("I prefer blue lines")).toBeNull());
  expect(calls.find((c) => c.url.endsWith("/dashboards/dash-0ad2b1c7/ask"))).toMatchObject({ method: "POST", body: { new_talk: true } });
});


// ---- CL1 ----
test("CL1: a dashboard on the read-only view carries comments on the whole dashboard and on each widget", async () => {
  mock(); at("/centre/consume/d/dash-0ad2b1c7");
  expect(await screen.findByRole("heading", { name: "Comments on this dashboard" })).toBeInTheDocument();
  await waitFor(() => expect(screen.getAllByRole("button", { name: "3 comments" }).length).toBe(2));  // one accepted tile + the dashboard
});

test("UC10B-004: on a slow first load the project page says it is opening, never that it has no figures", async () => {
  const calls = mock();
  let release: () => void = () => undefined;
  const slow = new Promise<void>((r) => { release = r; });
  const real = globalThis.fetch;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => { if (url.endsWith("/tables")) await slow; return real(url, init); }));
  at("/centre/consume/p/EV-0003");
  expect((await screen.findAllByText("Opening the figures.")).length).toBeGreaterThan(0);
  expect(screen.queryByText(/no figures yet|No dashboard has been published/)).toBeNull();
  release();
  expect(await screen.findByText("Net worth t-000002")).toBeInTheDocument();
  expect(screen.queryByText("Opening the figures.")).toBeNull();
  expect(calls.length).toBeGreaterThan(0);
});

test("VID4: a returns line shows 0.28 as 28% on the axis and in the tooltip; a money line is left alone", () => {
  const spec = { mark: "line", encoding: { x: { field: "month", type: "temporal" }, y: { field: "portfolio_return", type: "quantitative" } } };
  const out = rateSpec(spec, [{ month: "2026-01", portfolio_return: 0.28 }, { month: "2026-02", portfolio_return: -0.22 }]) as any;
  expect(out.encoding.y.axis.format).toBe(".2%");
  expect(out.encoding.tooltip.find((t: any) => t.field === "portfolio_return").format).toBe(".2%");
  expect(out.encoding.tooltip.find((t: any) => t.field === "month").format).toBeUndefined();
  const money = { mark: "line", encoding: { y: { field: "net_worth_sgd", type: "quantitative" } } };
  expect(rateSpec(money, [{ net_worth_sgd: 0.5 }])).toBe(money);
});

test("FIX1: every one-number tile kind shows its figure with thousands separators, not as Vega's bare number", () => {
  const used = { tables: [], last_refresh: null };
  render(<Chart label="Net worth" data={{ spec: { mark: { type: "text", fontSize: 40 }, encoding: { text: { field: "net_worth", type: "quantitative" } } }, rows: [{ net_worth: 103405000 }], data_used: used }} />);
  render(<Chart label="Holdings" data={{ spec: { mark: "text", usermeta: { view: "figure" }, encoding: { text: { field: "value", type: "quantitative" } } }, rows: [{ value: "2500000" }], data_used: used }} />);
  expect(screen.getByText("103,405,000.0")).toBeInTheDocument();
  expect(screen.getByText("2,500,000.0")).toBeInTheDocument();
});
