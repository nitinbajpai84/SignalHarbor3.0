import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import App from "../../../App";
import { setSessionExpiredHandler } from "../../../api/client";
import type { BaselineList, KpiFull, LensState, Prov, WorkList } from "../api";
import { m2Lens, m2Pre, m2Work } from "../copy";

// M2-P01 screens: the start page, the work list, triage, owners, governance. fetch is stubbed.

const BASE = "/api/modules/m2_baseline";
const BID = "a".repeat(32);
const prov = (value: string | null, mark: Prov["mark"] = "unknown", by = "Lens", from = ""): Prov => ({ value, mark, by, from, at: "2026-10-03T10:00:00+00:00" });
const noOwner = prov(null);

const kpi = (over: Partial<KpiFull> = {}): KpiFull => {
  const definition = over.definition ?? prov("Capital calls still to be paid, by due date", "guessed", "the pack", "Lakeside industry pack (suggestion)");
  const owners = over.owners ?? { business: noOwner, data: noOwner, process: noOwner };
  const producer = over.producer ?? noOwner;
  const gathered = over.gathered ?? prov("emails", "guessed", "Pat");
  return {
    id: "K1", name: "Capital calls due, by date", restricted: false, state: "drafted", problem_ids: ["p1"], priority: "must", definition, owners,
    governance: { personal: "not_sure", sensitive: false, may_see: [] }, tracking: noOwner, producer, gathered, questions: [], definition_proposal: null,
    triage: { definition, owner: noOwner, producer, gathered, unknown: ["owner", "producer"] }, missing_owners: ["business", "data", "process"],
    treated_as_personal: true, ...over,
  };
};
const worklist = (over: Partial<WorkList> = {}): WorkList => ({
  baseline: { id: BID, charter_outcome_id: "b".repeat(32), state: "draft", created_at: "2026-10-03T10:00:00+00:00" },
  charter: { outcome_id: "b".repeat(32), signed_at: "2026-10-01T10:00:00+00:00" },
  problems: [{ id: "p1", title: "Calls arrive too late", priority: "must", kpi_ids: [], has_kpi: false },
    { id: "p2", title: "Nobody trusts the numbers", priority: "should", kpi_ids: [], has_kpi: false }],
  kpis: [], suggestions: [{ id: "K1", name: "Capital calls due, by date", problem_ids: ["p1"], priority: "must" }],
  suggestion_label: "What others in the industry usually track (a suggestion, not your company's own definition)",
  pack: { available: true, label: "Family office" }, owners_complete: 0, lens_available: false, ...over,
});

interface World {
  list?: BaselineList;
  listStatus?: number;
  listBody?: unknown;
  hold?: boolean;
  wl?: WorkList;
  wlStatus?: number;
  after?: WorkList; // what every change answers with
  lens?: LensState;
}
const lensState = (over: Partial<LensState> = {}): LensState => ({
  available: true, locked: false, pack: { available: true, label: "Family office" }, pending: [], failed: [], drafting: [], documents: 0, people: [], refine: [], asks: [],
  say: { did: "I looked at your 2 charter problems.", next: "Use a definition, edit it, or tell me what to change.", need: "Nothing right now." }, ...over,
});
const calls: { method: string; url: string; body: unknown }[] = [];
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function mock(w: World) {
  calls.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    if (url === "/api/auth/me") return json(200, { display_name: "Pat Owner", company_id: "co-a", roles: ["company_admin"] });
    if (url === "/api/company") return json(200, { company_id: "co-a", name: "Harbor Test Co", industry: "family_office" });
    if (url === "/api/modules") return json(200, [{ id: "m2_baseline", number: 2, name: "Baseline", description: "d", agent: "Lens" }]);
    if (url === `${BASE}/baselines` && method === "GET") {
      if (w.hold) return new Promise<Response>(() => undefined);
      return w.listStatus ? json(w.listStatus, w.listBody ?? {}) : json(200, w.list ?? { charters: [], baselines: [] });
    }
    if (url === `${BASE}/baselines` && method === "POST") return json(201, w.wl ?? worklist());
    if (url === `${BASE}/baselines/${BID}` && method === "GET") return w.wlStatus ? json(w.wlStatus, { error: "x", message: "m" }) : json(200, w.wl ?? worklist());
    if (url === `${BASE}/baselines/${BID}/preread` && method === "GET") return json(200, { kinds: [], documents: [], can_upload: true, pack: { available: true, label: "Family office" } });
    if (url === `${BASE}/baselines/${BID}/lens` && method === "GET") return json(200, w.lens ?? lensState());
    if (url === `${BASE}/baselines/${BID}/nira`) return json(200, { name: "Nira", role: "the guide", available: true, text: "You are on step 1 of 5, the work list." });
    if (url.startsWith(`${BASE}/baselines/${BID}/`)) return json(200, w.after ?? w.wl ?? worklist());
    return json(404, {});
  }));
}
const open = (path = "/modules/m2_baseline") => render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
const work = `/modules/m2_baseline/baselines/${BID}`;
const sent = (method: string, tail: string) => calls.filter((c) => c.method === method && c.url === `${BASE}/baselines/${BID}${tail}`);
const body = (method: string, tail: string, i = 0) => sent(method, tail)[i]?.body;

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  sessionStorage.clear();
  setSessionExpiredHandler(null);
});

