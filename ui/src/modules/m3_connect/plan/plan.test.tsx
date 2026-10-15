import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import App from "../../../App";
import { setSessionExpiredHandler } from "../../../api/client";
import type { AssessmentDetail, Step } from "../api";
import { planCopy as T } from "./copy";
import type { PlanItem, PlanView, RiskRow, RisksView } from "./planApi";

// The plan screen (M3-P04): the risks, the three bands, editing with a reason, the sign panel, Nira's sentence, in five states. fetch is stubbed.

const BASE = "/api/modules/m3_connect";
const AID = "a".repeat(32);
const IDS: Step["id"][] = ["map", "request", "scan", "trial", "findings", "plan"];
const steps: Step[] = IDS.map((id) => ({ id, label: id, state: id === "plan" ? "in_progress" : "done", waiting_on: id === "plan" ? "Waiting for sign-off." : "" }));
const detail: AssessmentDetail = {
  assessment: { id: AID, baseline_outcome_id: "b".repeat(32), charter_outcome_id: null, state: "draft", created_by: "Pat", created_at: "2026-10-04T10:00:00+00:00" },
  steps, inputs: null,
};
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const item = (band: PlanItem["band"], over: Partial<PlanItem> = {}): PlanItem => ({
  key: `${band}:S1`, band, restricted: false, summary: `Summary for ${band}`, measures: [{ id: "K1", name: `Measure ${band}` }], pain_points: [{ id: "p1", title: "Late packs" }],
  effort: "small", effort_label: "Days", team: ["Investment Operations"], blocked_by: band === "next" ? ["No sample data has arrived yet"] : [],
  who_unblocks: band === "next" ? ["Omar Lee (data owner)"] : [], date: null, date_text: "[date]", why_descoped: band === "later" ? "Its sources have low impact for now" : null,
  covered_by: null, covered_text: "not planned yet", edits: {}, proposals: {}, ...over,
});
const risk = (id: string, state: RiskRow["state"] = "open", over: Partial<RiskRow> = {}): RiskRow => ({
  id, kind: "ambiguity", text: `Question ${id}`, restricted: false, measures: [{ id: "K1", name: "Measure now" }], pain_points: [], state, decision: null, ...over,
});
const planView = (over: Partial<PlanView> = {}): PlanView => ({
  drafted: true, waiting: null,
  bands_info: { now: { label: "Now", weeks: "Weeks 0 to 3" }, next: { label: "Next", weeks: "Weeks 3 to 8" }, later: { label: "Later", weeks: "8 weeks and beyond" } },
  bands: { now: [item("now")], next: [item("next")], later: [item("later")] }, drafted_at: "2026-10-04T10:00:00+00:00", signed_at: null, outcome_id: null,
  signatures: [], waiting_for: ["Sponsor", "Head of data"], risks_undecided: 2, can_sign: false, restricted_hidden: 0,
  effort: { small: "Days", medium: "About a week", large: "Two or more weeks" }, viewer: { name: "Pat", slot: "sponsor", can_edit: true }, ...over,
});
const counts = (rs: RiskRow[]) => ({ open: rs.filter((r) => r.state === "open").length, accepted: rs.filter((r) => r.state === "accepted").length,
  sent_back: rs.filter((r) => r.state === "sent_back").length, rechecked: rs.filter((r) => r.state === "rechecked").length });
const risksView = (rs: RiskRow[] = [risk("R1"), risk("R2")], over: Partial<RisksView> = {}): RisksView => ({ risks: rs, counts: counts(rs), signed: false, locked: false, ready: true, ...over });

interface World {
  plan?: PlanView;
  risks?: RisksView;
  hold?: boolean;
  status?: number;
  sentence?: string;
  nextStatus?: number;
}
const calls: { method: string; url: string; body?: unknown }[] = [];

