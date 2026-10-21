import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import * as client from "../../../api/client";
import KnowledgePage from "../KnowledgePage";
import * as api from "./api";
import { pack } from "./Domains";

vi.mock("../../Frame", () => ({ default: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));
vi.mock("../../../api/client", () => ({ getCompany: vi.fn() }));
vi.mock("./api", async (orig) => ({ ...(await orig<typeof api>()), getUseCases: vi.fn(), getStory: vi.fn(), getDomain: vi.fn(), getLogical: vi.fn(), getPhysical: vi.fn(), getDecisions: vi.fn() }));
vi.mock("../k/MoreViews", () => ({ default: () => <p>The older map views</p> }));

const m = vi.mocked(api);
const at = (q = "") => render(<MemoryRouter initialEntries={[`/v3/knowledge${q}`]}><KnowledgePage /></MemoryRouter>);
const item = (id: string, kind: api.ItemKind, label: string, sub = "", more: Partial<api.Item> = {}): api.Item => ({ id, kind, label, sub, detail: [{ k: "Means", v: `${label} means this` }], shared: [], ...more });
const story: api.Story = {
  id: "t-a", title: "Can Holdings pay the call?", stage: "live", stage_label: "Live", live: true, domain: { id: "cash", name: "Capital calls and cash" },
  who: { name: "Daniel Foo", role: "Head of Finance", at: "2026-10-21" }, asked: "Can Holdings pay it?", conversation: "/v3/thread/t-a",
  decisions: [item("brief:t-a", "brief", "Brief signed", "Daniel Foo · version 1"), item("rule:cash_buffer", "rule", "Cash buffer", "", { shared: [{ id: "t-b", title: "Log a call notice" }] })],
  kpis: [item("kpi:k1", "kpi", "Cash after calls due", "verified · recipe", { links: [{ label: "Open the figure page", to: "/v3/knowledge/figures/k1" }] }), item("kpi:k2", "kpi", "FX needed", "verified")],
  gold: [item("gold:g1", "gold", "cash after calls", "6 rows"), item("gold:g2", "gold", "fx needed", "1 row")],
  silver: [item("silver:cash_movements", "silver", "cash movements", "557 rows", { shared: [{ id: "t-b", title: "Log a call notice" }] })],
  bronze: [item("bronze:bank", "bronze", "Bank statements", "2 files")], used_by: [item("board:t-a", "board", "Board", "Can Holdings pay the call?")],
  edges: [["rule:cash_buffer", "kpi:k1"], ["gold:g1", "kpi:k1"], ["silver:cash_movements", "gold:g1"], ["bronze:bank", "silver:cash_movements"], ["gold:g2", "kpi:k2"], ["kpi:k1", "board:t-a"]],
};
const lists: api.UseCases = {
  groups: [{ domain: "cash", name: "Capital calls and cash", count: 2, items: [
    { id: "t-a", title: "Can Holdings pay the call?", stage: "live", stage_label: "Live", live: true, asked_by: "Daniel Foo", role: "", figures: 2, find: "can holdings pay the call? daniel foo cash after calls due" },
    { id: "t-b", title: "Log a call notice", stage: "decision2", stage_label: "x", live: false, asked_by: "Sam Lee", role: "", figures: 1, find: "log a call notice sam lee" }] }],
  domains: [{ id: "cash", name: "Capital calls and cash", count: 2 }, { id: "hold", name: "Holdings and risk", count: 0 }], total: 2,
};
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(client.getCompany).mockResolvedValue({ company_id: "evergreen", name: "Evergreen", industry: "" });
  m.getUseCases.mockResolvedValue(lists);
  m.getStory.mockResolvedValue(story);
});

