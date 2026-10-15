import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import MapPage from "./MapPage";
import fx from "./model.fixtures.json";

vi.mock("../../useSession", () => ({ useSession: () => ({ user: { roles: ["analyst"] } }), useSessionIfAny: () => ({ user: { roles: ["analyst"] } }) }));

// DM1: the Data model view against k3_model.py. model.fixtures.json is real output of the handler (test_k3_model.py checks its keys).
const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
const open = async (model: unknown = fx, at = "/centre/map?view=model") => {
  vi.stubGlobal("fetch", vi.fn(async () => json(model)));
  render(<ThemeProvider><MemoryRouter initialEntries={[at]}><MapPage /></MemoryRouter></ThemeProvider>);
  await screen.findByRole("heading", { name: "The data model" });
  await screen.findByText(fx.intro);
};
afterEach(() => vi.unstubAllGlobals());

test("the Map switch has the Data model option between Process map and Business glossary, and ?view=model opens it", async () => {
  await open();
  const tabs = within(screen.getByRole("tablist", { name: "Map views" })).getAllByRole("button").map((b) => b.textContent);
  expect(tabs).toEqual(["Ontology", "Process map", "Data model", "Business glossary"]);
  expect(screen.getByRole("button", { name: "Data model" })).toHaveAttribute("aria-pressed", "true");
});

test("three layers, each with its meaning, every table shown with its layer prefix; loaded tables only by default", async () => {
  await open();
  for (const h of [/^Bronze ·/, /^Silver ·/, /^Gold ·/]) expect(screen.getByRole("heading", { name: h })).toBeInTheDocument();
  expect(screen.getByText(fx.layers.gold.meaning)).toBeInTheDocument();
  for (const id of ["silver.valuation_observations", "gold.monthly_report_valuation_monthly"]) expect(screen.getByRole("button", { name: new RegExp(id.replace(/\./g, "\.")) })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Loaded · \d+/ })).toHaveAttribute("aria-pressed", "true");
  expect(screen.queryByRole("button", { name: /silver\.benchmark_definitions/ })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: /Whole model · \d+/ }));
  expect(screen.getByRole("button", { name: /silver\.benchmark_definitions/ })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /bronze\.administrator_export_valuations/ })).toBeInTheDocument();
});

test("picking a table shows its columns and what changes if it changes; gold shows what it reads", async () => {
  await open();
  fireEvent.click(screen.getByRole("button", { name: /^silver\.valuation_observations/ }));
  const detail = screen.getByRole("region", { name: "silver.valuation_observations" });
  expect(within(detail).getByText("Type")).toBeInTheDocument();
  const impact = screen.getByRole("complementary", { name: "If this table changes" });
  expect(within(impact).getByText(/1 gold table reads it, which feed 1 dashboard, in 1 project\./)).toBeInTheDocument();
  expect(within(impact).getByText("Dashboard: Net worth by month")).toBeInTheDocument();
  expect(within(impact).getByText("gold.monthly_report_valuation_monthly")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /^gold\.monthly_report_valuation_monthly/ }));
  expect(screen.getByText(/It reads: .*silver\.valuation_observations/)).toBeInTheDocument();
});

test("find narrows the tables by name or by a column", async () => {
  await open();
  fireEvent.click(screen.getByRole("button", { name: /Whole model/ }));
  fireEvent.change(screen.getByLabelText("Find a table or column"), { target: { value: "month" } });
  expect(screen.getByRole("button", { name: /^gold\.monthly_report_valuation_monthly/ })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /^silver\.portfolios/ })).toBeNull();
  fireEvent.change(screen.getByLabelText("Find a table or column"), { target: { value: "zzzz" } });
  expect(screen.getByText(/No table matches/)).toBeInTheDocument();
});

test("someone outside the data team is told they see ready-made figures only", async () => {
  await open({ ...fx, team: false, tables: fx.tables.filter((t) => t.layer === "gold"), counts: { loaded: 1, whole: 1 } });
  expect(screen.getByText(/You see the ready-made figures of the projects you can open/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /^silver\./ })).toBeNull();
});

test("someone outside the data team is told Bronze and Silver are kept by the data team, not that none are loaded", async () => {
  await open({ ...fx, team: false, tables: fx.tables.filter((t) => t.layer === "gold"), counts: { loaded: 1, whole: 1 } });
  expect(screen.getAllByText(/Kept by the data team\. Ask the head of data or a data engineer/)).toHaveLength(2);
  expect(screen.queryByText(/None loaded yet/)).toBeNull();
});

// DM2: the lineage graph.
test("Lineage draws the graph; picking a silver table lights what it reads and what reads it, and says how many projects use it", async () => {
  await open();
  fireEvent.click(screen.getByRole("button", { name: "Lineage" }));
  const graph = screen.getByRole("group", { name: "Company graph" });
  expect(within(graph).getByRole("button", { name: /^valuation_observations, used by 1 project/ })).toBeInTheDocument();
  expect(within(graph).getByRole("button", { name: /used by 1 project/ })).toBeInTheDocument();
  fireEvent.click(within(graph).getByRole("button", { name: /^valuation_observations/ }));
  const lit = (name: RegExp) => within(graph).getByRole("button", { name }).getAttribute("opacity");
  expect(lit(/^monthly_report_valuation_monthly/)).toBe("1");   // gold, downstream
  expect(lit(/^Net worth by month/)).toBe("1");                 // dashboard, two steps down
  expect(lit(/^Monthly investment report, project/)).toBe("1"); // project, two steps down
  expect(lit(/^portfolios/) ?? "0.3").toBe("0.3");              // unrelated silver table is dimmed (or not drawn)
  expect(screen.getByRole("complementary", { name: "If this table changes" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Tables" }));
  expect(screen.getByRole("heading", { name: /^Bronze ·/ })).toBeInTheDocument();
});

test("a pick far downstream lights everything upstream, back to the source", async () => {
  await open();
  fireEvent.click(screen.getByRole("button", { name: "Lineage" }));
  const graph = screen.getByRole("group", { name: "Company graph" });
  fireEvent.click(within(graph).getByRole("button", { name: /^Net worth by month/ }));
  for (const n of [/^monthly_report_valuation_monthly/, /^valuation_observations/, /^Fund administrator, source/]) expect(within(graph).getByRole("button", { name: n }).getAttribute("opacity")).toBe("1");
});