function mock(w: World) {
  calls.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    if (url === "/api/auth/me") return json(200, { display_name: "Pat Owner", company_id: "co-a", roles: ["sponsor"] });
    if (url === "/api/company") return json(200, { company_id: "co-a", name: "Harbor Test Co", industry: "family_office" });
    if (url === "/api/modules") return json(200, [{ id: "m3_connect", number: 3, name: "Assess and plan", description: "d", agent: "Lens" }]);
    if (url === `${BASE}/assessments/${AID}`) {
      if (w.hold) return new Promise<Response>(() => undefined);
      return w.status ? json(w.status, { error: w.status === 403 ? "forbidden" : "unreadable", message: "x" }) : json(200, detail);
    }
    if (url === `${BASE}/assessments/${AID}/plan` && method === "GET") return json(200, w.plan ?? planView());
    if (url === `${BASE}/assessments/${AID}/risks` && method === "GET") return json(200, w.risks ?? risksView());
    if (url === `${BASE}/assessments/${AID}/next`) return w.nextStatus ? json(w.nextStatus, {}) : json(200, { step: "plan", done: false, sentence: w.sentence ?? "2 risks need a decision from the sponsor." });
    if (method !== "GET") return json(200, w.plan ?? planView());
    return json(404, {});
  }));
}
const open = () => render(<MemoryRouter initialEntries={[`/modules/m3_connect/plan/${AID}`]}><App /></MemoryRouter>);
const first = <E,>(xs: E[]): E => {
  const x = xs[0];
  if (x === undefined) throw new Error("nothing found");
  return x;
};
const sent = (method: string, tail: string) => calls.filter((c) => c.method === method && c.url === `${BASE}/assessments/${AID}${tail}`);

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  sessionStorage.clear();
  setSessionExpiredHandler(null);
});

describe("plan screen: five states", () => {
  test("loading", async () => {
    mock({ hold: true });
    open();
    expect(await screen.findByRole("status")).toHaveTextContent("Loading");
  });

  test("empty: the plan waits for the findings and says so", async () => {
    mock({ plan: planView({ drafted: false, waiting: "Lens drafts the plan once the findings are in.", bands: { now: [], next: [], later: [] } }), risks: risksView([]) });
    open();
    expect(await screen.findByText("Lens drafts the plan once the findings are in.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Sign as/ })).not.toBeInTheDocument();
  });

  test("error: a way to try again", async () => {
    mock({ status: 500 });
    open();
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  test("refused: no plan shown", async () => {
    mock({ status: 403 });
    open();
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.queryByText(T.plan.title)).not.toBeInTheDocument();
  });

  test("populated: three bands with their cards, and Nira's sentence", async () => {
    mock({});
    open();
    expect(await screen.findByRole("heading", { name: T.plan.title })).toBeInTheDocument();
    for (const [label = "", weeks = ""] of [["Now", "Weeks 0 to 3"], ["Next", "Weeks 3 to 8"], ["Later", "8 weeks and beyond"]] as const) {
      const band = screen.getByRole("region", { name: label });
      expect(within(band).getByText(weeks)).toBeInTheDocument();
    }
    const now = screen.getByRole("region", { name: "Now" });
    expect(within(now).getByText("Summary for now")).toBeInTheDocument();
    expect(within(now).getByText("Measure now")).toBeInTheDocument();
    expect(within(now).getByText(/Late packs/)).toBeInTheDocument();
    expect(within(now).getByText(/Days/)).toBeInTheDocument();
    const next = screen.getByRole("region", { name: "Next" });
    expect(within(next).getByText(/No sample data has arrived yet/)).toBeInTheDocument();
    expect(within(next).getByText(/Omar Lee \(data owner\)/)).toBeInTheDocument();
    expect(within(next).getByText(/No date yet/)).toBeInTheDocument();
    const later = screen.getByRole("region", { name: "Later" });
    expect(within(later).getByText(/Its sources have low impact for now/)).toBeInTheDocument();
    expect(within(later).getByText(/not planned yet/)).toBeInTheDocument();
    expect(screen.getByText(T.suggestion)).toBeInTheDocument();
    expect(await screen.findByText("2 risks need a decision from the sponsor.")).toBeInTheDocument();
  });

  test("Nira falls back to the first waiting step when the sentence cannot be had", async () => {
    mock({ nextStatus: 500 });
    open();
    expect(await screen.findByText("Waiting for sign-off.")).toBeInTheDocument();
  });
});

describe("risks", () => {
  test("accept sends the optional note and asks again", async () => {
    mock({});
    const user = userEvent.setup();
    open();
    await screen.findByText("Question R1");
    await user.type(screen.getByLabelText(`${T.risks.note}: Question R1`), "We know about this");
    await user.click(first(screen.getAllByRole("button", { name: T.risks.accept })));
    await vi.waitFor(() => expect(sent("POST", "/risks/R1/decision")).toHaveLength(1));
    expect(sent("POST", "/risks/R1/decision")[0]?.body).toEqual({ decision: "accepted", note: "We know about this" });
  });

  test("send back needs a reason and then sends it", async () => {
    mock({});
    const user = userEvent.setup();
    open();
    await screen.findByText("Question R1");
    await user.click(first(screen.getAllByRole("button", { name: T.risks.sendBack })));
    expect(await screen.findByText(T.risks.needReason)).toBeInTheDocument();
    expect(sent("POST", "/risks/R1/decision")).toHaveLength(0);
    await user.type(screen.getByLabelText(`${T.risks.note}: Question R1`), "Count the empty cells");
    await user.click(first(screen.getAllByRole("button", { name: T.risks.sendBack })));
    await vi.waitFor(() => expect(sent("POST", "/risks/R1/decision")).toHaveLength(1));
    expect(sent("POST", "/risks/R1/decision")[0]?.body).toEqual({ decision: "sent_back", reason: "Count the empty cells" });
  });

  test("the date reads No date yet for null and for the old placeholder; accepted-in-module-2 lines are grouped", async () => {
    const tail = " (accepted in module 2 by Mei Tan)";
    mock({ risks: risksView([risk("R1", "open", { text: `F001 \`cash\` *is* unclear${tail}` }), risk("R2", "open", { text: `Second${tail}` })]) });
    open();
    await screen.findByRole("heading", { name: T.plan.title });
    expect(screen.getAllByText("No date yet").length).toBeGreaterThan(0);
    expect(screen.queryByText("[date]")).not.toBeInTheDocument();
    expect(screen.queryByText(/accepted in module 2 by/)).not.toBeInTheDocument();
    expect(screen.getByText("Mei Tan accepted 2 of these in module 2.")).toBeInTheDocument();
    expect(screen.getByText("F001 cash is unclear")).toBeInTheDocument();
  });

  test("accept all remaining is one action", async () => {
    mock({});
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: T.risks.acceptAll }));
    await vi.waitFor(() => expect(sent("POST", "/risks/accept-all")).toHaveLength(1));
  });

  test("a decided risk shows who and when; a restricted one shows no text and no buttons", async () => {
    const decided = risk("R1", "accepted", { decision: { decision: "accepted", note: "Fine", reason: null, by: "Sam Sponsor", at: "2026-10-04T10:00:00+00:00" } });
    const hidden = risk("R2", "open", { restricted: true, text: "A restricted measure", measures: [] });
    mock({ risks: risksView([decided, hidden]) });
    open();
    expect(await screen.findByText(/Sam Sponsor, 4 October 2026: Fine/)).toBeInTheDocument();
    expect(screen.getAllByText("A restricted measure").length).toBeGreaterThan(0);
    expect(screen.queryByLabelText(`${T.risks.note}: A restricted measure`)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: T.risks.acceptAll })).toBeInTheDocument();
  });
});