test("five tabs and More views; Use cases is the default and the older views sit behind More views", async () => {
  at();
  expect(await screen.findByRole("heading", { name: "Can Holdings pay the call?" })).toBeInTheDocument();
  for (const t of ["Use cases", "Domains", "Data model", "Decisions and rules", "Library", "More views"]) expect(screen.getByRole("button", { name: t })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Use cases" })).toHaveAttribute("aria-pressed", "true");
  fireEvent.click(screen.getByRole("button", { name: "More views" }));
  expect(await screen.findByText("The older map views")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Library" }));
  const lib = within(screen.getByRole("region", { name: "Library" }));
  expect(lib.getByRole("link", { name: /Figures/ })).toHaveAttribute("href", "/v3/knowledge/figures");
  expect(lib.getByRole("link", { name: /Skills Harbor uses/ })).toHaveAttribute("href", "/v3/knowledge/skills");
  expect(lib.getByRole("link", { name: /What Harbor watches for/ })).toHaveAttribute("href", "/v3/knowledge/signals");
});

test("the story runs top to bottom, shows the shared dot, and a click shows the detail with its links", async () => {
  at();
  await screen.findByRole("heading", { name: "Can Holdings pay the call?" });
  expect(screen.getByText(/Daniel Foo/, { selector: ".ks-who b" })).toBeInTheDocument();
  expect(screen.getByText(/“Can Holdings pay it\?”/)).toBeInTheDocument();
  const labels = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
  expect(labels).toEqual(["Who asked", "What they asked", "Decisions and rules", "KPIs", "Gold tables", "Silver tables", "Bronze sources", "Used by"]);
  expect(within(screen.getByRole("button", { name: /Cash buffer/ })).getByRole("img", { name: "Shared with other use cases" })).toBeInTheDocument();
  expect(within(screen.getByRole("button", { name: /Cash after calls due/ })).queryByRole("img")).toBeNull();
  const detail = screen.getByRole("complementary", { name: "Detail" });
  expect(within(detail).getByRole("heading", { name: "Cash after calls due" })).toBeInTheDocument();  // the first KPI is selected at first
  expect(within(detail).getByRole("link", { name: "Open the figure page" })).toHaveAttribute("href", "/v3/knowledge/figures/k1");
  expect(within(detail).getByRole("link", { name: "Open the use case conversation" })).toHaveAttribute("href", "/v3/thread/t-a");
  fireEvent.click(screen.getByRole("button", { name: /cash movements/ }));
  expect(within(detail).getByRole("heading", { name: "cash movements" })).toBeInTheDocument();
  expect(within(detail).getByRole("link", { name: "Log a call notice" })).toBeInTheDocument();
});

test("Show only its path dims everything not on that item's path, and Show everything brings it back", async () => {
  at();
  await screen.findByRole("heading", { name: "Can Holdings pay the call?" });
  fireEvent.click(screen.getByRole("button", { name: /Cash after calls due/ }));
  fireEvent.click(screen.getByRole("button", { name: "Show only its path" }));
  const dim = (n: RegExp) => screen.getByRole("button", { name: n }).className.includes("dim");
  expect(dim(/FX needed/)).toBe(true);
  expect(dim(/fx needed/)).toBe(true);
  expect(dim(/Brief signed/)).toBe(true);
  for (const n of [/Cash buffer/, /cash after calls/, /cash movements/, /Bank statements/, /Board/]) expect(dim(n)).toBe(false);  // up to its rule and down to its sources and use
  expect(screen.getByRole("status")).toHaveTextContent("Showing only the path of Cash after calls due");
  fireEvent.click(within(screen.getByRole("status")).getByRole("button", { name: "Show everything" }));
  expect(dim(/FX needed/)).toBe(false);
});

test("Find narrows the list of use cases", async () => {
  at();
  await screen.findByRole("heading", { name: "Can Holdings pay the call?" });
  fireEvent.change(screen.getByRole("searchbox", { name: "Find" }), { target: { value: "sam lee" } });
  const nav = screen.getByRole("navigation", { name: "Use cases by domain" });
  expect(within(nav).queryByRole("button", { name: "Can Holdings pay the call?" })).toBeNull();
  expect(within(nav).getByRole("button", { name: "Log a call notice" })).toBeInTheDocument();
});

test("pack: an item in every column is a banner; adjacent columns span; a gap splits it", () => {
  const it = (id: string, cols: number[], so = false): api.DomainItem => ({ id, label: id, sub: "", kind: "kpi", cols, shared_outside: so });
  const r = pack([it("all", [0, 1, 2]), it("two", [0, 1]), it("gap", [0, 2]), it("one", [2], true)], 3);
  expect(r.banner.map((b) => b.id)).toEqual(["all"]);
  const cells = r.lines.flat().map((c) => `${c.item.id}:${c.start}+${c.span}${c.shared ? "*" : ""}`);
  expect(cells).toEqual(["two:0+2*", "gap:0+1*", "one:2+1*", "gap:2+1*"].sort((a, b) => cells.indexOf(a) - cells.indexOf(b)));
  expect(new Set(cells)).toEqual(new Set(["two:0+2*", "gap:0+1*", "gap:2+1*", "one:2+1*"]));
});

test("Domains: use cases are columns, the shared KPI spans both, a header opens the story", async () => {
  const dom: api.Domain = {
    id: "cash", name: "Capital calls and cash", people: 2, usecases: [{ id: "t-a", title: "Can Holdings pay?", who: "Daniel Foo", role: "" }, { id: "t-b", title: "Log a call notice", who: "Sam Lee", role: "" }, { id: "t-c", title: "Weekly run", who: "Grace Ong", role: "" }],
    rows: {
      decisions: { label: "Decisions", items: [], hidden: 0 },
      kpis: { label: "KPIs", items: [{ id: "kpi:s", label: "Call payment status", sub: "", kind: "kpi", cols: [0, 1], shared_outside: false }, { id: "kpi:c", label: "Cash after calls due", sub: "", kind: "kpi", cols: [0], shared_outside: false }], hidden: 0 },
      gold: { label: "Gold", items: [], hidden: 0 }, silver: { label: "Silver", items: [{ id: "silver:a", label: "cash movements", sub: "557 rows", kind: "silver", cols: [0, 1, 2], shared_outside: false }], hidden: 0 }, bronze: { label: "Bronze", items: [], hidden: 0 },
    },
    others: [{ id: "hold", name: "Holdings and risk", count: 2 }],
  };
  m.getDomain.mockResolvedValue(dom);
  at("?tab=domains");
  expect(await screen.findByRole("heading", { name: "Capital calls and cash" })).toBeInTheDocument();
  expect(screen.getByText(/3 use cases/)).toBeInTheDocument();
  const kpi = screen.getByText("Call payment status").closest(".kd-cell") as HTMLElement;
  expect(kpi).toHaveTextContent("shared by 2");
  expect(kpi).toHaveTextContent("Call payment status");
  expect(kpi.className).toContain("shared");
  expect(kpi.getAttribute("style")).toContain("span 2");
  expect(screen.getByText(/Shared by all 3:/).closest(".kd-cell")).toHaveTextContent("cash movements");
  expect(screen.getByRole("button", { name: /Holdings and risk/ })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Log a call notice/ }));
  expect(await screen.findByRole("heading", { name: "Can Holdings pay the call?" })).toBeInTheDocument();  // the story of the first use case opens (the mocked story)
  await waitFor(() => expect(m.getStory).toHaveBeenCalled());
});

