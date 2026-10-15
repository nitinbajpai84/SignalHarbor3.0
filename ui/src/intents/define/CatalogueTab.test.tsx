import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { copy } from "../../copy";
import { SessionProvider } from "../../useSession";
import type { CatalogueList, Cell, Entry, Field, Governed, GovernedRow } from "./catalogueApi";
import { catalogueCopy as t, governedCopy as g } from "./catalogueCopy";
import { CatalogueTab } from "./CatalogueTab";
import { GovernedPanel } from "./GovernedPanel";

// B17: the Catalogue tab and the Governed panel in five states each; synthetic family-office wording; fetch is stubbed.
const BID = "e".repeat(32);
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const calls: { method: string; url: string; body: unknown }[] = [];
let roles = ["company_admin"];

const list = (over: Partial<CatalogueList> = {}): CatalogueList => ({
  baseline_id: BID, signed: false, empty: null, not_drafted: 1, guessed_parts: 2, lens_line: "I guessed 2 parts across 1 measures. Harvey Rowley, please check them.",
  counts: { confirmed: 1, draft: 0, not_drafted: 1, unknown_accepted: 0, changed: 0 }, blockers: [], waiting: [{ person: "Harvey Rowley", codes: ["K01"] }],
  measures: [
    { code: "K01", label: "Total AUM", aliases: ["Assets"], owner: "Harvey Rowley", state: "confirmed", state_label: "Confirmed", guessed: 0, priority: "must" },
    { code: "K02", label: "Fee income", aliases: [], owner: null, state: "not_drafted", state_label: "Not drafted", guessed: 2, priority: "should" },
    { restricted: true, label: "A restricted measure" },
  ], ...over,
});
const entry = (over: Partial<Entry> = {}): Entry => ({
  code: "K01", label: "Total AUM", aliases: ["Assets"], node: "measure:K01", state: "confirmed", state_label: "Confirmed", version: 2, business_definition: "Everything we hold for clients.",
  owners: { business: "Grace Ward", data: "Harvey Rowley", source: null, confirmed: false }, sources: [{ id: "S01", name: "Custody statements", owner: "Harvey Rowley" }],
  fields: [{ id: "F1", name: "closing_balance", class: null }], personal_class: null, may_see: null, accepted: null, sent_back: null, complete: true, missing: [], can_confirm: false, priority: "must",
  trail: [{ v: 1, at: "2026-10-03", text: "Lens drafted Sources" }, { v: 2, at: "2026-10-04", text: "Harvey Rowley confirmed" }], ...over,
});
const cell = (value: unknown, mark: Cell["mark"] = "stated", by = "Grace Ward", from = "confirmed in Define"): Cell => ({ value, mark, by, from, at: "2026-10-03T10:00:00+00:00" });
const unknownCell = (): Cell => cell(null, "unknown", "Lens", "not drafted yet");
function row(over: Partial<GovernedRow> = {}, cells: Partial<Record<Field, Cell>> = {}, can: Partial<Record<Field, boolean>> = {}): GovernedRow {
  return {
    id: "K01", name: "Total AUM", priority: "must", complete: false, n: 1, needs: ["classification", "who may see"], proposals: {}, owners: { business: "Grace Ward", data: "Harvey Rowley", source: null, confirmed: true },
    state: { owners: cell({ business: "Grace Ward", data: "Harvey Rowley", process: null }), classification: unknownCell(), may_see: cell([], "guessed", "Lens", "the work list"), resolving: unknownCell(), affects: unknownCell(), review_date: cell("2027-01-04", "guessed", "Lens", "default"), ...cells },
    slots: { business: false, data: true, source: false },
    can_confirm: { owners: true, classification: false, may_see: false, resolving: false, affects: true, review_date: true, ...can }, ...over,
  };
}
const governed = (over: Partial<Governed> = {}): Governed => ({
  baseline_id: BID, measures: [row()], strip: { owned: { n: 1, of: 3, pct: 33 }, classified: { n: 0, of: 3, pct: 0 }, may_see_confirmed: { n: 0, of: 3, pct: 0 }, team_assigned: { n: 0, of: 3, pct: 0 } },
  empty: null, must: { n: 0, of: 2 }, should: { n: 0, of: 1 }, not_governed: [{ id: "K01", name: "Total AUM", needs: ["classification", "who may see"] }], waiting_on: ["Harvey Rowley"],
  refusal: "Only the person named for this part can confirm it. Ask them, or ask the sponsor to name them.", ...over,
});

function serve(routes: Record<string, () => Response | Promise<Response>>) {
  calls.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    if (url === "/api/auth/me") return json(200, { display_name: "Pat Owner", company_id: "ardmore", roles });
    const hit = routes[`${method} ${url}`];
    return hit ? hit() : json(404, {});
  }));
}
const wrap = (el: ReactElement) => <MemoryRouter><SessionProvider>{el}</SessionProvider></MemoryRouter>;
afterEach(() => { vi.unstubAllGlobals(); roles = ["company_admin"]; });

