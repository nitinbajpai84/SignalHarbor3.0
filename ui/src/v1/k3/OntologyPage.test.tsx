import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { layout, layoutCompany, visible } from "./onto";
import MapPage from "./MapPage";
import ReviewQueue from "./ReviewQueue";
import fx from "./onto.fixtures.json";
import type { Ontology } from "./api";

// V5W-6: the whole-company map and its review queue. onto.fixtures.json is real output of k3_onto on the seeded test company.
const o = fx.ontology as unknown as Ontology;
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const posts: { url: string; body: unknown }[] = [];
const stub = () => vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
  if (init?.method === "POST") { posts.push({ url, body: JSON.parse(String(init.body)) }); return json(200, { ok: true }); }
  return url.endsWith("/ontology") ? json(200, fx.ontology) : url.endsWith("/review") ? json(200, fx.review) : json(404, {});
}));
afterEach(() => { vi.unstubAllGlobals(); posts.length = 0; });
const page = (ui: React.ReactElement, at: string) => render(<ThemeProvider><MemoryRouter initialEntries={[at]}>{ui}</MemoryRouter></ThemeProvider>);

test("layout puts each layer in its own column and the meaning band beneath", () => {
  const v = visible(o, { lens: "all", hidden: new Set(), state: "all", project: null, q: "" });
  const L = layout(v.nodes, v.edges);
  const x = (id: string) => L.placed.get(id)!.x;
  const gold = v.nodes.find((n) => n.layer === "gold")!, src = v.nodes.find((n) => n.type === "source")!, dash = v.nodes.find((n) => n.type === "dashboard")!;
  expect(x(src.id)).toBeLessThan(x(gold.id));
  expect(x(gold.id)).toBeLessThan(x(dash.id));
  const def = v.nodes.find((n) => n.type === "definition");
  if (def) expect(L.placed.get(def.id)!.y).toBeGreaterThan(L.placed.get(gold.id)!.y);
});