describe("the plan", () => {
  test("a change needs a reason and sends only what changed", async () => {
    mock({});
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: `${T.plan.edit}: Measure next` }));
    await user.selectOptions(screen.getByLabelText(T.plan.effort, { selector: "select" }), "large");
    await user.click(screen.getByRole("button", { name: T.plan.save }));
    expect(await screen.findByText(T.plan.needReason)).toBeInTheDocument();
    expect(sent("PUT", "/plan/item")).toHaveLength(0);
    await user.type(screen.getByLabelText(T.plan.reason), "The vendor needs two weeks");
    await user.click(screen.getByRole("button", { name: T.plan.save }));
    await vi.waitFor(() => expect(sent("PUT", "/plan/item")).toHaveLength(1));
    expect(sent("PUT", "/plan/item")[0]?.body).toEqual({ key: "next:S1", reason: "The vendor needs two weeks", effort: "large" });
  });

  test("saving with nothing changed says so", async () => {
    mock({});
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: `${T.plan.edit}: Measure later` }));
    await user.type(screen.getByLabelText(T.plan.reason), "No reason");
    await user.click(screen.getByRole("button", { name: T.plan.save }));
    expect(await screen.findByText(T.plan.nothingChanged)).toBeInTheDocument();
  });

  test("an edited item shows who changed it and why, and a proposal waits beside it", async () => {
    const edited = item("next", { edits: { effort: { value: "large", reason: "Vendor is slow", by: "Sam", at: "2026-10-04T10:00:00+00:00" } }, proposals: { effort: "small" } });
    mock({ plan: planView({ bands: { now: [], next: [edited], later: [] } }) });
    open();
    expect(await screen.findByText("Changed by Sam: Vendor is slow")).toBeInTheDocument();
    expect(screen.getByText(/Lens now suggests: effort Days/)).toBeInTheDocument();
  });

  test("a restricted item is only the words A restricted measure", async () => {
    const stub: PlanItem = { key: "later:r:K2", band: "later", restricted: true, summary: "A restricted measure", measures: [], pain_points: [], team: [], blocked_by: [], who_unblocks: [] };
    mock({ plan: planView({ bands: { now: [], next: [], later: [stub] } }) });
    open();
    const later = await screen.findByRole("region", { name: "Later" });
    expect(within(later).getByText("A restricted measure")).toBeInTheDocument();
    expect(within(later).queryByRole("button")).not.toBeInTheDocument();
  });

  test("draft again asks the server and says the changes were kept", async () => {
    mock({});
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: T.plan.redraft }));
    expect(await screen.findByText(T.plan.redrafted)).toBeInTheDocument();
    expect(sent("POST", "/plan/draft")).toHaveLength(1);
  });
});

