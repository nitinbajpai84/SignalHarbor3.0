import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { copy } from "../../../copy";
import { SessionProvider } from "../../../useSession";
import type { Prov } from "../api";
import { m2Steps } from "../copy";
import { m2Tech as t } from "./copy";
import OwnerQuestions from "../requests/OwnerQuestions";
import OwnerTechnical from "../requests/OwnerTechnical";
import OpenQuestionsScreen from "./OpenQuestionsScreen";
import TechnicalColumns from "./TechnicalColumns";
import TechnicalSection from "./TechnicalSection";
import type { Ambiguity, TechKpi, TechnicalScreen, TechPart, TechPartView } from "./technicalApi";

// M2-E1: the technical definition section (under the business definition) and the baseline-level Open questions tab, in five states each.
// Family-office-free synthetic wording. fetch is stubbed.

const BID = "c".repeat(32);
const T = `/api/modules/m2_baseline/baselines/${BID}/technical`;
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const calls: { method: string; url: string; body: unknown }[] = [];

const p = (value: string | string[] | null, mark: Prov["mark"] = "stated", by = "Arjun Rao", from = "Technical notes"): Prov<string | string[]> => ({ value, mark, by, at: "2026-10-03T09:00:00+00:00", from });
const LABELS: Record<TechPart, string> = { sources: "Sources", tables: "Tables", fields: "Fields", calculation: "Calculation", filters: "Filters", grain: "Grain", period: "Period", currency_basis: "Currency basis", notes: "Notes" };
const part = (name: TechPart, cell: Prov<string | string[]>, over: Partial<TechPartView> = {}): TechPartView => ({ part: name, label: LABELS[name], cell, links: [], proposal: null, withheld: false, ...over });
const unknown = (from = "Missing: nothing says"): Prov<string | string[]> => ({ value: null, mark: "unknown", by: "Lens", at: "2026-10-03T09:00:00+00:00", from });

function parts(over: Partial<Record<TechPart, TechPartView>> = {}): TechPartView[] {
  const base: Record<TechPart, TechPartView> = {
    sources: part("sources", p(["S01"], "guessed", "Lens", "Technical notes, the catalogue"), { links: [{ id: "S01", name: "Custody daily file" }] }),
    tables: part("tables", unknown()),
    fields: part("fields", p(["F001"], "guessed", "Lens", "the catalogue"), { links: [{ id: "F001", name: "closing_balance" }] }),
    calculation: part("calculation", p("1. Take the month-end balance per account.\n2. Convert USD.", "guessed", "Lens", "Technical notes")),
    filters: part("filters", unknown()),
    grain: part("grain", unknown()),
    period: part("period", p("month end", "stated", "Sara Lim")),
    currency_basis: part("currency_basis", unknown("Missing: the FX rate source")),
    notes: part("notes", unknown()),
  };
  return Object.values({ ...base, ...over });
}
const kpi = (over: Partial<TechKpi> = {}): TechKpi => ({
  kpi_id: "K1", name: "Cash cushion", parts: parts(), confirmed: null, complete: true, missing: [], open: 1, ready: { ready: false, reasons: ["x"], label: "2 things open" }, ...over,
});
const amb = (over: Partial<Ambiguity> = {}): Ambiguity => ({
  id: "amb-1", kind: "currency", text: "The FX rate source is not stated.", question: "Which rate, from where, on which date?", where: "Cash cushion: currency basis", raised_by: "Lens",
  status: "open", resolution: null, by: null, at: "2026-10-03T09:00:00+00:00", kpi_id: "K1", kpi_name: "Cash cushion", owner: "Tom Ng", derived: false, ...over,
});
const screenOf = (over: Partial<TechnicalScreen> = {}): TechnicalScreen => ({
  baseline_id: BID, signed: false, lens_available: true, kpis: [kpi()], ambiguities: [amb()], counts: { all: 1, open: 1, settled: 0, accepted: 0 },
  summary: { measures: 1, drafted: 1, ready: 0, open: 1 }, ...over,
});

