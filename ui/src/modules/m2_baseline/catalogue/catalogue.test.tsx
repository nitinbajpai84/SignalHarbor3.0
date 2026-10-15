import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { copy } from "../../../copy";
import type { CatCell, CatColumn, CatRow, CatTab, CatTabSchema, CatalogueView, Mark } from "../api";
import { m2Cat as t } from "../copy";
import CatalogueScreen from "./CatalogueScreen";

// M2-P04 screens: the five tabs, stated/guessed/unknown, the unknown filter, conflicts, restricted rows, the download. Family-office wording only.

const BID = "b".repeat(32);
const BASE = `/api/modules/m2_baseline/baselines/${BID}/catalogue`;
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const calls: { method: string; url: string; body: unknown }[] = [];

const cell = (value: CatCell["value"], mark: Mark = "stated", by = "Arjun"): CatCell => ({ value, mark, by, at: "2026-10-03T09:00:00+00:00", from: "the questionnaire" });
const col = (header: string, required = false, over: Partial<CatColumn> = {}): CatColumn => ({ header, guidance: "", required, options: [], computed: false, picks_from: null, ...over });
const schema = (title: string, id: string, status: string, cols: CatColumn[]): CatTabSchema => ({ sheet: title, title, blurb: "", id_header: id, status_header: status, columns: [col(id), ...cols, col(status, false, { computed: true }), col("How sure are we", false, { computed: true })] });
const SCHEMA: Record<CatTab, CatTabSchema> = {
  sources: schema("1 Sources", "Source ID", "Complete?", [col("Source name", true), col("Source type", true, { options: ["Email with attachment", "Third-party portal or API"] }), col("Data owner", true), col("How often it arrives", true), col("Availability")]),
  tables: schema("2 Tables", "Item ID", "Complete?", [col("Source ID", true, { picks_from: "sources" }), col("Name of table, file or document type", true), col("Related KPIs", true)]),
  fields: schema("3 Fields", "Field ID", "Complete?", [col("Item ID", true, { picks_from: "tables" }), col("Field name as in the source", true), col("Feeds measure", true, { picks_from: "kpis" })]),
  extractions: schema("4 Extractions", "Extract ID", "Complete?", [col("Item ID (document type)", true, { picks_from: "tables" }), col("What to extract", true)]),
  kpis: schema("5 KPIs", "KPI ID", "Ready for module 3?", [col("KPI name", true), col("Priority"), col("Data owner", true), col("Tables mapped", false, { computed: true })]),
};
const row = (cells: Record<string, CatCell>): CatRow => cells;
const done = cell("Complete", "stated", "Signal Harbor");
const SOURCES = [
  row({ "Source ID": cell("S01"), "Source name": cell("Bank portal"), "Source type": cell("Third-party portal or API"), "Data owner": cell("Arjun"), "How often it arrives": cell("Daily"), "Complete?": done, "How sure are we": cell("Stated by a named person", "stated", "Signal Harbor") }),
  row({ "Source ID": cell("S02"), "Source name": cell("Call notices by email", "guessed", "Sara"), "Source type": cell(null, "unknown", "Lens"), "Data owner": cell("Sara"), "How often it arrives": cell(null, "unknown", "Lens"), "Complete?": cell("Missing 2 required", "stated", "Signal Harbor"), "How sure are we": cell("Guessed", "stated", "Signal Harbor") }),
  { "Source ID": cell("S03"), _hidden: true },
];
const KPIS = [
  row({ "KPI ID": cell("K01"), "KPI name": cell("Capital calls due, by date"), Priority: cell("Must"), "Data owner": cell("Sara"), "Tables mapped": cell(0, "stated", "Signal Harbor"), "Ready for module 3?": cell("Not ready", "stated", "Signal Harbor"), "How sure are we": cell("Unknown", "stated", "Signal Harbor") }),
];
const view = (over: Partial<CatalogueView> = {}): CatalogueView => ({
  baseline_id: BID, schema: SCHEMA, sources: SOURCES, tables: [], fields: [], extractions: [], kpis: KPIS, conflicts: [], findings: { K01: ["nothing_mapped", "no_data_owner"] }, ...over,
});
const CONFLICT = {
  id: "c-1", tab: "sources" as const, row_id: "S01", column: "How often it arrives", state: "open" as const, settled_by: null, settled_value: null, settled_at: null, note: null,
  versions: [{ value: "Daily", by: "Arjun", at: "2026-10-03T09:00:00+00:00", from: "q", kpi_id: "K02" }, { value: "Weekly", by: "Mei", at: "2026-10-03T10:00:00+00:00", from: "q", kpi_id: "K01" }],
};