describe("the sign panel", () => {
  test("while risks are open the button is off and says why", async () => {
    mock({});
    open();
    expect(await screen.findByText(T.sign.risksOpen(2))).toBeInTheDocument();
    expect(screen.getByRole("button", { name: T.sign.signAs.sponsor })).toBeDisabled();
  });

  test("when every risk is decided the sponsor signs", async () => {
    mock({ plan: planView({ risks_undecided: 0, can_sign: true }), risks: risksView([risk("R1", "accepted")]) });
    const user = userEvent.setup();
    open();
    const button = await screen.findByRole("button", { name: T.sign.signAs.sponsor });
    expect(button).toBeEnabled();
    await user.click(button);
    await vi.waitFor(() => expect(sent("POST", "/plan/sign")).toHaveLength(1));
  });

  test("the head of data sees their own button after the sponsor", async () => {
    mock({ plan: planView({ risks_undecided: 0, can_sign: true, viewer: { name: "Pat", slot: "head_of_data", can_edit: false },
      signatures: [{ slot: "sponsor", label: "Sponsor", name: "Sam Sponsor", at: "2026-10-04T10:00:00+00:00", restricted_covered: 1, note: "covers 1 restricted measure" }], waiting_for: ["Head of data"] }),
    risks: risksView([risk("R1", "accepted")], { locked: true }) });
    open();
    expect(await screen.findByRole("button", { name: T.sign.signAs.head_of_data })).toBeEnabled();
    expect(screen.getByText(/Sponsor: Sam Sponsor/)).toBeInTheDocument();
    expect(screen.getByText(/covers 1 restricted measure/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: T.plan.edit })).not.toBeInTheDocument();       // the first signature locks the plan
    expect(screen.queryByRole("button", { name: T.risks.accept })).not.toBeInTheDocument();
  });

  test("someone whose turn it is not sees no button", async () => {
    mock({ plan: planView({ viewer: { name: "Pat", slot: null, can_edit: true } }) });
    open();
    expect(await screen.findByText(T.sign.notYourTurn)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Sign as/ })).not.toBeInTheDocument();
  });

  test("signed: read-only, with both names, and nothing left to press", async () => {
    mock({ plan: planView({ risks_undecided: 0, can_sign: true, signed_at: "2026-10-04T12:00:00+00:00", waiting_for: [], outcome_id: "o".repeat(32),
      viewer: { name: "Pat", slot: null, can_edit: false },
      signatures: [{ slot: "sponsor", label: "Sponsor", name: "Sam", at: "2026-10-04T10:00:00+00:00", restricted_covered: 0, note: null },
        { slot: "head_of_data", label: "Head of data", name: "Hana", at: "2026-10-04T12:00:00+00:00", restricted_covered: 0, note: null }] }),
    risks: risksView([risk("R1", "accepted")], { signed: true, locked: true }) });
    open();
    expect(await screen.findByText(T.sign.signed)).toBeInTheDocument();
    expect(screen.getByText(/Sponsor: Sam/)).toBeInTheDocument();
    expect(screen.getByText(/Head of data: Hana/)).toBeInTheDocument();
    for (const name of [/Sign as/, T.plan.edit, T.risks.accept, T.risks.sendBack, T.plan.redraft, T.risks.acceptAll]) {
      expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
    }
  });

  test("a restricted measure hidden from the signer is said plainly", async () => {
    mock({ plan: planView({ restricted_hidden: 2 }) });
    open();
    expect(await screen.findByText(T.sign.hidden(2))).toBeInTheDocument();
  });
});