let roles = ["company_admin"];
function serve(get: () => Response | Promise<Response>, extra?: (url: string, method: string, body: unknown) => Response | undefined) {
  calls.length = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      calls.push({ method, url, body });
      if (url === "/api/auth/me") return json(200, { display_name: "Pat Owner", company_id: "co-a", roles });
      if (url === T && method === "GET") return get();
      return extra?.(url, method, body) ?? json(404, {});
    }),
  );
}
const wrap = (el: ReactElement, path = "/x") => (
  <MemoryRouter initialEntries={[path]}>
    <SessionProvider>
      <Routes>
        <Route path="/x" element={el} />
        <Route path="/modules/m2_baseline/questions/:baselineId" element={el} />
      </Routes>
    </SessionProvider>
  </MemoryRouter>
);
const section = (locked = false, governor = true) => render(wrap(<TechnicalSection baselineId={BID} kpiId="K1" locked={locked} governor={governor} />));
const tab = () => render(wrap(<OpenQuestionsScreen />, `/modules/m2_baseline/questions/${BID}`));
afterEach(() => {
  vi.unstubAllGlobals();
  roles = ["company_admin"];
});
const partRow = (label: string) => within(screen.getByRole("listitem", { name: label }));

describe("the technical definition section: five states", () => {
  it("loading", () => {
    serve(() => new Promise<Response>(() => undefined));
    section();
    expect(screen.getByRole("status")).toHaveTextContent(t.loading);
  });
  it("empty: says Lens has not drafted it and offers to", async () => {
    serve(() => json(200, screenOf({ kpis: [kpi({ parts: parts({ sources: part("sources", unknown()), fields: part("fields", unknown()), calculation: part("calculation", unknown()), period: part("period", unknown()) }) })], ambiguities: [] })));
    section();
    expect(await screen.findByText(t.empty)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: t.draft })).toBeEnabled();
  });
  it("error: plain words and a way to try again", async () => {
    serve(() => json(500, { error: "x" }));
    section();
    expect(await screen.findByRole("alert")).toHaveTextContent(t.loadFailed);
    expect(screen.getByRole("button", { name: copy.states.retry })).toBeInTheDocument();
  });
  it("refused: no access, nothing to act on", async () => {
    serve(() => json(403, { error: "forbidden", message: "x" }));
    section();
    expect(await screen.findByRole("alert")).toHaveTextContent(t.refused);
    expect(screen.queryByRole("button", { name: t.draft })).toBeNull();
  });
  it("populated: sources and fields as links, the calculation in steps, how sure and where from, unknown with what is missing", async () => {
    serve(() => json(200, screenOf()));
    section();
    expect(await screen.findByRole("heading", { name: t.title })).toBeInTheDocument();
    const src = partRow("Sources");
    expect(src.getByRole("link", { name: "Custody daily file" })).toHaveAttribute("href", `/modules/m2_baseline/catalogue/${BID}?tab=sources`);
    expect(src.getByText(t.marks.guessed)).toBeInTheDocument();
    expect(src.getByText(/from Technical notes, the catalogue/)).toBeInTheDocument();
    const steps = within(screen.getByRole("listitem", { name: "Calculation" })).getAllByRole("listitem");
    expect(steps.map((s) => s.textContent)).toEqual(["Take the month-end balance per account.", "Convert USD."]);
    expect(partRow("Currency basis").getByText(/Not available yet\. Missing: the FX rate source/)).toBeInTheDocument();
    expect(partRow("Period").getByText(t.marks.stated)).toBeInTheDocument();
    expect(screen.getByText("2 things open")).toBeInTheDocument();
    expect(screen.getByText(t.notConfirmed)).toBeInTheDocument();
  });
  it("a part limited to named people says so and shows nothing of it", async () => {
    serve(() => json(200, screenOf({ kpis: [kpi({ parts: parts({ calculation: part("calculation", unknown(), { withheld: true }) }) })] })));
    section();
    expect(await within(await screen.findByRole("listitem", { name: "Calculation" })).findByText(t.withheld)).toBeInTheDocument();
  });
});