test("Data model: logical shows plain relations and an entity's KPIs; physical lights one KPI's path", async () => {
  const objs: api.LogicalObject[] = [
    { id: "entity", label: "Legal entity", about: "a company the family owns", count: 3, table: "legal entities", properties: [{ label: "Entity name" }], relations: [{ to: "bank_account", to_label: "Bank account", label: "banks with" }], kpis: [{ id: "k1", name: "Cash after calls due", usecases: [{ id: "t-a", title: "Can Holdings pay?" }] }] },
    { id: "bank_account", label: "Bank account", about: "accounts", count: 38, table: "bank accounts", properties: [], relations: [], kpis: [] },
  ];
  m.getLogical.mockResolvedValue({ objects: objs, pack: null });
  const phys = (kpi: boolean): api.Physical => ({
    bronze: { items: [{ id: "bronze:a", label: "Bank statements", rows: 2, kinds: "csv" }, { id: "bronze:b", label: "Invoices", rows: 1, kinds: "pdf" }], total: 3 },
    silver: { items: [{ id: "silver:cash_movements", label: "cash movements", rows: 557 }, { id: "silver:documents", label: "documents", rows: 9 }], total: 2 },
    gold: { items: [{ id: "gold:g1", label: "cash after calls", rows: 6, usecase: "Can Holdings pay?" }], total: 1 },
    kpis: { items: [{ id: "k1", name: "Cash after calls due", status: "verified", usecases: [{ id: "t-a", title: "Can Holdings pay?", who: "Daniel Foo" }], used_by: [{ kind: "board", label: "Board", sub: "" }], gold: ["gold:g1"], silver: ["silver:cash_movements"], bronze: ["bronze:a"] }], total: 1 },
    picked: kpi ? { id: "k1", name: "Cash after calls due", status: "verified", usecases: [{ id: "t-a", title: "Can Holdings pay?", who: "Daniel Foo" }], used_by: [{ kind: "board", label: "Board", sub: "" }], gold: ["gold:g1"], silver: ["silver:cash_movements"], bronze: ["bronze:a"] } : null,
    path: kpi ? { gold: ["gold:g1"], silver: ["silver:cash_movements"], bronze: ["bronze:a"] } : null,
  });
  m.getPhysical.mockImplementation((k) => Promise.resolve(phys(!!k)));
  at("?tab=model");
  expect(await screen.findByText("banks with")).toBeInTheDocument();
  const detail = screen.getByRole("complementary", { name: "Detail" });
  expect(within(detail).getByRole("link", { name: "Cash after calls due" })).toHaveAttribute("href", "/v3/knowledge/figures/k1");
  fireEvent.click(screen.getByRole("button", { name: /Bank account/ }));
  expect(within(detail).getByRole("heading", { name: "Bank account" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Physical" }));
  expect(await screen.findByText("Invoices", { exact: false })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "What Harbor knows" })).toHaveAttribute("href", "/v3/trust/ontology");
  fireEvent.change(screen.getByRole("combobox", { name: "KPI" }), { target: { value: "k1" } });
  await waitFor(() => expect(m.getPhysical).toHaveBeenCalledWith("k1"));
  const chip = (t: string) => screen.getByText(t).closest(".ks-chip") as HTMLElement;
  await waitFor(() => expect(chip("Invoices").className).toContain("dim"));
  expect(chip("Bank statements").className).not.toContain("dim");
  expect(chip("documents").className).toContain("dim");
  expect(chip("cash movements").className).not.toContain("dim");
});

test("Decisions and rules: one list, filtered by kind, each with the use cases it affects", async () => {
  const rows: api.DecisionRow[] = [
    { id: "rule:a", kind: "rule", label: "Cash buffer", sub: "Rule · version 2 · Daniel Foo", detail: [{ k: "What it says", v: "Keep 250,000" }], usecases: [{ id: "t-a", title: "Can Holdings pay?" }] },
    { id: "brief:t-a", kind: "decision", label: "Brief signed", sub: "Daniel", detail: [], usecases: [{ id: "t-a", title: "Can Holdings pay?" }] },
    { id: "as:1", kind: "assumption", label: "Rate is the fixing", sub: "x", detail: [], usecases: [] },
  ];
  m.getDecisions.mockResolvedValue({ items: rows, counts: { rule: 1, decision: 1, assumption: 1 }, in_force: 1 });
  at("?tab=decisions");
  expect(await screen.findByText("Keep 250,000")).toBeInTheDocument();
  expect(screen.getAllByRole("link", { name: "Can Holdings pay?" })[0]).toHaveAttribute("href", "/v3/knowledge?tab=usecases&uc=t-a");
  fireEvent.click(screen.getByRole("button", { name: /Assumptions/ }));
  expect(screen.queryByText("Cash buffer")).toBeNull();
  expect(screen.getByText("Rate is the fixing")).toBeInTheDocument();
  expect(screen.getByText("No use case reads it yet.")).toBeInTheDocument();
});
