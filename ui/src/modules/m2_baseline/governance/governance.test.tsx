import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { copy } from "../../../copy";
import type { CatTabSchema, GovRow, GovernanceView } from "../api";
import { m2Gov as t, m2Steps } from "../copy";
import GovernanceColumns from "./GovernanceColumns";
import GovernanceScreen from "./GovernanceScreen";

// M2-E3 screen: the five states, the summary, the filters, proposals, limiting a field, the signed banner, a restricted measure. Synthetic wording.

const BID = "d".repeat(32);
const URL = `/api/modules/m2_baseline/baselines/${BID}/governance`;
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const calls: { method: string; url: string; body: unknown }[] = [];

const everyone = { mode: "everyone" as const, text: "Everyone in the company with access to this module", names: [] };
const field = (id: string, name: string, over: Partial<GovRow> = {}): GovRow => ({
  kind: "field", id, name, restricted: false, personal: "Neither", sensitive: false, visible_to: everyone, decided: { by: "Test Pat", at: "2026-10-03T10:00:00+00:00" }, undecided: [], table: "balances", source: "Bank portal", ...over,
});
const FIELDS = [
  field("F001", "closing_balance"),
  field("F002", "contact_email", { personal: "", decided: null, undecided: ["no personal-data decision"], proposal: { class: "Personal data", kind: "contact", mark: "guessed", reason: "the name looks like contact details", by: "Lens" } }),
  field("F003", "due_date", { personal: "", decided: null, undecided: ["no personal-data decision"], proposal: { class: "Neither", kind: null, mark: "guessed", reason: "nothing in its name suggests personal data", by: "Lens" } }),
  field("F004", "salary", { personal: "Personal data", sensitive: true, restricted: true, visible_to: { mode: "follows", text: "Follows the measure “Pay review”", names: [] } }),
];
const view = (over: Partial<GovernanceView> = {}): GovernanceView => ({
  baseline_id: BID, signed: false, pack_label: "x", can_change: true,
  summary: { measures: { total: 2, decided: 1, undecided: 1, restricted: 1 }, sources: { total: 1, decided: 1, undecided: 0, restricted: 0 }, fields: { total: 4, decided: 2, undecided: 2, restricted: 1 }, lines: ["2 fields have no personal-data decision"] },
  measures: [
    { kind: "measure", id: "K01", name: "Capital calls due", restricted: false, personal: "no", sensitive: false, visible_to: everyone, decided: { by: "Test Pat", at: "2026-10-03T10:00:00+00:00" }, undecided: [],
      sources: [{ kind: "source", id: "S01", name: "Bank portal", restricted: false, personal: "No", sensitive: null, visible_to: everyone, decided: null, undecided: [] }], fields: FIELDS.slice(0, 3) },
  ],
  other_sources: [], other_fields: [FIELDS[3] as GovRow], organiser: false, note: null, ...over,
});

function serve(get: () => Response | Promise<Response>, extra?: (url: string, method: string) => Response | undefined) {
  calls.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    if (url === URL && method === "GET") return get();
    return extra?.(url, method) ?? json(404, {});
  }));
}
const open = () => render(<MemoryRouter initialEntries={[`/governance/${BID}`]}><Routes><Route path="/governance/:baselineId" element={<GovernanceScreen />} /></Routes></MemoryRouter>);
afterEach(() => vi.unstubAllGlobals());

