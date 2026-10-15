import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { DataSourcesTab } from "./DataSourcesTab";

// B15: the Data sources tab. fetch is stubbed with synthetic data.

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const cell = (value: string | null, mark = "stated") => ({ value, mark: value ? mark : "unknown", by: "Janet Shaw", from: null });
const CAN = { edit: true, set_class: false, confirm: false, reassign: false, remove: true, restore: false, problem: true };
const src = (id: string, name: string, owners: [string | null, string | null, string | null], state: string, can = {}) => ({
  id, name, system: { ref: "systems.portfolio", name: "Portfolio system" }, format: cell("Manual workbook (Excel)"), structure: cell(null), lands: cell("A shared folder"),
  connection: cell(null), frequency: cell("Daily"), sla: cell(null), personal: cell("Not sure", "guessed"), who_may_see: cell(null), undecided: true,
  owners: { business: cell(owners[0]), data: cell(owners[1]), source: cell(owners[2]) }, state, confirmed_by: null, waiting_for: owners[2], proposals: {},
  fields: [{ id: "F001", name: "NAV", meaning: null, class: null }], used_in: { measures: [], steps: [], clusters: ["Late calls"] }, problems: [], left_out: null, history: [],
  can: { ...CAN, ...can },
});
const DATA = (over = {}) => ({
  sources: [src("S01", "Performance workbook", ["Daniel Kerr", "Grace Ward", "Harvey Rowley"], "edited", { confirm: true }), src("S02", "Custodian file", [null, "Grace Ward", null], "needs_owner")],
  left_out: [], restricted: 1, counters: { named: 2, confirmed: 0 },
  areas: { chips: [{ id: "system:portfolio", kind: "system", name: "Portfolio system", count: 2, confirmed: false, source_ids: ["S01"], linked: ["team:ops"], who_can_say: [{ name: "Harvey Rowley", mark: "stated" }], hidden: null },
    { id: "team:ops", kind: "team", name: "Operations", count: 2, confirmed: false, source_ids: [], linked: [], who_can_say: [], hidden: null }], hidden: [], nobody_named: 1 },
  data_sources: { state: "in_review", done_by: null, done_at: null }, systems: [{ ref: "systems.portfolio", name: "Portfolio system" }], people: ["Harvey Rowley"],
  schema: { formats: ["File drop: CSV or Excel"], frequencies: ["Daily"], connections: ["API"], structures: ["Structured"], classes: ["Yes", "No", "Not sure"] },
  can: { draft: true, add: true, done: true, area: true }, ...over,
});

const calls: { url: string; method: string; body: Record<string, unknown> }[] = [];
function mock(body: unknown, status = 200) {
  calls.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method && init.method !== "GET") { calls.push({ url, method: init.method, body: JSON.parse(String(init.body)) }); return json(200, { message: "Lens drafted 1 source from 0 documents and the systems list.", id: "S09" }); }
    return json(status, body);
  }));
}
afterEach(() => vi.unstubAllGlobals());

test("shows the progress line, three separate owner lines, Not named yet, the chips and the restricted line", async () => {
  mock(DATA());
  render(<DataSourcesTab intentId="ini-1" />);
  expect((await screen.findAllByText("Performance workbook")).length).toBeGreaterThan(0);
  expect(screen.getByText(/2 named, 0 confirmed by their source owner, 1 restricted source/)).toBeInTheDocument();
  for (const k of ["Business owner", "Data owner", "Source owner"]) expect(screen.getAllByText(k).length).toBeGreaterThan(1);
  expect(screen.getAllByText("Not named yet").length).toBeGreaterThan(0);
  expect(screen.queryByText("Owner")).toBeNull();
  expect(screen.getAllByRole("button", { name: /Portfolio system/ }).length).toBeGreaterThan(0);
  expect(screen.getByText("A restricted source")).toBeInTheDocument();
  expect(screen.getAllByText("Needs source owner").length).toBeGreaterThan(0);
});

test("the empty state and the missing baseline say what is missing", async () => {
  mock(DATA({ sources: [], restricted: 0, counters: { named: 0, confirmed: 0 }, areas: { chips: [], hidden: [], nobody_named: 0 }, systems: [] }));
  render(<DataSourcesTab intentId="ini-1" />);
  expect((await screen.findAllByText(/No sources named yet\. Ask Lens to draft/)).length).toBeGreaterThan(0);
  expect(screen.getByText(/No systems or teams named yet/)).toBeInTheDocument();
  expect(screen.getByText("Ask Lens to draft").closest("button")).toBeDisabled();
});

test("Confirm shows only to the named source owner and posts the confirmation", async () => {
  mock(DATA());
  render(<DataSourcesTab intentId="ini-1" />);
  fireEvent.click((await screen.findAllByText("Performance workbook"))[0]!);
  fireEvent.click(await screen.findByText("Confirm this is how Harvey Rowley works"));
  await waitFor(() => expect(calls[0]).toMatchObject({ url: "/api/intents/ini-1/data-sources/S01/confirm", method: "POST" }));
  mock(DATA());
  render(<DataSourcesTab intentId="ini-2" />);
  fireEvent.click((await screen.findAllByText("Custodian file"))[0]!);
  expect(screen.queryByText(/Confirm this is how/)).toBeNull();
  expect(screen.queryByText(/Waiting for/)).toBeNull(); // S02 has no source owner: nobody to wait for
});

test("Ask Lens to draft posts and shows what Lens did; Add a source needs a name", async () => {
  mock(DATA());
  render(<DataSourcesTab intentId="ini-1" />);
  await screen.findAllByText("Performance workbook");
  fireEvent.click(screen.getByText("Ask Lens to draft"));
  expect(await screen.findByText(/Lens drafted 1 source from 0 documents/)).toBeInTheDocument();
  expect(calls[0]).toMatchObject({ url: "/api/intents/ini-1/data-sources/draft", method: "POST" });
  fireEvent.click(screen.getByText("Add a source"));
  fireEvent.click(await screen.findByText("Save"));
  expect(await screen.findByText("A source needs a name.")).toBeInTheDocument();
});

test("an area drawer lists the sources here and who could say; a refused load shows the words", async () => {
  mock(DATA());
  render(<DataSourcesTab intentId="ini-1" />);
  await screen.findAllByText("Performance workbook");
  fireEvent.click(screen.getAllByRole("button", { name: /Portfolio system/ })[0]!);
  expect(await screen.findByText("Sources here")).toBeInTheDocument();
  expect(screen.getByText("People who could say")).toBeInTheDocument();
  expect(screen.getByText("Harvey Rowley", { selector: "li" })).toBeInTheDocument();
});