describe("the Catalogue tab: five states", () => {
  const LIST = "GET /api/intents/i1/catalogue";
  it("loading", () => {
    serve({ [LIST]: () => new Promise<Response>(() => undefined) });
    render(wrap(<CatalogueTab intentId="i1" />));
    expect(screen.getByRole("status")).toHaveTextContent(t.loading);
  });
  it("empty: names where measures come from", async () => {
    serve({ [LIST]: () => json(200, list({ measures: [], counts: null, empty: "No measures yet. Measures come from the wall clusters in Define. Open Clusters." })) });
    render(wrap(<CatalogueTab intentId="i1" />));
    expect(await screen.findByText(/No measures yet\. Measures come from the wall clusters/)).toBeInTheDocument();
  });
  it("error and refused say what to do", async () => {
    serve({ [LIST]: () => json(500, {}) });
    const first = render(wrap(<CatalogueTab intentId="i1" />));
    expect(await screen.findByRole("alert")).toHaveTextContent(t.failed);
    expect(screen.getByRole("button", { name: copy.states.retry })).toBeInTheDocument();
    first.unmount();
    serve({ [LIST]: () => json(403, { error: "forbidden", message: "You do not have access to this catalogue." }) });
    render(wrap(<CatalogueTab intentId="i1" />));
    expect(await screen.findByRole("alert")).toHaveTextContent("You do not have access");
  });
  it("populated: counts, the list, a restricted row without a code, and a filter", async () => {
    serve({ [LIST]: () => json(200, list()) });
    render(wrap(<CatalogueTab intentId="i1" />));
    expect(await screen.findByText("Total AUM")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: `${t.counts.confirmed} 1` })).toBeInTheDocument();
    expect(screen.getByText(t.restricted)).toBeInTheDocument();
    expect(screen.getByText(`${t.owner}: ${t.notNamed}`)).toBeInTheDocument();
    expect(screen.getByText(t.guessed(2))).toBeInTheDocument();
    expect(screen.getByRole("button", { name: t.draftWithLens })).toBeEnabled();
    await userEvent.click(screen.getByRole("button", { name: `${t.counts.not_drafted} 1` }));
    expect(screen.queryByText("Total AUM")).not.toBeInTheDocument();
    expect(screen.getByText("Fee income")).toBeInTheDocument();
    await userEvent.type(screen.getByRole("searchbox", { name: t.search }), "zzz");
    expect(screen.getByText(t.noMatch)).toBeInTheDocument();
  });
  it("Draft with Lens is for the organiser and analyst only", async () => {
    roles = ["participant"];
    serve({ [LIST]: () => json(200, list()) });
    render(wrap(<CatalogueTab intentId="i1" />));
    await screen.findByText("Total AUM");
    expect(screen.queryByRole("button", { name: t.draftWithLens })).not.toBeInTheDocument();
  });
  it("opens an entry: business definition, owners with Not named, the version trail", async () => {
    serve({
      [LIST]: () => json(200, list()),
      "GET /api/intents/i1/catalogue/entry/K01": () => json(200, entry()),
      [`GET /api/modules/m2_baseline/baselines/${BID}/technical`]: () => json(200, { baseline_id: BID, signed: false, lens_available: true, kpis: [], ambiguities: [], counts: {}, summary: {} }),
      "GET /api/intents/i1/governed": () => json(200, governed()),
    });
    render(wrap(<CatalogueTab intentId="i1" />));
    await userEvent.click(await screen.findByRole("button", { name: /K01 Total AUM/ }));
    expect(await screen.findByText("Everything we hold for clients.")).toBeInTheDocument();
    expect(screen.getByText(`${t.source}:`, { exact: false })).toBeInTheDocument();
    expect(screen.getAllByText(t.notNamed).length).toBeGreaterThan(0);
    expect(screen.getByText("v2, 2026-10-04, Harvey Rowley confirmed")).toBeInTheDocument();
  });
});