test("the ontology opens on the flow with meaning hidden; a click gives the item's card", async () => {
  stub();
  page(<MapPage />, "/centre/map");
  expect(await screen.findByRole("group", { name: "Company graph" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Ontology" })).toHaveAttribute("aria-pressed", "true");   // the Map opens on the ontology, everything shown
  expect(screen.getAllByRole("button", { name: /, Project, / }).length).toBeGreaterThan(0);
  expect(screen.queryByRole("group", { name: "Lenses" })).toBeNull();   // the lens row is gone
  expect(screen.queryByRole("link", { name: "Company map" })).toBeNull();
  expect(screen.getByRole("button", { name: /^Cases/ })).toHaveAttribute("aria-pressed", "false");   // meaning starts hidden, one click brings it back
  expect(screen.getByRole("button", { name: /^People/ })).toHaveAttribute("aria-pressed", "true");
  const proj = await screen.findByRole("button", { name: /Monthly investment report, Project, in progress|Monthly investment report, Project, verified/ });
  fireEvent.click(proj);
  const card = screen.getByRole("complementary", { name: "About this item" });
  expect(within(card).getByText("Raised from")).toBeInTheDocument();
});

test("the Map shows no waiting bar, no list chip and no agents; the three views are the only switch", async () => {
  stub();
  page(<MapPage />, "/centre/map");
  await screen.findByRole("group", { name: "Company graph" });
  expect(screen.queryByText(/wait for the head of data/)).toBeNull();
  for (const gone of ["Show as a list", "Whole company", /^Agents/, "Data flow by stage", "Conversations"]) expect(screen.queryByRole("button", { name: gone })).toBeNull();
  expect(screen.queryByRole("button", { name: /, Agent, / })).toBeNull();
  for (const v of ["Ontology", "Process map", "Business glossary"]) expect(screen.getByRole("button", { name: v })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "The office's ontology" })).toBeInTheDocument();
  expect(screen.getByLabelText("Find on the map")).toBeInTheDocument();
  expect(screen.getByLabelText("One project")).toBeInTheDocument();
});

test("one project at a time: the growth steps, replay, and what each step added", async () => {
  stub();
  page(<MapPage />, `/centre/map?project=${o.projects[0]!.id}`);
  expect(await screen.findByText(/grew the map/)).toBeInTheDocument();
  const steps = screen.getByRole("group", { name: "Project steps" });
  expect(within(steps).getAllByRole("button")).toHaveLength(4);
  fireEvent.click(within(steps).getByRole("button", { name: /Intent/ }));
  expect(screen.getByText(/Step 1 of 4/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Replay the growth" })).toBeInTheDocument();
});

test("review queue: approve the selected, reject only with a reason", async () => {
  stub();
  page(<ReviewQueue />, "/centre/map/review");
  const approve = await screen.findByRole("button", { name: /Approve the 4 selected/ });
  fireEvent.click(approve);
  await waitFor(() => expect(posts[0]?.url).toBe("/api/v1/centre-map/review/approve"));
  expect((posts[0]!.body as { ids: string[] }).ids).toHaveLength(4);
  const reject = await screen.findByRole("button", { name: "Reject and send back" });
  expect(reject).toBeDisabled();
  fireEvent.change(screen.getByLabelText(/Reason, if you reject/), { target: { value: "Wrong audience" } });
  expect(reject).toBeEnabled();
  fireEvent.click(reject);
  await waitFor(() => expect(posts[1]?.url).toBe("/api/v1/centre-map/review/reject"));
  expect(posts[1]!.body).toMatchObject({ reason: "Wrong audience" });
});

test("review queue: the person who built the project cannot review it (maker never checker)", async () => {
  const mine = { ...fx.review, projects: fx.review.projects.map((p: object) => ({ ...p, mine: true })) };
  vi.stubGlobal("fetch", vi.fn(async (url: string) => (String(url).endsWith("/review") ? json(200, mine) : json(404, {}))));
  page(<ReviewQueue />, "/centre/map/review");
  expect(await screen.findAllByText(/another person has to review what it made/)).not.toHaveLength(0);
  expect(screen.queryByRole("button", { name: /Approve the/ })).not.toBeInTheDocument();
});

test("F1: the graph is drawn to fit its width and no node reaches past the right edge", async () => {
  const v = visible(o, { lens: "all", hidden: new Set(), state: "all", project: null, q: "" });
  const L = layout(v.nodes, v.edges);
  expect(Math.max(...[...L.placed.values()].map((p) => p.x + 132))).toBeLessThanOrEqual(L.width - 8);
  stub();
  page(<MapPage />, "/centre/map");
  const svg = await screen.findByRole("group", { name: "Company graph" });
  expect(svg.getAttribute("viewBox")).toMatch(/^0 0 [0-9]+ [0-9]+$/);
  expect(svg.getAttribute("width")).toBe("100%");
});


test("V6 (F1): the whole-company layout puts people and agents across the top, projects beneath, the data in the middle and meaning below", () => {
  const v = visible(o, { lens: "all", hidden: new Set(), state: "all", project: null, q: "" });
  const L = layoutCompany(v.nodes, v.edges, o.columns);
  const y = (t: string) => Math.min(...v.nodes.filter((n) => n.type === t).map((n) => L.placed.get(n.id)!.y));
  expect(y("person")).toBeLessThan(y("project"));
  expect(y("project")).toBeLessThan(y("source"));
  const gold = v.nodes.find((n) => n.layer === "gold")!, src = v.nodes.find((n) => n.type === "source")!, dash = v.nodes.find((n) => n.type === "dashboard")!;
  expect(L.placed.get(src.id)!.x).toBeLessThan(L.placed.get(gold.id)!.x);   // the flow still reads left to right
  expect(L.placed.get(gold.id)!.x).toBeLessThan(L.placed.get(dash.id)!.x);
  const def = v.nodes.find((n) => n.type === "definition");
  if (def) expect(L.placed.get(def.id)!.y).toBeGreaterThan(L.placed.get(gold.id)!.y);
  expect(L.labels.map((l) => l.text)).toEqual(expect.arrayContaining(["People", "Projects"]));
  expect(v.nodes.some((n) => n.type === "agent")).toBe(false);   // agents own nothing: the view leaves them off
  expect(L.placed.size).toBe(v.nodes.length);   // every node is drawn once
});

test("/centre/map opens on the ontology", async () => {
  stub();
  const { routes } = await import("./routes");
  const home = routes.find((r) => r.path === "map")!;
  page(home.element as React.ReactElement, "/centre/map");
  expect(await screen.findByRole("heading", { name: "The office's ontology" })).toBeInTheDocument();
});

test("the old whole-company address lands on the Map and keeps its choices", async () => {
  stub();
  const { routes } = await import("./routes");
  const Where = () => <p data-testid="where">{useLocation().pathname}{useLocation().search}</p>;
  render(<ThemeProvider><MemoryRouter initialEntries={["/centre/map/company?lens=flow"]}><Routes>
    {routes.map((r) => <Route key={r.path} path={`/centre/${r.path}`} element={r.element} />)}</Routes><Where /></MemoryRouter></ThemeProvider>);
  await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("/centre/map?lens=flow"));
});

test("the ontology graph zooms with the buttons, clamps at 0.5 to 2.5, and Fit resets", async () => {
  stub();
  page(<MapPage />, "/centre/map");
  await screen.findByRole("group", { name: "Company graph" });
  const layer = screen.getByTestId("graph-zoom");
  const scale = () => Number(/scale\(([0-9.]+)\)/.exec(layer.style.transform)![1]);
  expect(scale()).toBe(1);
  fireEvent.click(screen.getByRole("button", { name: "Zoom in" }));
  expect(scale()).toBeCloseTo(1.25);
  for (let i = 0; i < 10; i++) fireEvent.click(screen.getByRole("button", { name: "Zoom in" }));
  expect(scale()).toBe(2.5);
  for (let i = 0; i < 20; i++) fireEvent.click(screen.getByRole("button", { name: "Zoom out" }));
  expect(scale()).toBe(0.5);
  fireEvent.click(screen.getByRole("button", { name: "Fit" }));
  expect(scale()).toBe(1);
});