describe("start page: five states", () => {
  test("loading", async () => {
    mock({ hold: true });
    open();
    expect(await screen.findByRole("heading", { name: "Baseline" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Loading");
  });

  test("empty company: honest words, and a way to start with nothing", async () => {
    mock({});
    open();
    expect(await screen.findByText(m2Work.noBaselines)).toBeInTheDocument();
    expect(screen.getByText(m2Work.noCharters)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: m2Work.startEmpty })).toBeInTheDocument();
    expect(screen.queryByText("Illustrative")).not.toBeInTheDocument();
  });

  test("populated: a signed charter starts a baseline and opens its work list", async () => {
    mock({ list: { charters: [{ outcome_id: "b".repeat(32), signed_at: "2026-10-01T10:00:00+00:00", problem_count: 2, baseline_id: null }],
      baselines: [{ id: "c".repeat(32), charter_outcome_id: null, state: "draft", created_at: "2026-10-02T10:00:00+00:00", kpi_count: 3 }] } });
    const user = userEvent.setup();
    open();
    expect(await screen.findByText("3 measures", { exact: false })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: m2Work.openBaseline })).toHaveAttribute("href", `/modules/m2_baseline/baselines/${"c".repeat(32)}`);
    await user.click(screen.getByRole("button", { name: m2Work.startFromCharter }));
    await user.click(await screen.findByRole("button", { name: m2Pre.start })); // first, "Give Lens what you already have"
    expect(await screen.findByRole("heading", { name: m2Work.title })).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST" && c.url === `${BASE}/baselines`)?.body).toEqual({ charter_outcome_id: "b".repeat(32) });
  });

  test("error: one sentence and a way to try again", async () => {
    mock({ listStatus: 500, listBody: { detail: "boom" } });
    const user = userEvent.setup();
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong. Try again in a moment.");
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(calls.filter((c) => c.url === `${BASE}/baselines`).length).toBeGreaterThan(1);
  });

  test("refused: a role without access gets plain words, not a role code", async () => {
    mock({ listStatus: 403, listBody: { error: "forbidden", message: "x" } });
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent("You do not have access to this. Ask your administrator.");
  });
});