describe("the five screen states", () => {
  it("loading", () => {
    serve(() => new Promise<Response>(() => undefined));
    open();
    expect(screen.getByRole("status")).toHaveTextContent(copy.states.loading);
  });
  it("empty: honest, with what to do", async () => {
    serve(() => json(200, view({ measures: [], other_fields: [] })));
    open();
    expect(await screen.findByText(t.empty)).toBeInTheDocument();
  });
  it("error: plain words and a way to try again", async () => {
    serve(() => json(500, { error: "x" }));
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent(copy.states.error);
    expect(screen.getByRole("button", { name: copy.states.retry })).toBeInTheDocument();
  });
  it("refused", async () => {
    serve(() => json(403, { error: "module_not_available", message: "x" }));
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent(copy.states.refused);
  });
  it("populated: the summary and the table", async () => {
    serve(() => json(200, view()));
    open();
    const table = await screen.findByRole("table", { name: t.tableLabel });
    expect(screen.getByText("2 fields have no personal-data decision")).toBeInTheDocument();
    expect(within(table).getByText("closing_balance")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: m2Steps.governance })).toHaveAttribute("href", `/modules/m2_baseline/governance/${BID}`);
  });
});

describe("the governance table", () => {
  it("says personal data, sensitive, who may see it, who decided and what is left, in plain words", async () => {
    serve(() => json(200, view()));
    open();
    const table = await screen.findByRole("table", { name: t.tableLabel });
    const k1 = within(table).getByText("Capital calls due").closest("tr") as HTMLElement;
    expect(within(k1).getAllByText(t.no)).toHaveLength(2); // holds no personal data, not sensitive
    expect(within(k1).getByText(/Everyone in the company/)).toBeInTheDocument();
    expect(within(k1).getByText(/Test Pat, 2026-10-03/)).toBeInTheDocument();
    const mail = within(table).getByText("contact_email").closest("tr") as HTMLElement;
    expect(within(mail).getByText(t.notDecided)).toBeInTheDocument();
    expect(within(mail).getByText("no personal-data decision")).toBeInTheDocument();
    const pay = within(table).getByText("salary").closest("tr") as HTMLElement;
    expect(within(pay).getByText(/Follows the measure/)).toBeInTheDocument();
  });

  it("shows a restricted measure as no row at all, only a plain line without a number", async () => {
    serve(() => json(200, view({ note: "Some measures are restricted to named people" })));
    open();
    const table = await screen.findByRole("table", { name: t.tableLabel });
    expect(within(table).queryByText("A restricted measure")).toBeNull();
    expect(screen.getByText("Some measures are restricted to named people")).toBeInTheDocument();
  });

  it("tells the organiser they see every row", async () => {
    serve(() => json(200, view({ organiser: true })));
    open();
    expect(await screen.findByText(t.organiserNote)).toBeInTheDocument();
  });

  it("filters: not decided, personal data, restricted", async () => {
    serve(() => json(200, view()));
    open();
    const table = await screen.findByRole("table", { name: t.tableLabel });
    await userEvent.click(screen.getByLabelText(t.filterUndecided));
    expect(within(table).queryByText("closing_balance")).toBeNull();
    expect(within(table).getByText("contact_email")).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText(t.filterUndecided));
    await userEvent.click(screen.getByLabelText(t.filterRestricted));
    expect(within(table).getAllByRole("row")).toHaveLength(2); // the header and the one restricted field shown
    expect(within(table).getByText("salary")).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText(t.filterRestricted));
    await userEvent.click(screen.getByLabelText(t.filterPersonal));
    expect(within(table).getByText("salary")).toBeInTheDocument();
    expect(within(table).queryByText("closing_balance")).toBeNull();
  });
});