function serve(get: () => Response | Promise<Response>, extra?: (url: string, method: string) => Response | undefined) {
  calls.length = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
      if (url === BASE && method === "GET") return get();
      return extra?.(url, method) ?? json(404, {});
    }),
  );
}
const open = () =>
  render(
    <MemoryRouter initialEntries={[`/catalogue/${BID}`]}>
      <Routes>
        <Route path="/catalogue/:baselineId" element={<CatalogueScreen />} />
      </Routes>
    </MemoryRouter>,
  );
afterEach(() => vi.unstubAllGlobals());
const first = <T,>(xs: T[]): T => {
  const x = xs[0];
  if (x === undefined) throw new Error("expected at least one");
  return x;
};

describe("the five screen states", () => {
  it("loading", () => {
    serve(() => new Promise<Response>(() => undefined));
    open();
    expect(screen.getByRole("status")).toHaveTextContent(copy.states.loading);
  });
  it("empty: honest, with the way to fill it", async () => {
    serve(() => json(200, view({ sources: [], kpis: [] })));
    open();
    expect(await screen.findByText(t.empty)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: t.refresh })).toBeEnabled();
  });
  it("error: plain words and a way to try again", async () => {
    serve(() => json(500, { error: "x" }));
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent(copy.states.error);
    expect(screen.getByRole("button", { name: copy.states.retry })).toBeInTheDocument();
  });
  it("refused: this module is not part of the plan", async () => {
    serve(() => json(403, { error: "module_not_available", message: "x" }));
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent(copy.states.refused);
  });
  it("populated", async () => {
    serve(() => json(200, view()));
    open();
    expect(await screen.findByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: t.title })).toBeInTheDocument();
  });
});