describe("what a person does to a part", () => {
  it("Use this puts Lens's draft beside a person's value to work", async () => {
    const draft = part("period", p("last business day", "stated", "Sara Lim"), { proposal: p("month end", "guessed", "Lens", "Technical notes") });
    serve(() => json(200, screenOf({ kpis: [kpi({ parts: parts({ period: draft }) })] })), (url, method) => (url === `${T.replace("/technical", "")}/kpis/K1/technical/use` && method === "POST" ? json(200, screenOf()) : undefined));
    section();
    await screen.findByRole("listitem", { name: "Period" });
    const row = partRow("Period");
    expect(await row.findByText(t.suggestion)).toBeInTheDocument();
    await userEvent.setup().click(row.getByRole("button", { name: `${t.useThis}: Period` }));
    await waitFor(() => expect(calls.find((c) => c.url.endsWith("/technical/use"))?.body).toEqual({ part: "period" }));
  });
  it("Edit saves what the person wrote as stated, and a link part takes catalogue ids", async () => {
    serve(() => json(200, screenOf()), (url, method) => (method === "PUT" ? json(200, screenOf()) : undefined));
    section();
    const user = userEvent.setup();
    await screen.findByRole("heading", { name: t.title });
    await user.click(partRow("Grain").getByRole("button", { name: `${t.edit}: Grain` }));
    await user.type(within(screen.getByRole("listitem", { name: "Grain" })).getByRole("textbox", { name: `${t.edit}: Grain` }), "per account per month");
    await user.click(within(screen.getByRole("listitem", { name: "Grain" })).getByRole("button", { name: t.save }));
    await waitFor(() => expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ part: "grain", value: "per account per month", mark: "stated" }));
    await user.click(partRow("Tables").getByRole("button", { name: `${t.edit}: Tables` }));
    await user.type(within(screen.getByRole("listitem", { name: "Tables" })).getByRole("textbox", { name: `${t.edit}: Tables` }), "T01, T02");
    await user.click(within(screen.getByRole("listitem", { name: "Tables" })).getByRole("button", { name: t.save }));
    await waitFor(() => expect(calls.filter((c) => c.method === "PUT")[1]?.body).toEqual({ part: "tables", value: ["T01", "T02"], mark: "stated" }));
  });
  it("Tell Lens what to change sends the instruction with the part's name", async () => {
    serve(() => json(200, screenOf()), (url, method) => (url.endsWith("/lens/technical/redraft") && method === "POST" ? json(200, screenOf({ outcome: "redrafted" })) : undefined));
    section();
    const user = userEvent.setup();
    await screen.findByRole("heading", { name: t.title });
    await user.click(partRow("Filters").getByRole("button", { name: `${t.tell}: Filters` }));
    await user.type(within(screen.getByRole("listitem", { name: "Filters" })).getByRole("textbox"), "leave out paid calls");
    await user.click(within(screen.getByRole("listitem", { name: "Filters" })).getByRole("button", { name: t.tellSend }));
    await waitFor(() => expect(calls.find((c) => c.url.endsWith("/redraft"))?.body).toEqual({ kpi_id: "K1", instruction: "Filters: leave out paid calls" }));
  });
  it("the data owner confirms a complete definition; a refusal is shown in plain words", async () => {
    serve(() => json(200, screenOf()), (url, method) => (url.endsWith("/technical/confirm") && method === "POST" ? json(403, { error: "not_allowed", message: "Only the data owner named for this measure can confirm its technical definition." }) : undefined));
    section();
    await userEvent.setup().click(await screen.findByRole("button", { name: t.confirm }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Only the data owner");
  });
  it("a signed baseline: every action is off", async () => {
    serve(() => json(200, screenOf({ signed: true })));
    section(true);
    await screen.findByRole("heading", { name: t.title });
    for (const b of screen.getAllByRole("button", { name: new RegExp(`^(${t.edit}|${t.tell}|${t.answer}|${t.ask}|${t.accept})`) })) expect(b).toBeDisabled();
  });
});