describe("proposals and limiting a field", () => {
  it("labels Lens's proposal as a suggestion and confirms one field on request", async () => {
    serve(() => json(200, view()), (url, method) => (method === "POST" && url === `${URL}/proposals/confirm` ? json(200, { confirmed: ["F002"], skipped: 0 }) : undefined));
    open();
    const mail = (await screen.findByText("contact_email")).closest("tr") as HTMLElement;
    expect(within(mail).getByText(t.suggestion)).toBeInTheDocument();
    expect(within(mail).getByText(t.suggests("Personal data"))).toBeInTheDocument();
    await userEvent.click(within(mail).getByRole("button", { name: t.confirm }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ field_ids: ["F002"] });
    expect(await screen.findByText(t.confirmed(1))).toBeInTheDocument();
  });

  it("confirms all the proposals for fields that are not personal", async () => {
    serve(() => json(200, view()), (url, method) => (method === "POST" && url === `${URL}/proposals/confirm` ? json(200, { confirmed: ["F003"], skipped: 0 }) : undefined));
    open();
    await userEvent.click(await screen.findByRole("button", { name: t.confirmAll }));
    await waitFor(() => expect(calls.find((c) => c.method === "POST")?.body).toEqual({ only_not_personal: true }));
  });

  it("limits one field to named people", async () => {
    serve(() => json(200, view()), (url, method) => (method === "PUT" && url === `${URL}/fields/F001` ? json(200, { status: "saved" }) : undefined));
    open();
    const row = (await screen.findByText("closing_balance")).closest("tr") as HTMLElement;
    await userEvent.click(within(row).getByRole("button", { name: t.limit }));
    await userEvent.type(within(row).getByRole("textbox"), "Lena Hr, Alan Analyst");
    await userEvent.click(within(row).getByRole("button", { name: t.limitSave }));
    await waitFor(() => expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ may_see: ["Lena Hr", "Alan Analyst"] }));
  });

  it("a plain refusal from the server is shown in words", async () => {
    serve(() => json(200, view()), (url, method) => (method === "PUT" ? json(422, { error: "invalid", message: "That would let someone see this field who may not see its measure or source." }) : undefined));
    open();
    const row = (await screen.findByText("closing_balance")).closest("tr") as HTMLElement;
    await userEvent.click(within(row).getByRole("button", { name: t.limit }));
    await userEvent.type(within(row).getByRole("textbox"), "Someone");
    await userEvent.click(within(row).getByRole("button", { name: t.limitSave }));
    expect(await screen.findByRole("alert")).toHaveTextContent("may not see its measure");
  });

  it("someone who cannot change who may see is not offered the button", async () => {
    serve(() => json(200, view({ can_change: false })));
    open();
    await screen.findByRole("table", { name: t.tableLabel });
    expect(screen.queryByRole("button", { name: t.limit })).toBeNull();
    expect(screen.getByText(t.readOnlyNote)).toBeInTheDocument();
  });
});

describe("a signed baseline", () => {
  it("shows the read-only banner and offers no change", async () => {
    serve(() => json(200, view({ signed: true })));
    open();
    await screen.findByRole("table", { name: t.tableLabel });
    expect(screen.getByRole("status")).toHaveTextContent(m2Steps.signed);
    expect(screen.getByRole("button", { name: t.confirmAll })).toBeDisabled();
    const row = screen.getByText("closing_balance").closest("tr") as HTMLElement;
    expect(within(row).getByRole("button", { name: t.limit })).toBeDisabled();
  });
});

describe("the catalogue's governance columns", () => {
  const schema = { id_header: "Field ID" } as unknown as CatTabSchema;
  const cell = (v: string) => ({ value: v, mark: "stated" as const, by: "x", at: "", from: "" });
  it("shows personal data, sensitive and who may see it beside the Fields tab rows", () => {
    render(<GovernanceColumns tab="fields" schema={schema} rows={[{ "Field ID": cell("F001"), "Field name as in the source": cell("closing_balance") }, { "Field ID": cell("F009"), _hidden: true }]}
      governance={{ kpis: {}, fields: { F001: { personal: "Neither", sensitive: "No", who: "Everyone in the company with access to this module" } } }} />);
    const row = screen.getByText("closing_balance").closest("tr") as HTMLElement;
    expect(within(row).getByText("Neither")).toBeInTheDocument();
    expect(within(row).getByText(/Everyone in the company/)).toBeInTheDocument();
    expect(screen.getAllByRole("row")).toHaveLength(2); // a row the person may not see is not listed
  });
  it("is not drawn on the other tabs, or without governance", () => {
    const { container } = render(<GovernanceColumns tab="sources" schema={schema} rows={[]} governance={{ kpis: {}, fields: {} }} />);
    expect(container).toBeEmptyDOMElement();
  });
});