describe("the catalogue", () => {
  it("shows the five tabs with their counts and the download link", async () => {
    serve(() => json(200, view()));
    open();
    await screen.findByRole("table");
    expect(screen.getAllByRole("tab").map((x) => x.textContent)).toEqual(["Sources (3)", "Tables (0)", "Fields (0)", "Extractions (0)", "Measures (1)"]);
    expect(screen.getByRole("button", { name: t.download })).toBeInTheDocument();
  });

  it("marks stated, guessed and unknown; an unknown is never shown as filled", async () => {
    serve(() => json(200, view()));
    open();
    const table = await screen.findByRole("table");
    const s2 = within(table).getByText("S02").closest("tr") as HTMLElement;
    expect(within(s2).getAllByText(t.marks.guessed, { selector: ".n-pill" }).length).toBeGreaterThanOrEqual(2); // the guessed name, and the row as a whole
    expect(within(s2).getAllByText(t.unknown, { selector: ".n-pill" }).length).toBeGreaterThanOrEqual(2);
    const s1 = within(table).getByText("S01").closest("tr") as HTMLElement;
    expect(within(s1).getByText(t.marks.stated, { selector: ".n-pill" })).toBeInTheDocument();
  });

  it("filters to the rows with something unknown", async () => {
    serve(() => json(200, view()));
    open();
    const table = await screen.findByRole("table");
    expect(within(table).getByText("S01")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox", { name: new RegExp(t.filterUnknown) }));
    expect(within(screen.getByRole("table")).queryByText("S01")).not.toBeInTheDocument();
    expect(within(screen.getByRole("table")).getByText("S02")).toBeInTheDocument();
  });

  it("a row the person is not named for shows that it exists and nothing else", async () => {
    serve(() => json(200, view()));
    open();
    await screen.findByRole("table");
    const hidden = screen.getByText("S03").closest("tr") as HTMLElement;
    expect(within(hidden).getByText(t.restricted)).toBeInTheDocument();
    expect(within(hidden).queryByRole("button")).not.toBeInTheDocument();
  });

  it("a KPI with nothing mapped is visible, and says what else is missing", async () => {
    serve(() => json(200, view()));
    open();
    await userEvent.click(await screen.findByRole("tab", { name: /Measures/ }));
    const k = (await screen.findByText("K01")).closest("tr") as HTMLElement;
    expect(within(k).getByText(t.findings["nothing_mapped"] ?? "")).toBeInTheDocument();
    expect(within(k).getByText(t.findings["no_data_owner"] ?? "")).toBeInTheDocument();
    expect(within(k).getByText("0")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.addTo(t.tabs.kpis) })).not.toBeInTheDocument(); // KPIs come from the charter
  });

  it("opens a row to show who said each cell and when", async () => {
    serve(() => json(200, view()));
    open();
    await userEvent.click(first(await screen.findAllByRole("button", { name: t.open })));
    const panel = screen.getByRole("region", { name: "S01" });
    expect(within(panel).getAllByText(/Arjun, 2026-10-03/).length).toBeGreaterThan(0);
  });

  it("adds a row and sends only what was filled in", async () => {
    serve(() => json(200, view()), (url, method) => (url === `${BASE}/tables/rows` && method === "POST" ? json(200, { id: "T01" }) : undefined));
    open();
    await userEvent.click(await screen.findByRole("tab", { name: /Tables/ }));
    await userEvent.click(screen.getByRole("button", { name: t.addTo(t.tabs.tables) }));
    await userEvent.selectOptions(screen.getByLabelText(/^Source ID/), "S01");
    await userEvent.type(screen.getByLabelText(/^Name of table/), "statement.csv");
    await userEvent.click(screen.getByRole("button", { name: t.save }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.url === `${BASE}/tables/rows`)).toBe(true));
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ cells: { "Source ID": "S01", "Name of table, file or document type": "statement.csv" }, mark: "stated" });
  });

  it("edits one cell and sends only that cell, so the rest keep who said them", async () => {
    serve(() => json(200, view()), (url, method) => (url === `${BASE}/sources/rows/S02` && method === "PUT" ? json(200, { status: "saved" }) : undefined));
    open();
    await userEvent.click(first((await screen.findAllByRole("button", { name: t.open })).slice(1)));
    await userEvent.click(screen.getByRole("button", { name: t.edit }));
    await userEvent.type(screen.getByLabelText(/^How often it arrives/), "Weekly");
    await userEvent.click(screen.getByRole("button", { name: t.save }));
    await waitFor(() => expect(calls.some((c) => c.method === "PUT")).toBe(true));
    expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ cells: { "How often it arrives": "Weekly" }, mark: "stated" });
  });

  it("says in plain words why a save was refused", async () => {
    serve(() => json(200, view()), (url, method) => (method === "POST" && url.endsWith("/tables/rows") ? json(422, { error: "invalid", message: "That source is not in the catalogue yet. Add the source first." }) : undefined));
    open();
    await userEvent.click(await screen.findByRole("tab", { name: /Tables/ }));
    await userEvent.click(screen.getByRole("button", { name: t.addTo(t.tabs.tables) }));
    await userEvent.type(screen.getByLabelText(/^Name of table/), "x");
    await userEvent.click(screen.getByRole("button", { name: t.save }));
    expect(await screen.findByRole("alert")).toHaveTextContent("That source is not in the catalogue yet.");
  });

  it("fills the catalogue from the answers", async () => {
    serve(() => json(200, view()), (url, method) => (url === `${BASE}/refresh` && method === "POST" ? json(200, { status: "ok" }) : undefined));
    open();
    await screen.findByRole("table");
    await userEvent.click(screen.getByRole("button", { name: t.refresh }));
    expect(await screen.findByText(t.refreshed)).toBeInTheDocument();
  });
});