describe("work list", () => {
  test("a problem with no measure says so; Lens's suggestion is labelled and is not a measure until confirmed", async () => {
    mock({});
    const user = userEvent.setup();
    open(work);
    expect((await screen.findAllByText("Calls arrive too late")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(m2Work.noMeasureYet)).toHaveLength(2);
    expect(screen.getByText(/What others in the industry usually track/)).toBeInTheDocument();
    expect(screen.getByText(m2Work.suggestionTag)).toBeInTheDocument();
    expect(screen.getByText(m2Work.emptyList)).toBeInTheDocument(); // no measure until a person confirms
    expect(screen.getByText(m2Work.lensNoModel)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: `${m2Work.confirm}: Capital calls due, by date` }));
    expect(body("POST", "/kpis", 0)).toEqual({ suggestion_id: "K1", problem_ids: ["p1"] });
  });

  test("when Lens's model call was refused, the person is told plainly", async () => {
    const did = "I looked at your 2 charter problems. I could not reach the model for 1 measure.";
    mock({ wl: worklist({ kpis: [kpi()], suggestions: [], lens_available: true }),
      lens: lensState({ failed: ["K1"], say: { did, next: "Use a definition.", need: "I could not reach the model for 1 measure: please try again." } }) });
    open(work);
    expect(await screen.findByText(new RegExp(did))).toBeInTheDocument(); // said in Lens's block, never silent
    expect(screen.getAllByRole("button", { name: m2Lens.retry }).length).toBeGreaterThan(0);
  });

  test("P4: the organiser is told plainly when measures wait for governance", async () => {
    const note = "16 measures are visible only to you until you set who may see them.";
    mock({ wl: worklist({ kpis: [kpi()], suggestions: [], governance_note: note }) });
    open(work);
    expect(await screen.findByText(note)).toBeInTheDocument();
  });

  test("triage: four things per measure, each with its mark and who; unknown is shown, not blank", async () => {
    mock({ wl: worklist({ kpis: [kpi()], problems: [{ id: "p1", title: "Calls arrive too late", priority: "must", kpi_ids: ["K1"], has_kpi: true }], suggestions: [], owners_complete: 0 }) });
    open(work);
    const table = await screen.findByRole("table");
    const row = within(table).getByRole("row", { name: /Capital calls due/ });
    expect(within(row).getByText("Capital calls still to be paid, by due date")).toBeInTheDocument();
    expect(within(row).getAllByText(m2Work.marks.guessed)).toHaveLength(2); // definition and how it is gathered
    expect(within(row).getAllByText(m2Work.marks.unknown)).toHaveLength(2); // owner and producer
    expect(within(row).getByText(/by the pack/)).toBeInTheDocument();
    expect(within(row).getByText(m2Work.states.drafted)).toBeInTheDocument();
    expect(screen.getByText(/0 of 1 with all three owners/)).toBeInTheDocument();
  });

  test("saving what you know sends the value with the mark you chose", async () => {
    mock({ wl: worklist({ kpis: [kpi()], suggestions: [] }) });
    const user = userEvent.setup();
    open(work);
    await user.click(await screen.findByRole("button", { name: `${m2Work.details}: Capital calls due, by date` }));
    await user.type(screen.getByLabelText(m2Work.fields.producer), "The fund administrator"); // typing says "I know this"
    await user.click(screen.getByRole("button", { name: `${m2Work.save}: ${m2Work.fields.producer}` }));
    expect(body("PUT", "/kpis/K1/triage", 0)).toEqual({ producer: { text: "The fund administrator", mark: "stated" } });
  });

  test("owners: nominate by name with or without an account; one person can be all three", async () => {
    mock({ wl: worklist({ kpis: [kpi()], suggestions: [] }) });
    const user = userEvent.setup();
    open(work);
    await user.click(await screen.findByRole("button", { name: `${m2Work.details}: Capital calls due, by date` }));
    expect(screen.getByText(/No owner yet: business owner, data owner, process owner/)).toBeInTheDocument();
    await user.type(screen.getByLabelText(`${m2Work.roles.data}: ${m2Work.ownerName}`), "Arjun Rao");
    await user.click(screen.getByRole("button", { name: `${m2Work.nominate}: ${m2Work.roles.data}` }));
    expect(body("PUT", "/kpis/K1/owners", 0)).toEqual({ data: { name: "Arjun Rao", has_account: false } });
    await user.click(screen.getByRole("button", { name: m2Work.meForAll }));
    const mine = { name: "Pat Owner", has_account: true };
    expect(body("PUT", "/kpis/K1/owners", 1)).toEqual({ business: mine, data: mine, process: mine });
  });

  test("a nominated owner can decline, which returns the question", async () => {
    const nominated = prov("Arjun Rao", "stated", "Pat Owner", "nominated, no account yet");
    mock({ wl: worklist({ kpis: [kpi({ owners: { business: noOwner, data: nominated, process: noOwner } })], suggestions: [] }) });
    const user = userEvent.setup();
    open(work);
    await user.click(await screen.findByRole("button", { name: `${m2Work.details}: Capital calls due, by date` }));
    expect(screen.getAllByText(/Arjun Rao/).length).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: `${m2Work.declineOwner}: ${m2Work.roles.data}` }));
    expect(sent("POST", "/kpis/K1/owners/data/decline")).toHaveLength(1);
  });

  test("governance: not sure is explained as personal; who may see it is sent as names", async () => {
    mock({ wl: worklist({ kpis: [kpi()], suggestions: [] }) });
    const user = userEvent.setup();
    open(work);
    await user.click(await screen.findByRole("button", { name: `${m2Work.details}: Capital calls due, by date` }));
    expect(screen.getByText(m2Work.notSureNote)).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: m2Work.personalOptions.no }));
    expect(body("PUT", "/kpis/K1/governance", 0)).toEqual({ personal: "no" });
    await user.type(screen.getByLabelText(m2Work.mayAccess), "Mei, Wei , Tom");
    await user.click(screen.getByRole("button", { name: m2Work.save }));
    expect(body("PUT", "/kpis/K1/governance", 1)).toEqual({ may_see: ["Mei", "Wei", "Tom"] });
  });

  test("a measure you are not named for shows that it exists and nothing else", async () => {
    mock({ wl: worklist({ kpis: [{ id: "K9", name: "Exposure to one name", restricted: true, state: "drafted" }], suggestions: [] }) });
    open(work);
    const row = await screen.findByRole("row", { name: /Exposure to one name/ });
    expect(within(row).getByText(m2Work.restricted)).toBeInTheDocument();
    expect(within(row).queryByRole("button")).not.toBeInTheDocument();
  });

  test("a company with no pack is told so and can still add a measure", async () => {
    mock({ wl: worklist({ problems: [], suggestions: [], charter: null, pack: { available: false, label: "" } }) });
    const user = userEvent.setup();
    open(work);
    expect(await screen.findByText(m2Work.noPack)).toBeInTheDocument();
    await user.type(screen.getByLabelText(m2Work.addName), "Cash on hand");
    await user.click(screen.getByRole("button", { name: m2Work.add }));
    expect(body("POST", "/kpis", 0)).toEqual({ name: "Cash on hand", problem_ids: [] });
  });

  test("a signed baseline cannot be changed from the screen", async () => {
    const base = worklist().baseline;
    mock({ wl: worklist({ baseline: { ...base, state: "signed" }, kpis: [kpi({ state: "signed" })], suggestions: [] }) });
    const user = userEvent.setup();
    open(work);
    await user.click(await screen.findByRole("button", { name: `${m2Work.details}: Capital calls due, by date` }));
    expect(screen.getByRole("button", { name: m2Work.add })).toBeDisabled();
    expect(screen.getByRole("button", { name: `${m2Work.nominate}: ${m2Work.roles.data}` })).toBeDisabled();
    expect(screen.queryByRole("button", { name: m2Work.remove })).not.toBeInTheDocument();
  });

  test("Lens's newer draft sits beside a stated definition and is used only on request", async () => {
    const proposal = prov("Calls due, by notice date", "guessed", "Lens", "Funding calls note");
    mock({ wl: worklist({ kpis: [kpi({ definition: prov("Our wording", "stated", "Pat"), definition_proposal: proposal })], suggestions: [] }) });
    const user = userEvent.setup();
    open(work);
    await user.click(await screen.findByRole("button", { name: `${m2Work.details}: Capital calls due, by date` }));
    expect(screen.getByText("Calls due, by notice date")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: m2Work.useProposal }));
    expect(body("PUT", "/kpis/K1/triage", 0)).toEqual({ definition: { text: "Calls due, by notice date", mark: "stated" } });
  });

  test("a change that is refused shows the server's plain sentence", async () => {
    mock({ wl: worklist({ kpis: [kpi()], suggestions: [] }) });
    const user = userEvent.setup();
    open(work);
    await user.click(await screen.findByRole("button", { name: `${m2Work.details}: Capital calls due, by date` }));
    vi.stubGlobal("fetch", vi.fn(async () => json(409, { error: "signed", message: "This baseline is signed, so it can no longer be changed." })));
    await user.click(screen.getByRole("radio", { name: m2Work.personalOptions.yes }));
    expect(await screen.findByText("This baseline is signed, so it can no longer be changed.")).toBeInTheDocument();
  });

  test("the work list's own refusal and error states", async () => {
    mock({ wlStatus: 404 });
    open(work);
    expect(await screen.findByRole("alert")).toHaveTextContent("m");
  });
});