describe("open questions in a measure", () => {
  it("lists them with the three ways to deal with each; Lens's proposed answer is a suggestion", async () => {
    serve(() => json(200, screenOf({ ambiguities: [amb({ suggestion: { value: "Use the custody rate at close.", mark: "guessed", by: "Lens" } })] })));
    section();
    const item = within(await screen.findByRole("listitem", { name: `${t.kind.currency}: Which rate, from where, on which date?` }));
    expect(item.getByText(/The FX rate source is not stated\./)).toBeInTheDocument();
    expect(item.getByText(/Suggestion from Lens: Use the custody rate at close\./)).toBeInTheDocument();
    for (const b of [t.answer, t.ask, t.accept]) expect(item.getByRole("button", { name: b })).toBeEnabled();
  });
  it("Answer settles it with the words written; a suggestion can be used but is never applied by itself", async () => {
    let now = screenOf({ ambiguities: [amb({ suggestion: { value: "Use the custody rate at close.", mark: "guessed", by: "Lens" } })] });
    serve(() => json(200, now), (url, method) => {
      if (!(url.endsWith("/ambiguities/amb-1/answer") && method === "POST")) return undefined;
      now = screenOf({ ambiguities: [amb({ status: "settled", resolution: "Use the custody rate at close.", by: "Pat Owner" })] });
      return json(200, now);
    });
    section();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: t.answer }));
    expect(screen.getByRole("textbox", { name: t.answerLabel })).toHaveValue("Use the custody rate at close."); // prefilled for the person to keep or change
    expect(calls.some((c) => c.method === "POST")).toBe(false);
    await user.click(screen.getByRole("button", { name: t.answerSave }));
    await waitFor(() => expect(calls.find((c) => c.url.endsWith("/answer"))?.body).toEqual({ resolution: "Use the custody rate at close." }));
    expect(await screen.findByText(t.status.settled)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.answer })).toBeNull(); // dealt with: no more actions
  });
  it("asks which part the answer changes, preselects the question's own part and pre-fills the current text; nothing changes by default", async () => {
    let now = screenOf({ kpis: [kpi({ definition: "Cash we would still have in the worst month." })], ambiguities: [amb({ kind: "period", suggested_part: "period" })] });
    serve(() => json(200, now), (url, method) => {
      if (!(url.endsWith("/ambiguities/amb-1/answer") && method === "POST")) return undefined;
      now = screenOf({ ambiguities: [amb({ status: "settled", resolution: "Last business day.", by: "Pat Owner" })] });
      return json(200, now);
    });
    section();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: t.answer }));
    const which = screen.getByRole("combobox", { name: t.whichPart }) as HTMLSelectElement;
    expect(which.value).toBe("period"); // preselected
    expect(within(which).getByRole("option", { name: t.justRecord })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: t.wordingLabel })).toHaveValue("month end"); // the current text, to edit
    await user.type(screen.getByRole("textbox", { name: t.answerLabel }), "Last business day.");
    await user.clear(screen.getByRole("textbox", { name: t.wordingLabel }));
    expect(screen.getByRole("button", { name: t.answerSave })).toBeDisabled(); // a part needs its wording
    await user.type(screen.getByRole("textbox", { name: t.wordingLabel }), "last business day of the month");
    await user.click(screen.getByRole("button", { name: t.answerSave }));
    await waitFor(() => expect(calls.find((c) => c.url.endsWith("/answer"))?.body).toEqual({ resolution: "Last business day.", part: "period", wording: "last business day of the month" }));
  });
  it("'Just record the answer' sends the answer alone", async () => {
    serve(() => json(200, screenOf({ ambiguities: [amb({ suggested_part: "currency_basis" })] })), (url, method) =>
      url.endsWith("/answer") && method === "POST" ? json(200, screenOf({ ambiguities: [amb({ status: "settled", resolution: "x", by: "Pat" })] })) : undefined);
    section();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: t.answer }));
    await user.selectOptions(screen.getByRole("combobox", { name: t.whichPart }), t.justRecord);
    expect(screen.queryByRole("textbox", { name: t.wordingLabel })).toBeNull();
    await user.type(screen.getByRole("textbox", { name: t.answerLabel }), "Custody rate.");
    await user.click(screen.getByRole("button", { name: t.answerSave }));
    await waitFor(() => expect(calls.find((c) => c.url.endsWith("/answer"))?.body).toEqual({ resolution: "Custody rate." }));
  });
  it("an item the code closed says so", async () => {
    serve(() => json(200, screenOf({ ambiguities: [amb({ status: "settled", resolution: "Closed: the catalogue now has it", by: "Lens", auto: true })] })));
    section();
    expect(await screen.findByText(/Closed: the catalogue now has it/)).toBeInTheDocument();
    expect(screen.getByText(t.closedAuto)).toBeInTheDocument();
  });
  it("Ask the owner adds it to that owner's request and shows the words to copy", async () => {
    serve(() => json(200, screenOf()), (url, method) =>
      url.endsWith("/ask") && method === "POST" ? json(200, screenOf({ asked: { owner: "Tom Ng", email: { subject: "s", body: "Hello Tom,\n- Which rate, from where, on which date?" }, link_path: null } })) : undefined);
    section();
    await userEvent.setup().click(await screen.findByRole("button", { name: t.ask }));
    expect(await screen.findByRole("status")).toHaveTextContent("Added to Tom Ng's request.");
    expect(screen.getByText(/Hello Tom/)).toBeInTheDocument();
  });
  it("Accept as a known risk needs a reason and is offered only to the organiser or sponsor", async () => {
    serve(() => json(200, screenOf()), (url, method) => (url.endsWith("/accept") && method === "POST" ? json(200, screenOf({ ambiguities: [amb({ status: "accepted", resolution: "After the audit.", by: "Pat Owner" })] })) : undefined));
    section(false, true);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: t.accept }));
    expect(screen.getByRole("button", { name: t.acceptSave })).toBeDisabled();
    await user.type(screen.getByRole("textbox", { name: t.reasonLabel }), "After the audit.");
    await user.click(screen.getByRole("button", { name: t.acceptSave }));
    await waitFor(() => expect(calls.find((c) => c.url.endsWith("/accept"))?.body).toEqual({ reason: "After the audit." }));
  });
  it("an analyst is not offered Accept", async () => {
    serve(() => json(200, screenOf()));
    section(false, false);
    await screen.findByRole("button", { name: t.answer });
    expect(screen.queryByRole("button", { name: t.accept })).toBeNull();
  });
  it("a governance question is decided in the governance view, with no actions here", async () => {
    serve(() => json(200, screenOf({ ambiguities: [amb({ id: "gov-1", kind: "governance", derived: true, question: "Who may see it?" })] })));
    section();
    expect(await screen.findByText(t.decideInGovernance)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.answer })).toBeNull();
  });
});