describe("conflicts", () => {
  it("shows both versions and who said each, and lets a named person settle it", async () => {
    serve(() => json(200, view({ conflicts: [CONFLICT] })), (url, method) => (url === `${BASE}/conflicts/c-1/settle` && method === "POST" ? json(200, { id: "c-1", state: "settled", settled_by: "Tom" }) : undefined));
    open();
    const panel = (await screen.findByRole("heading", { name: t.conflicts.heading })).closest("section") as HTMLElement;
    expect(within(panel).getByText(/“Daily”/)).toBeInTheDocument();
    expect(within(panel).getByText(/Arjun, 2026-10-03/)).toBeInTheDocument();
    expect(within(panel).getByText(/“Weekly”/)).toBeInTheDocument();
    expect(within(panel).getByText(/Mei, 2026-10-03/)).toBeInTheDocument();
    expect(within(panel).getByText(`Bank portal: How often it arrives`)).toBeInTheDocument();
    await userEvent.click(first(within(panel).getAllByRole("button", { name: t.conflicts.use })));
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/settle"))).toBe(true));
    expect(calls.find((c) => c.url.endsWith("/settle"))?.body).toEqual({ value: "Daily", note: "" });
  });

  it("keeps a settled conflict visible with who settled it", async () => {
    serve(() => json(200, view({ conflicts: [{ ...CONFLICT, state: "settled", settled_by: "Tom", settled_value: "Daily", note: "Arjun runs the download" }] })));
    open();
    expect(await screen.findByText(t.conflicts.settled("Tom"))).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.conflicts.use })).not.toBeInTheDocument();
  });

  it("says plainly when a person is refused", async () => {
    serve(() => json(200, view({ conflicts: [CONFLICT] })), () => json(403, { error: "forbidden", message: "x" }));
    open();
    await userEvent.click(first(await screen.findAllByRole("button", { name: t.conflicts.use })));
    expect(await screen.findByRole("alert")).toHaveTextContent(copy.states.noAccess);
  });
});

describe("personal data not decided yet, and fields with no meaning", () => {
  it("says plainly how many rows are hidden", async () => {
    serve(() => json(200, view({ hidden_note: "1 row is hidden until the organiser decides on personal data" })));
    open();
    expect(await screen.findByText("1 row is hidden until the organiser decides on personal data")).toBeInTheDocument();
  });

  it("flags a source whose personal-data answer is not decided yet, and only that one", async () => {
    const flagged: CatRow = { ...first(SOURCES), "Source ID": cell("S04"), _undecided: true };
    serve(() => json(200, view({ sources: [first(SOURCES), flagged] })));
    open();
    await screen.findByRole("table");
    expect(within(screen.getByText("S04").closest("tr") as HTMLElement).getByText(t.undecided)).toBeInTheDocument();
    expect(within(screen.getByText("S01").closest("tr") as HTMLElement).queryByText(t.undecided)).not.toBeInTheDocument();
  });

  it("a field with no known meaning says Not available yet, and several KPIs read together", async () => {
    const withMeaning = { ...SCHEMA, fields: { ...SCHEMA.fields, columns: [...SCHEMA.fields.columns, col("Business meaning", true)] } };
    const field = row({ "Field ID": cell("F001"), "Item ID": cell("T01"), "Field name as in the source": cell("period_return"), "Feeds measure": cell("K01, K02"), "Business meaning": cell(null, "unknown", "Signal Harbor"), "Complete?": done, "How sure are we": cell("Guessed", "stated", "Signal Harbor") });
    serve(() => json(200, view({ schema: withMeaning, fields: [field] })));
    open();
    await userEvent.click(await screen.findByRole("tab", { name: /Fields/ }));
    expect(await screen.findByText("K01, K02")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: t.open }));
    expect(screen.getByText(t.notAvailable, { selector: ".n-pill" })).toBeInTheDocument();
  });
});

describe("CRITIC-M2 round 4", () => {
  it("the unknown count includes a computed cell the list shows as Unknown, and the filter agrees with it", async () => {
    const { hasUnknown } = await import("./CatalogueTab");
    const sch = schema("5 KPIs", "KPI ID", "Ready for module 3?", [col("KPI name", true), col("Tables mapped", true, { computed: true })]);
    const r = row({ "KPI ID": cell("K01"), "KPI name": cell("Capital calls due, by date"), "Tables mapped": cell(null, "unknown", "Signal Harbor"), "Ready for module 3?": cell("Ready", "stated", "Signal Harbor") });
    expect(hasUnknown(r, sch)).toBe(false); // by the stored columns alone it looked complete
    expect(hasUnknown(r, sch, "kpis")).toBe(true); // but the list shows "Unknown" in that cell
  });
  it("a signed baseline shows the read-only banner and the rows cannot be changed", async () => {
    serve(() => json(200, view({ signed: true })));
    open();
    expect(await screen.findByText("Signed: read-only")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: t.addTo(t.tabs.sources) })).toBeDisabled();
  });
});