describe("the Governed panel", () => {
  const GOV = "GET /api/intents/i1/governed";
  it("empty reads Not available yet, not 0%", async () => {
    serve({ [GOV]: () => json(200, governed({ measures: [], strip: null, empty: "Governed: Not available yet. No measures have been named in this Initiative." })) });
    render(wrap(<GovernedPanel intentId="i1" />));
    expect(await screen.findByText(/Governed: Not available yet/)).toBeInTheDocument();
  });
  it("populated: four traced bars, Must line, owners to confirm, and the refusal copy", async () => {
    serve({ [GOV]: () => json(200, governed()) });
    render(wrap(<GovernedPanel intentId="i1" />));
    expect(await screen.findByText(`${g.strip.owned}: ${g.of(1, 3)}, 33%`)).toBeInTheDocument();
    expect(screen.getByText(g.must(0, 2))).toBeInTheDocument();
    expect(screen.getByText(g.ownerNotConfirmed("Harvey Rowley"))).toBeInTheDocument();
    expect(screen.getByText(/Only the person named for this part/)).toBeInTheDocument();
  });
  it("a named person confirms through module 2's route with the right value", async () => {
    serve({
      [GOV]: () => json(200, governed()),
      [`POST /api/modules/m2_baseline/baselines/${BID}/governed/K01/confirm`]: () => json(200, {}),
    });
    render(wrap(<GovernedPanel intentId="i1" measureId="K01" />));
    const ring = within(await screen.findByRole("listitem", { name: g.fields.review_date }));
    await userEvent.click(ring.getByRole("button", { name: g.confirmButton.review_date }));
    await userEvent.click(ring.getByRole("button", { name: g.save }));
    const post = calls.find((c) => c.method === "POST");
    expect(post?.body).toEqual({ field: "review_date", value: "2027-01-04" });
  });
  it("owners are confirmed one slot at a time: the business slot is refused to the data owner", async () => {
    serve({ [GOV]: () => json(200, governed()), [`POST /api/modules/m2_baseline/baselines/${BID}/governed/K01/confirm`]: () => json(200, {}) });
    render(wrap(<GovernedPanel intentId="i1" measureId="K01" />));
    const own = within(await screen.findByRole("listitem", { name: g.fields.owners }));
    expect(own.queryByRole("button", { name: g.confirmButton.owners })).not.toBeInTheDocument();
    const biz = own.getByRole("button", { name: g.confirmSlot.business });
    expect(biz).toBeDisabled();
    expect(biz).toHaveAttribute("title", expect.stringMatching(/Only the person named for this part/));
    expect(calls.some((c) => c.method === "POST")).toBe(false);
    await userEvent.click(own.getByRole("button", { name: g.confirmSlot.data }));
    expect(own.queryByRole("textbox", { name: g.business })).not.toBeInTheDocument();
    await userEvent.click(own.getByRole("button", { name: g.save }));
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ field: "owners", value: { business: "Grace Ward", data: "Harvey Rowley", process: null } });
  });
  it("Ask Lens to draft again is for the organiser and analyst, and says how many parts were drafted", async () => {
    serve({ [GOV]: () => json(200, governed()), "GET /api/intents/i1/governed?redraft=K01": () => json(200, governed({ redrafted: { id: "K01", n: 3 } })) });
    render(wrap(<GovernedPanel intentId="i1" measureId="K01" roles={["company_admin"]} />));
    await userEvent.click(await screen.findByRole("button", { name: g.redraft }));
    expect(await screen.findByText(g.redrafted(3))).toBeInTheDocument();
  });
  it("Ask Lens to draft again is disabled for others, with the reason", async () => {
    serve({ [GOV]: () => json(200, governed()) });
    render(wrap(<GovernedPanel intentId="i1" measureId="K01" roles={["participant"]} />));
    await screen.findByRole("listitem", { name: g.fields.owners });
    expect(screen.getByRole("button", { name: g.redraft })).toBeDisabled();
    expect(screen.getByText(g.redraftOnly)).toBeInTheDocument();
  });
  it("someone not named sees the refusal line and nothing is written", async () => {
    serve({ [GOV]: () => json(200, governed()) });
    render(wrap(<GovernedPanel intentId="i1" measureId="K01" />));
    const cls = within(await screen.findByRole("listitem", { name: g.fields.classification }));
    expect(cls.getByRole("button", { name: g.confirmButton.classification })).toBeDisabled();
    expect(cls.getByText(/Only the person named for this part/)).toBeInTheDocument();
    expect(calls.some((c) => c.method === "POST")).toBe(false);
  });
  it("a stated cell offers a proposal with a reason; a waiting proposal can be applied by the named person", async () => {
    serve({
      [GOV]: () => json(200, governed({ measures: [row({ proposals: { classification: { value: "personal", reason: "It holds names", by: "Janet Shaw", at: "2026-10-05" } } },
        { classification: cell("open") }, { classification: true })] })),
      "POST /api/intents/i1/governed/K01/proposal/classification/decide": () => json(200, {}),
    });
    render(wrap(<GovernedPanel intentId="i1" measureId="K01" />));
    const cls = within(await screen.findByRole("listitem", { name: g.fields.classification }));
    expect(cls.getByText(/Janet Shaw proposed a change to classification: It holds names/)).toBeInTheDocument();
    await userEvent.click(cls.getByRole("button", { name: g.apply }));
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ decision: "apply", reason: undefined });
  });
  it("Propose a change needs a reason before it can be sent", async () => {
    serve({ [GOV]: () => json(200, governed({ measures: [row({}, { classification: cell("open") })] })), "POST /api/intents/i1/governed/K01/propose": () => json(200, {}) });
    render(wrap(<GovernedPanel intentId="i1" measureId="K01" />));
    const cls = within(await screen.findByRole("listitem", { name: g.fields.classification }));
    await userEvent.click(cls.getByRole("button", { name: g.proposeLink }));
    expect(cls.getByRole("button", { name: g.send })).toBeDisabled();
    await userEvent.type(cls.getByRole("textbox", { name: g.reason }), "It holds names");
    await userEvent.selectOptions(cls.getByRole("combobox", { name: g.fields.classification }), "personal");
    await userEvent.click(cls.getByRole("button", { name: g.send }));
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ field: "classification", value: "personal", reason: "It holds names" });
  });
});