describe("the Open questions tab: five states", () => {
  const two = [amb(), amb({ id: "amb-2", kind: "period", question: "Which date is the reporting date?", status: "settled", resolution: "Month end.", by: "Sara Lim", owner: "Sara Lim", kpi_id: "K2", kpi_name: "Known obligations" }),
    amb({ id: "amb-3", kind: "threshold", question: "What is the number?", status: "accepted", resolution: "After the audit.", by: "Pat Owner", owner: "Sara Lim", kpi_id: "K3", kpi_name: "Old valuations" })];
  const full = () => screenOf({ ambiguities: two, counts: { all: 3, open: 1, settled: 1, accepted: 1 } });
  it("loading", () => {
    serve(() => new Promise<Response>(() => undefined));
    tab();
    expect(screen.getByRole("status")).toHaveTextContent(copy.states.loading);
  });
  it("empty", async () => {
    serve(() => json(200, screenOf({ ambiguities: [], counts: { all: 0, open: 0, settled: 0, accepted: 0 } })));
    tab();
    expect(await screen.findByText(t.tab.empty)).toBeInTheDocument();
  });
  it("error", async () => {
    serve(() => json(500, { error: "x" }));
    tab();
    expect(await screen.findByRole("alert")).toHaveTextContent(copy.states.error);
    expect(screen.getByRole("button", { name: copy.states.retry })).toBeInTheDocument();
  });
  it("refused", async () => {
    serve(() => json(403, { error: "module_not_available", message: "x" }));
    tab();
    expect(await screen.findByRole("alert")).toHaveTextContent(t.refused);
  });
  it("populated: the open ones first, the step in the tabs, filters by status, kind and owner", async () => {
    serve(() => json(200, full()));
    tab();
    const user = userEvent.setup();
    expect(await screen.findByRole("heading", { name: t.tab.counts(1, 1, 1) })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: m2Steps.questions }).className).toContain("active");
    expect(screen.getByRole("button", { name: `${t.status.open} (1)` })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getAllByRole("listitem", { name: /Which rate/ })).toHaveLength(1);
    expect(screen.queryByText("Which date is the reporting date?")).toBeNull();
    await user.click(screen.getByRole("button", { name: `${t.tab.all} (3)` }));
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
    await user.click(screen.getByRole("button", { name: `${t.status.settled} (1)` }));
    expect(screen.getByText("Which date is the reporting date?")).toBeInTheDocument();
    expect(screen.getByText("Known obligations")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: `${t.tab.all} (3)` }));
    await user.selectOptions(screen.getByRole("combobox", { name: t.tab.kindFilter }), "threshold");
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    await user.selectOptions(screen.getByRole("combobox", { name: t.tab.kindFilter }), "all");
    await user.selectOptions(screen.getByRole("combobox", { name: t.tab.ownerFilter }), "Sara Lim");
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    await user.click(screen.getByRole("button", { name: `${t.status.open} (1)` }));
    expect(screen.getByText(t.tab.none)).toBeInTheDocument();
  });
});