describe("CRITIC-M2 round 4: the work list", () => {
  test("a click on a measure brings its detail into view and puts the keyboard there", async () => {
    mock({ wl: worklist({ kpis: [kpi()], suggestions: [] }) });
    const scroll = vi.fn();
    Element.prototype.scrollIntoView = scroll; // jsdom has none
    const user = userEvent.setup();
    open(work);
    await user.click(await screen.findByRole("button", { name: `${m2Work.details}: Capital calls due, by date` }));
    const detail = await screen.findByRole("region", { name: `${m2Work.details}: Capital calls due, by date` });
    expect(detail).toHaveFocus();
    expect(scroll).toHaveBeenCalled();
  });

  test("the greeting asks about the owners only while some are missing", async () => {
    const owned = { business: prov("Mei Tan", "stated", "Pat"), data: prov("Arjun Rao", "stated", "Pat"), process: prov("Sara Lim", "stated", "Pat") };
    mock({ wl: worklist({ kpis: [kpi({ owners: owned, missing_owners: [] })], suggestions: [], owners_complete: 1 }) });
    open(work);
    expect(await screen.findByText(m2Work.lensLineOwnersDone)).toBeInTheDocument();
    expect(screen.queryByText(/Shall we nominate the owners/)).toBeNull();
  });

  test("while owners are missing the greeting still asks", async () => {
    mock({ wl: worklist({ kpis: [kpi()], suggestions: [], owners_complete: 0 }) });
    open(work);
    expect(await screen.findByText(m2Work.lensLine)).toBeInTheDocument();
  });

  test("a restricted measure shows only that it is restricted: no name, and nothing to open", async () => {
    mock({ wl: worklist({ kpis: [kpi(), { id: "K18", name: "A restricted measure", restricted: true, state: "drafted" }], suggestions: [] }) });
    open(work);
    const table = await screen.findByRole("table");
    expect(within(table).getByText("A restricted measure")).toBeInTheDocument();
    expect(within(table).queryByRole("button", { name: /A restricted measure/ })).toBeNull();
    expect(within(table).getByText(m2Work.restricted)).toBeInTheDocument();
  });

  test("a signed baseline shows 'Signed: read-only' and Lens can explain but not change", async () => {
    const base = worklist().baseline;
    mock({ wl: worklist({ baseline: { ...base, state: "signed" }, kpis: [kpi({ state: "signed" })], suggestions: [] }), lens: lensState({ locked: true }) });
    open(work);
    expect(await screen.findByText("Signed: read-only")).toBeInTheDocument();
    expect(await screen.findByText(m2Lens.signedNote)).toBeInTheDocument();
  });

  test("the analyst's note about measures waiting for the organiser is shown, without a name", async () => {
    const note = "2 measures are visible only to the organiser until they set who may see them.";
    mock({ wl: worklist({ kpis: [kpi(), { id: "K18", name: "A restricted measure", restricted: true, state: "drafted" }], suggestions: [], governance_note: note }) });
    open(work);
    expect(await screen.findByText(note)).toBeInTheDocument();
  });

  test("the baselines list says which charter each came from", async () => {
    mock({ list: { charters: [], baselines: [
      { id: "c".repeat(32), charter_outcome_id: "b".repeat(32), state: "draft", created_at: "2026-10-02T10:00:00+00:00", kpi_count: 3, charter_title: "Calls arrive too late and 1 more", charter_signed_at: "2026-10-01T10:00:00+00:00" },
      { id: "d".repeat(32), charter_outcome_id: "e".repeat(32), state: "draft", created_at: "2026-10-02T11:00:00+00:00", kpi_count: 2, charter_title: "Nobody trusts the numbers", charter_signed_at: "2026-09-20T10:00:00+00:00" }] } });
    open();
    expect(await screen.findByText(/Calls arrive too late and 1 more/)).toBeInTheDocument();
    expect(screen.getByText(/Nobody trusts the numbers/)).toBeInTheDocument();
    expect(screen.queryByText(m2Work.fromCharter)).toBeNull();
  });
});