describe("the catalogue shows the calculation and the inputs", () => {
  const schema = { id_header: "KPI ID", status_header: "Ready for module 3?", columns: [], title: "", sheet: "", blurb: "" } as never;
  const cell = (v: string) => ({ value: v, mark: "stated" as const, by: "x", at: "", from: "" });
  it("the KPIs tab lists each measure's calculation and sources; the Fields tab says which measures use each field", () => {
    const technical = { kpis: { K1: { calculation: "1. Take closing_balance.", sources: "Custody daily file", tables: "statement", fields: "closing_balance", filters: "", grain: "per account", period: "month end", currency_basis: "", notes: "", confirmed: "Pat Owner, 2026-10-03" } }, inputs: { F001: ["Cash cushion"] } };
    const { rerender } = render(<TechnicalColumns tab="kpis" schema={schema} rows={[{ "KPI ID": cell("K1"), "KPI name": cell("Cash cushion") }]} technical={technical} />);
    const row = within(screen.getByRole("row", { name: /Cash cushion/ }));
    expect(row.getByText("1. Take closing_balance.")).toBeInTheDocument();
    expect(row.getByText("Custody daily file")).toBeInTheDocument();
    expect(row.getByText("Pat Owner, 2026-10-03")).toBeInTheDocument();
    rerender(<TechnicalColumns tab="fields" schema={{ ...(schema as object), id_header: "Field ID" } as never} rows={[{ "Field ID": cell("F001"), "Field name as in the source": cell("closing_balance") }, { "Field ID": cell("F002"), "Field name as in the source": cell("notes") }]} technical={technical} />);
    expect(within(screen.getByRole("row", { name: /closing_balance/ })).getByText("Cash cushion")).toBeInTheDocument();
    expect(within(screen.getByRole("row", { name: /notes/ })).getByText(t.cat.notUsed)).toBeInTheDocument();
  });
  it("shows nothing when the server sent nothing", () => {
    const { container } = render(<TechnicalColumns tab="kpis" schema={schema} rows={[{ "KPI ID": cell("K1") }]} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("a re-opened question and the owner's answer page", () => {
  it("a re-opened question says why, visibly, and keeps what it was", async () => {
    serve(() => json(200, screenOf({ ambiguities: [amb({ reopened: "Re-opened: the period was changed by Sara Lim after this was settled", history: [{ status: "settled", resolution: "Month end.", by: "Pat Owner", at: "2026-10-03T09:00:00+00:00" }] })] })));
    section();
    expect(await screen.findByText(/Re-opened: the period was changed by Sara Lim/)).toBeInTheDocument();
    expect(screen.getByText(/before: Month end\./)).toBeInTheDocument();
  });
  it("the owner reads the question worded for them and replies; the reply is sent with the link's token and the question goes", async () => {
    serve(() => json(404, {}), (url, method) => (url.endsWith("/answer/question") && method === "POST" ? json(200, { questions: [] }) : undefined));
    render(<OwnerQuestions token="ow-x-y" locked={false} questions={[{ ambiguity_id: "amb-1", kpi_id: "K1", kpi_name: "Cash cushion", text: "A question about Cash cushion needs your answer." }]} />);
    const user = userEvent.setup();
    expect(screen.getByText("A question about Cash cushion needs your answer.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send this answer" })).toBeDisabled();
    await user.type(screen.getByRole("textbox"), "Custody rate at close.");
    await user.click(screen.getByRole("button", { name: "Send this answer" }));
    await waitFor(() => expect(calls.find((c) => c.url.endsWith("/answer/question"))?.body).toEqual({ kpi_id: "K1", ambiguity_id: "amb-1", resolution: "Custody rate at close." }));
    expect(await screen.findByText("Thank you. That question is settled.")).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).toBeNull();
  });
  it("shows nothing when no question was put to this owner", () => {
    const { container } = render(<OwnerQuestions token="t" locked={false} questions={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
  it("an owner with an account sees the question read-only and a way to sign in; there is nothing to type", () => {
    serve(() => json(404, {}));
    render(<OwnerQuestions token="t" locked={false} questions={[{ ambiguity_id: "amb-1", kpi_id: "K1", kpi_name: "Cash cushion", text: "Which rate?", needs_sign_in: true }]} />);
    expect(screen.getByText("Which rate?")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign in to answer" }).getAttribute("href")).toMatch(/^\/login\?next=/);
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.queryByRole("button", { name: "Send this answer" })).toBeNull();
  });
});

describe("the owner's technical definitions (answer link and signed in)", () => {
  it("shows only their own measure, confirms it and shows who confirmed; an owner with an account is told to sign in", async () => {
    serve(() => json(404, {}));
    const done = kpi({ confirmed: { by: "Arjun Rao", at: "2026-10-04T09:00:00+00:00" } });
    const user = userEvent.setup();
    render(<OwnerTechnical technical={[kpi()]} signIn={[{ kpi_id: "K2", name: "Old valuations" }]} signInPath="/modules/m2_baseline/signoff/x" locked={false} onConfirm={async () => [done]} />);
    expect(screen.getByRole("heading", { name: "Cash cushion" })).toBeInTheDocument();
    expect(screen.getByText("closing_balance")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign in" }).getAttribute("href")).toMatch(/^\/login\?next=/);
    await user.click(screen.getByRole("button", { name: "Confirm this technical definition: Cash cushion" }));
    expect(await screen.findByText("Confirmed by Arjun Rao.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Confirm this technical definition/ })).toBeNull();
  });
  it("renders nothing for someone who owns nothing", () => {
    const { container } = render(<OwnerTechnical technical={[]} locked={false} onConfirm={async () => []} />);
    expect(container).toBeEmptyDOMElement();
  });
});