describe("M2-FIX-N D8: the four lists of the charter", () => {
  test("problems, pain points, what to track and levers show in four groups and the count adds up", async () => {
    const item = (id: string, title: string, kind: string) => ({ id, title, priority: null, kind });
    mock({
      wl: worklist({
        problems: [{ id: "p1", title: "Calls arrive too late", priority: "must", kind: "problem", kpi_ids: [], has_kpi: false },
          { id: "pp1", title: "Reports go out late", priority: "must", kind: "pain_point", kpi_ids: [], has_kpi: false }],
        suggestions: [{ id: "K1", name: "Capital calls due, by date", problem_ids: ["pp1"], priority: "must" }],
        charter_groups: [
          { key: "problems", heading: "Problems to solve now", items: [item("p1", "Calls arrive too late", "problem")] },
          { key: "pain_points", heading: "Pain points", items: [item("pp1", "Reports go out late", "pain_point")] },
          { key: "future_signals", heading: "What to track in future", items: [item("fs1", "Interest rate moves", "future_signal")] },
          { key: "levers", heading: "Levers for what-if", items: [item("lv1", "Call notice period", "lever")] },
        ],
      }),
    });
    open(work);
    for (const h of Object.values(m2Work.charterGroups)) expect(await screen.findByRole("heading", { name: h })).toBeInTheDocument();
    expect(screen.getByText("Interest rate moves")).toBeInTheDocument();
    expect(screen.getByText("Call notice period")).toBeInTheDocument();
    expect(screen.getByText(/^4 problems/)).toBeInTheDocument(); // module 1's "4 go on"
    const pain = screen.getAllByText("Reports go out late").map((e) => e.closest("li")).find((l) => l?.querySelector(".n-sticky-board")) as HTMLElement;
    expect(within(pain).getByText("Capital calls due, by date")).toBeInTheDocument(); // a pain point gets measure suggestions
  });
});
