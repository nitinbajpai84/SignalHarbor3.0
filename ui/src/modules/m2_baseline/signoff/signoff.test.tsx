import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import type { AuditLog, Gate, KpiReview, PartView, SignoffView } from "../api";
import { m2Signoff as T } from "../copy";
import SignoffScreen from "./SignoffScreen";

// M2-P05: the review and sign-off screen in its five states, confirming, accepting, signing and the read-only paper. fetch is stubbed.

const BID = "b1";
const BASE = `/api/modules/m2_baseline/baselines/${BID}`;
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const part = (id: string, label: string, owner_label: string, owner: string | null, over: Partial<PartView> = {}): PartView => ({
  id, label, owner_label, owner_status: owner ? "named" : "no_owner", owner_name: owner, named_by_sponsor: false, confirmed: null, ...over,
});
const kpi = (over: Partial<KpiReview> = {}): KpiReview => ({
  id: "K1", name: "Capital call timeliness", priority: "must", state: "ready",
  parts: [part("definition", "Definition", "business owner", "Bea Business"), part("source", "Source", "data owner", "Dan Data"), part("process", "Process", "process owner", "Pia Process")],
  source: { status: "stated", value: "Custodian portal export" }, sensing: [],
  tracking: { value: "tracked_now", mark: "stated", label: "Tracked today", today: true },
  unknowns: [], missing: [], waiting_on: [], waiting_note: null, confirmed_all: false, review: null, ...over,
});
const k2 = kpi({
  id: "K2", name: "Exposure concentration", source: { status: "unknown", value: null },
  tracking: { value: "not_tracked", mark: "stated", label: "Not tracked today", today: false },
  unknowns: ["Source is unknown"], review: { tentative_date: "2027-03-31", next_step: "Ask the custodian", project: "Data hub", accepted: null },
});
const k3 = kpi({
  id: "K3", name: "Manager fee reconciliation", state: "blocked", unknowns: ["No business owner: the sponsor needs to name one"],
  parts: [part("definition", "Definition", "business owner", null), part("source", "Source", "data owner", "Dan Data"), part("process", "Process", "process owner", "Pia Process")],
});
const view = (over: Partial<SignoffView> = {}): SignoffView => ({
  baseline_id: BID, version: 1, versions: 1, status: "open", locked: null, signatures: [], waiting_for: ["Sponsor", "Head of data"], signed_at: null, outcome_id: null,
  ready: true, can_countersign: false,
  items: [
    { id: "owners", label: "Every measure has its three owners, or is marked blocked", met: true, required: true, missing: [] },
    { id: "source", label: "Every measure has a stated source, or it is marked unknown", met: true, required: true, missing: [] },
    { id: "sensing", label: "The sensing questions are answered", met: true, required: true, missing: [] },
    { id: "next_steps", label: "Every measure not tracked today has a next step and a sponsor's acceptance", met: false, required: false, missing: ["Exposure concentration: the sponsor has not accepted it as unknown for now"] },
  ],
  kpis: [kpi(), k2, k3],
  coming: [{ kpi_id: "K2", name: "Exposure concentration", tentative_date: "2027-03-31", next_step: "Ask the custodian", project: "Data hub", accepted: null }],
  viewer: { name: "Bea Business", sponsor: false, can_settle: false, slot: null }, ...over,
});
const audit = (over: Partial<AuditLog> = {}): AuditLog => ({ entries: [], intact: true, ...over });

interface Call { method: string; url: string; body: unknown }
const calls: Call[] = [];
function mock(handler: (c: Call) => Response | Promise<Response>) {
  calls.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const c = { method: init?.method ?? "GET", url, body: init?.body ? JSON.parse(String(init.body)) : undefined };
    calls.push(c);
    return handler(c);
  }));
}
const serve = (v: SignoffView, a: AuditLog = audit(), rest: (c: Call) => Response | undefined = () => undefined) =>
  mock((c) => rest(c) ?? (c.url.endsWith("/audit") ? json(200, a) : json(200, v)));
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
function open() {
  return render(
    <MemoryRouter initialEntries={[`/modules/m2_baseline/signoff/${BID}`]}>
      <Routes>
        <Route path="/modules/m2_baseline/signoff/:baselineId" element={<SignoffScreen />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("the review and sign-off screen: five states", () => {
  it("loading", () => {
    mock(() => new Promise<Response>(() => undefined));
    open();
    expect(screen.getByRole("status")).toHaveTextContent("Loading");
  });
  it("empty: a baseline with no measures says so, and is not ready", async () => {
    serve(view({ kpis: [], coming: [], ready: false, items: [{ id: "owners", label: "Every measure has its three owners, or is marked blocked", met: false, required: true, missing: ["There are no measures to baseline yet"] }] }));
    open();
    expect(await screen.findByText(T.readiness.noMeasures)).toBeInTheDocument();
    expect(screen.getByText(T.readiness.notReady)).toBeInTheDocument();
  });
  it("error: plain words and a way to try again", async () => {
    mock(() => json(500, { detail: "boom" }));
    open();
    expect(await screen.findByRole("alert")).not.toHaveTextContent("boom");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
  it("refused: another role is told they have no access", async () => {
    mock(() => json(403, { error: "forbidden", message: "x" }));
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent("do not have access");
  });
  it("populated: the checklist, what is unknown, what is coming and the signature lines", async () => {
    serve(view());
    open();
    expect(await screen.findByText(T.readiness.ready)).toBeInTheDocument();
    expect(screen.getByText("Every measure has a stated source, or it is marked unknown")).toBeInTheDocument();
    expect(screen.getByText("Exposure concentration: the sponsor has not accepted it as unknown for now")).toBeInTheDocument();
    expect(screen.getByText("Source is unknown")).toBeInTheDocument();
    expect(screen.getByText("No business owner: the sponsor needs to name one")).toBeInTheDocument();
    expect(screen.getByText(T.kpis.state.blocked)).toBeInTheDocument();
    expect(screen.getByText(T.coming.row("Exposure concentration", "2027-03-31", "Data hub"))).toBeInTheDocument();
    expect(screen.getByText("Sponsor")).toBeInTheDocument();
    expect(screen.getByText("Head of data")).toBeInTheDocument();
    expect(await screen.findByText(T.audit.empty)).toBeInTheDocument();
    expect(await screen.findByText(T.audit.intact)).toBeInTheDocument();
  });
});

describe("owners confirm, the sponsor accepts and names, the sponsor and head of data sign", () => {
  it("shows a Confirm button only on the part the viewer owns, and sends it", async () => {
    const after = view({ kpis: [kpi({ parts: [part("definition", "Definition", "business owner", "Bea Business", { confirmed: { by: "Bea Business", at: "2026-10-03T10:00:00+00:00" } }), ...kpi().parts.slice(1)] }), k2, k3] });
    serve(view(), audit(), (c) => (c.method === "POST" ? json(200, after) : undefined));
    open();
    const buttons = await screen.findAllByRole("button", { name: /^Confirm:/ });
    expect(buttons.map((b) => b.getAttribute("aria-label"))).toEqual(["Confirm: Capital call timeliness, Definition", "Confirm: Exposure concentration, Definition"]);
    await userEvent.click(buttons[0]!);
    expect(calls.find((c) => c.method === "POST")).toMatchObject({ url: `${BASE}/confirm`, body: { kpi_id: "K1", part: "definition" } });
    expect(await screen.findByText(T.parts.confirmedBy("Bea Business", "3 October 2026"))).toBeInTheDocument();
  });
  it("a sponsor names a missing owner and accepts a measure as unknown for now", async () => {
    const sponsor = view({ viewer: { name: "Sam Sponsor", sponsor: true, can_settle: true, slot: "sponsor" } });
    const accepted = view({ viewer: sponsor.viewer, kpis: [kpi(), { ...k2, review: { ...k2.review!, accepted: { by: "Sam Sponsor", at: "2026-10-03T10:00:00+00:00" } } }, k3] });
    serve(sponsor, audit(), (c) => (c.method === "POST" ? json(200, c.url.endsWith("/accept") ? accepted : sponsor) : undefined));
    open();
    await userEvent.type(await screen.findByLabelText("Name the business owner"), "Bea Business");
    await userEvent.click(screen.getByRole("button", { name: T.parts.nameButton }));
    expect(calls.find((c) => c.url.endsWith("/K3/owner"))).toMatchObject({ method: "POST", body: { part: "definition", name: "Bea Business" } });
    await userEvent.click(await screen.findByRole("button", { name: `${T.next.accept}: Exposure concentration` }));
    expect(await screen.findByText(T.next.accepted("Sam Sponsor", "3 October 2026"))).toBeInTheDocument();
  });
  it("saves a next step and a tentative date", async () => {
    serve(view());
    open();
    const step = await screen.findByLabelText(`${T.next.step}: Exposure concentration`);
    await userEvent.clear(step);
    await userEvent.type(step, "Ask for a feed");
    await userEvent.click(screen.getByRole("button", { name: `${T.next.save}: Exposure concentration` }));
    expect(calls.find((c) => c.method === "PUT")).toMatchObject({ url: `${BASE}/review/K2`, body: { tentative_date: "2027-03-31", next_step: "Ask for a feed", project: "Data hub" } });
  });
  it("a signer sees the Sign button only when the baseline can be signed", async () => {
    const signer = { name: "Sam Sponsor", sponsor: true, can_settle: true, slot: "sponsor" };
    serve(view({ viewer: signer }));
    const first = open();
    expect(await screen.findByText(T.paper.cannot)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: T.paper.sign })).toBeNull();
    first.unmount();
    const signed = view({ viewer: signer, can_countersign: true, status: "open", signatures: [{ slot: "sponsor", label: "Sponsor", name: "Sam Sponsor", at: "2026-10-03T10:00:00+00:00" }], waiting_for: ["Head of data"] });
    serve(view({ viewer: signer, can_countersign: true }), audit(), (c) => (c.method === "POST" ? json(200, signed) : undefined));
    open();
    await userEvent.click(await screen.findByRole("button", { name: T.paper.sign }));
    expect(calls.find((c) => c.method === "POST")?.url).toBe(`${BASE}/countersign`);
    expect(await screen.findByText(T.paper.waiting(["Head of data"]))).toBeInTheDocument();
  });
  it("a sponsor who cannot see every measure is told what their signature covers, and it shows once signed", async () => {
    const signer = { name: "Sam Sponsor", sponsor: true, can_settle: true, slot: "sponsor" };
    const note = "covers 1 restricted measure confirmed by their named owners";
    serve(view({ viewer: signer, can_countersign: true, restricted_count: 1, note: "1 measure is restricted from you.", signatures: [{ slot: "sponsor", label: "Sponsor", name: "Sam Sponsor", at: "2026-10-03T10:00:00+00:00", restricted_covered: 1, note }], waiting_for: ["Head of data"] }));
    open();
    expect(await screen.findByText("1 measure is restricted from you.")).toBeInTheDocument();
    expect(screen.getByText(note)).toBeInTheDocument();
  });
  it("a signed baseline is read-only: no inputs, no Confirm, and a way to start a new version", async () => {
    const sigs = [
      { slot: "sponsor", label: "Sponsor", name: "Sam Sponsor", at: "2026-10-03T10:00:00+00:00" },
      { slot: "head_of_data", label: "Head of data", name: "Hana Head", at: "2026-10-04T10:00:00+00:00" },
    ];
    const done = view({ status: "signed", signatures: sigs, waiting_for: [], locked: "the baseline is already signed by Sam Sponsor (Sponsor), Hana Head (Head of data)", signed_at: sigs[1]!.at });
    serve(done, audit(), (c) => (c.method === "POST" ? json(200, view({ version: 2, versions: 2 })) : undefined));
    open();
    expect(await screen.findByText(`${T.paper.locked} ${T.paper.handedOn}`)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Confirm:/ })).toBeNull();
    const step = screen.getByLabelText(`${T.next.step}: Exposure concentration`);
    expect(step.closest("fieldset")).toBeDisabled();
    expect(screen.getByText("Hana Head")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: T.paper.newVersion }));
    expect(calls.find((c) => c.method === "POST")?.url).toBe(`${BASE}/versions`);
    expect(await screen.findByText(T.version(2))).toBeInTheDocument();
  });
  it("a refused change shows the server's plain sentence", async () => {
    serve(view(), audit(), (c) => (c.method === "POST" ? json(409, { error: "not_your_part", message: "Only Bea Business, the business owner, can confirm this part." }) : undefined));
    open();
    await userEvent.click((await screen.findAllByRole("button", { name: /^Confirm:/ }))[0]!);
    expect(await screen.findByRole("alert")).toHaveTextContent("Only Bea Business, the business owner, can confirm this part.");
  });
  it("lists the history and warns when it does not match what was recorded", async () => {
    serve(view(), audit({ intact: false, entries: [{ n: 1, at: "2026-10-03T10:00:00+00:00", by: "Bea Business", action: "confirm", version: 1, kpi_id: "K1" }] }));
    open();
    const item = await screen.findByText(/Bea Business confirmed a part/);
    expect(within(item.closest("ul")!.parentElement!).getByRole("alert")).toHaveTextContent(T.audit.broken);
    await waitFor(() => expect(item).toBeInTheDocument());
  });
});

describe("who blocks what, and settling a real conflict", () => {
  const conflicted = kpi({
    waiting_on: ["Wei Chen"], waiting_note: "waiting on Wei Chen",
    sensing: [{ id: "tracked_today", label: "Tracked today", status: "conflict", value: null, settled: null,
      options: [{ value: "yes", by: "Dan Data" }, { value: "no", by: "Pia Process" }] }],
  });
  it("names the person a measure is waiting on", async () => {
    serve(view({ kpis: [conflicted] }));
    open();
    expect(await screen.findByText("Waiting on Wei Chen")).toBeInTheDocument();
  });
  it("a sponsor or admin picks one of the stated answers; both are listed", async () => {
    const sponsor = { name: "Sam Sponsor", sponsor: true, can_settle: true, slot: "sponsor" };
    const after = view({ viewer: sponsor, kpis: [kpi({ sensing: [{ id: "tracked_today", label: "Tracked today", status: "stated", value: "no", options: [], settled: { value: "no", by: "Sam Sponsor", at: "2026-10-03T10:00:00+00:00" } }] })] });
    serve(view({ viewer: sponsor, kpis: [conflicted] }), audit(), (c) => (c.method === "POST" ? json(200, after) : undefined));
    open();
    expect(await screen.findByText(T.settle.option("yes", "Dan Data"))).toBeInTheDocument();
    expect(screen.getByText(T.settle.option("no", "Pia Process"))).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: `${T.settle.button}: Tracked today, no` }));
    expect(calls.find((c) => c.method === "POST")).toMatchObject({ url: `${BASE}/signoff/settle`, body: { kpi_id: "K1", field: "tracked_today", value: "no" } });
    expect(await screen.findByText(`Tracked today: ${T.settle.settledBy("no", "Sam Sponsor", "3 October 2026")}`)).toBeInTheDocument();
  });
  it("someone who cannot settle sees the conflict but no button", async () => {
    serve(view({ kpis: [conflicted] }));
    open();
    await screen.findByText(T.settle.option("yes", "Dan Data"));
    expect(screen.queryByRole("button", { name: new RegExp(T.settle.button) })).toBeNull();
  });
});

describe("CRITIC-M2 round 4: plain words and one signed state", () => {
  const sensing = (over = {}) => ({ id: "tracked_today", label: "Tracked today", status: "conflict" as const, value: null, settled: null,
    options: [{ value: "tracked_now", label: "Tracked today", by: "Dan Data" }, { value: "not_tracked", label: "Not tracked today", by: "Pia Process" }], ...over });
  it("a conflict shows the words, never the stored id", async () => {
    serve(view({ viewer: { name: "Sam Sponsor", sponsor: true, can_settle: true, slot: "sponsor" }, kpis: [kpi({ sensing: [sensing()] })] }));
    open();
    expect(await screen.findByText(T.settle.option("Tracked today", "Dan Data"))).toBeInTheDocument();
    expect(screen.getByText(T.settle.option("Not tracked today", "Pia Process"))).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/tracked_now|not_tracked|tracked_today/);
  });
  it("a settled difference reads in words too", async () => {
    const done = sensing({ status: "stated", options: [], settled: { value: "tracked_now", label: "Tracked today", by: "Sam Sponsor", at: "2026-10-03T10:00:00+00:00" } });
    serve(view({ kpis: [kpi({ sensing: [done] })] }));
    open();
    expect(await screen.findByText(`Tracked today: ${T.settle.settledBy("Tracked today", "Sam Sponsor", "3 October 2026")}`)).toBeInTheDocument();
  });
  it("the history names the measure and the part, groups repeats, and has no raw words", async () => {
    const at = "2026-10-03T10:00:00+00:00";
    const entries = [
      { n: 1, at, by: "Mei Tan", action: "confirm", version: 1, kpi_id: "K1", part: "definition" },
      { n: 2, at, by: "Mei Tan", action: "confirm", version: 1, kpi_id: "K1", part: "source" },
      { n: 3, at, by: "Mei Tan", action: "confirm", version: 1, kpi_id: "K1", part: "process" },
      { n: 4, at, by: "Mei Tan", action: "confirm", version: 1, kpi_id: "K2", part: "definition" },
      { n: 5, at, by: "Sam Sponsor", action: "settle", version: 1, kpi_id: "K1", detail: "settled tracked today" },
    ];
    serve(view(), audit({ entries }));
    open();
    expect(await screen.findByText("3 October 2026: Mei Tan confirmed the business owner, data owner and process owner parts of Capital call timeliness")).toBeInTheDocument();
    expect(screen.getByText("3 October 2026: Mei Tan confirmed the business owner part of Exposure concentration")).toBeInTheDocument();
    expect(screen.getByText(/Sam Sponsor settled a difference for Capital call timeliness \(settled tracked today\)/)).toBeInTheDocument();
    expect(screen.queryByText(/confirmed a part/)).toBeNull();
    expect(document.body.textContent).not.toMatch(/tracked_now|tracked_today/);
  });
  it("a partly tracked measure is not headed 'Not tracked today'", async () => {
    const partly = kpi({ id: "K4", name: "Partly one", tracking: { value: "partly", mark: "stated", label: "Partly tracked", today: false },
      review: { tentative_date: null, next_step: null, project: null, accepted: null } });
    serve(view({ kpis: [partly] }));
    open();
    expect(await screen.findByText(T.next.titlePartly)).toBeInTheDocument();
    expect(screen.queryByText(T.next.title)).toBeNull();
  });
  it("a measure covered by its named owners says so instead of 'Not accepted yet'", async () => {
    serve(view({ kpis: [{ ...k2, covered: true }] }));
    open();
    expect(await screen.findByText(T.next.covered)).toBeInTheDocument();
    expect(screen.queryByText(T.next.notAccepted)).toBeNull();
  });
  it("a signed baseline shows the same read-only banner as every other screen", async () => {
    serve(view({ status: "signed", waiting_for: [], signatures: [{ slot: "sponsor", label: "Sponsor", name: "Sam", at: "2026-10-03T10:00:00+00:00" }] }));
    open();
    expect(await screen.findByText("Signed: read-only")).toBeInTheDocument();
  });
});

describe("M2-FIX-N", () => {
  it("D4: an owner whose role cannot open the review sees their own parts and can confirm them", async () => {
    let confirmed = false;
    mock((c) => {
      if (c.url.endsWith("/review")) return json(403, { error: "forbidden", message: "You do not have access." });
      if (c.method === "POST") confirmed = true;
      return json(200, { status: "open", parts: [{ kpi_id: "K1", kpi_name: "Capital call timeliness", part: "definition", label: "Definition", confirmed }] });
    });
    open();
    await userEvent.click(await screen.findByRole("button", { name: /Confirm my part/ }));
    expect(calls.find((c) => c.method === "POST")?.url).toBe(`${BASE}/confirm`);
    expect(await screen.findByText(T.mine.done)).toBeInTheDocument();
    expect(screen.queryByText("Exposure concentration")).toBeNull();
  });
  it("D10: while a signature is saving the page says so, then shows the signature, never a stale 'Not signed yet'", async () => {
    const signer = { name: "Sam Sponsor", sponsor: true, can_settle: true, slot: "sponsor" };
    const after = view({ viewer: signer, can_countersign: true, signatures: [{ slot: "sponsor", label: "Sponsor", name: "Sam Sponsor", at: "2026-10-03T10:00:00+00:00" }], waiting_for: ["Head of data"] });
    let release: (r: Response) => void = () => undefined;
    serve(view({ viewer: signer, can_countersign: true }), audit(), (c) => (c.method === "POST" ? (new Promise<Response>((r) => (release = r)) as unknown as Response) : undefined));
    open();
    await userEvent.click(await screen.findByRole("button", { name: T.paper.sign }));
    expect(await screen.findAllByText(T.paper.saving)).not.toHaveLength(0);
    expect([...document.querySelectorAll(".sig-actor")].map((e) => e.textContent)).not.toContain(T.paper.notSigned);
    release(json(200, after));
    expect(await screen.findByText("Sam Sponsor")).toBeInTheDocument();
    expect(screen.queryByText(T.paper.saving)).toBeNull();
  });
});

// ---- M2-E4: the ready-to-build checklist, the two documents, the downloads and "Leave out"
const gate = (over: Partial<Gate> = {}): Gate => ({
  ok: false,
  measures: { ready: 1, total: 2, items: [
    { kpi_id: "K1", name: "Capital call timeliness", ready: true, reasons: [], open: 0 },
    { kpi_id: "K2", name: "Exposure concentration", ready: false, reasons: ["The technical definition is not complete: it still needs its calculation."], open: 0 },
  ] },
  glossary: { ok: false, reasons: ["2 new entries have not been reviewed."] },
  governance: { ok: true, reasons: [] },
  open: { n: 1 },
  left_out: [],
  restricted: false,
  fix: { measures: "baselines", glossary: "glossary", governance: "governance", open: "questions" },
  refusal: "The baseline cannot be signed yet: 1 of 2 measures are ready to build; the glossary has not been reviewed yet; 1 open question remains.",
  ...over,
});
const docs = [{ id: "business_glossary" as const, name: "Business glossary" }, { id: "data_catalogue" as const, name: "Data catalogue" }];
const G = T.gate;
const D = T.documents;
const sponsor = { name: "Sam Sponsor", sponsor: true, can_settle: true, slot: "sponsor" };

describe("M2-E4 the checklist", () => {
  it("shows each line with where it is fixed, and the reasons for what is open", async () => {
    serve(view({ gate: gate(), documents: docs }));
    open();
    expect(await screen.findByText(G.measures(1, 2))).toBeInTheDocument();
    expect(screen.getByText(G.glossary)).toBeInTheDocument();
    expect(screen.getByText(G.governance)).toBeInTheDocument();
    expect(screen.getByText(G.open(1))).toBeInTheDocument();
    expect(screen.getByText("2 new entries have not been reviewed.")).toBeInTheDocument();
    expect(screen.getAllByText("The technical definition is not complete: it still needs its calculation.")).not.toHaveLength(0);
    expect(screen.getByText(G.notReady)).toBeInTheDocument();
    const links = screen.getAllByRole("link", { name: G.fix }).map((a) => a.getAttribute("href"));
    expect(links).toEqual([`/modules/m2_baseline/baselines/${BID}`, `/modules/m2_baseline/glossary/${BID}`, `/modules/m2_baseline/questions/${BID}`]); // governance is done: no link
  });
  it("says 'Something restricted is still open' without detail when something hidden is open", async () => {
    serve(view({ gate: gate({ restricted: true }), documents: docs }));
    open();
    expect(await screen.findByText(G.restricted)).toBeInTheDocument();
  });
  it("when it does not hold the sentence shows and Sign is off; when it does, it says ready and Sign works", async () => {
    serve(view({ viewer: sponsor, can_countersign: true, gate: gate(), documents: docs }));
    const first = open();
    expect(await screen.findByText(gate().refusal)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: T.paper.sign })).toBeDisabled();
    first.unmount();
    serve(view({ viewer: sponsor, can_countersign: true, gate: gate({ ok: true, glossary: { ok: true, reasons: [] }, open: { n: 0 }, measures: { ready: 2, total: 2, items: [] }, refusal: "" }), documents: docs }));
    open();
    expect(await screen.findByText(G.ready)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: T.paper.sign })).toBeEnabled();
  });
  it("an organiser or sponsor leaves a measure out with a reason; the reason shows and the measure can be brought back", async () => {
    const out = gate({ left_out: [{ kpi_id: "K2", name: "Exposure concentration", reason: "Replaced next year.", by: "Sam Sponsor", at: "2026-10-03T10:00:00+00:00" }] });
    serve(view({ viewer: sponsor, gate: gate(), documents: docs }), audit(), (c) => (c.method === "POST" ? json(200, view({ viewer: sponsor, gate: c.url.endsWith("/bring-back") ? gate() : out, documents: docs })) : undefined));
    open();
    await userEvent.type(await screen.findByLabelText(G.leftOut.reason("Exposure concentration")), "Replaced next year.");
    await userEvent.click(screen.getByRole("button", { name: `${G.leftOut.button}: Exposure concentration` }));
    expect(calls.find((c) => c.method === "POST")).toMatchObject({ url: `${BASE}/review/K2/leave-out`, body: { reason: "Replaced next year." } });
    expect(await screen.findByText(G.leftOut.line("Exposure concentration", "Replaced next year.", "Sam Sponsor"))).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: `${G.leftOut.bring}: Exposure concentration` }));
    expect(calls.filter((c) => c.method === "POST").pop()?.url).toBe(`${BASE}/review/K2/bring-back`);
  });
  it("someone who may not leave a measure out sees no button, and the button waits for a reason", async () => {
    serve(view({ gate: gate(), documents: docs }));
    const first = open();
    await screen.findByText(G.measures(1, 2));
    expect(screen.queryByRole("button", { name: /Leave out/ })).toBeNull();
    first.unmount();
    serve(view({ viewer: sponsor, gate: gate(), documents: docs }));
    open();
    expect(await screen.findByRole("button", { name: `${G.leftOut.button}: Exposure concentration` })).toBeDisabled();
  });
});

describe("M2-E4 the two documents and the downloads", () => {
  it("lists both documents with their downloads and the draft bundle before signing", async () => {
    serve(view({ gate: gate(), documents: docs }));
    open();
    await waitFor(() => { // the panel renders in two steps; look again after each render instead of holding a stale element
      expect(screen.getByText(D.glossary)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: D.bundleDraft })).toBeInTheDocument();
    });
    expect(screen.getByText(D.catalogue)).toBeInTheDocument();
    expect(screen.getByText(D.draft)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: `${D.glossary}: ${D.excel}` })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: `${D.glossary}: ${D.print}` })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: `${D.catalogue}: ${D.excel}` })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: D.bundleDraft })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: D.bundle })).toBeNull();
  });
  it("the bundle button downloads the zip with the session, named by the server", async () => {
    const saved: (string | null)[] = [];
    serve(view({ gate: gate(), documents: docs }), audit(), (c) => (c.url.endsWith("/signoff/bundle") ? new Response("zip", { status: 200, headers: { "Content-Disposition": 'attachment; filename="draft-baseline.zip"' } }) : undefined));
    URL.createObjectURL = vi.fn(() => "blob:z");
    URL.revokeObjectURL = vi.fn();
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      saved.push(this.download);
    });
    open();
    await userEvent.click(await screen.findByRole("button", { name: D.bundleDraft }));
    await waitFor(() => expect(saved).toEqual(["draft-baseline.zip"]));
    expect(calls.some((c) => c.url === `${BASE}/signoff/bundle`)).toBe(true);
  });
  it("a refused download shows the server's plain sentence", async () => {
    serve(view({ gate: gate(), documents: docs }), audit(), (c) => (c.url.endsWith("/signoff/bundle") ? json(403, { error: "forbidden", message: "You do not have access to this." }) : undefined));
    open();
    await userEvent.click(await screen.findByRole("button", { name: D.bundleDraft }));
    expect(await screen.findByText("You do not have access to this.")).toBeInTheDocument();
  });
  it("once signed it says 'Signed: ready to build', names the signers and dates, shows the fingerprints and offers the signed bundle", async () => {
    const sigs = [
      { slot: "sponsor", label: "Sponsor", name: "Sam Sponsor", at: "2026-10-03T10:00:00+00:00" },
      { slot: "head_of_data", label: "Head of data", name: "Hana Head", at: "2026-10-04T10:00:00+00:00" },
    ];
    const sha = "a".repeat(64);
    serve(view({ status: "signed", signatures: sigs, waiting_for: [], gate: gate({ ok: true }), documents: [
      { ...docs[0]!, sha256: sha, built_at: "2026-10-04T10:00:00+00:00", unchanged: true },
      { ...docs[1]!, sha256: "b".repeat(64), built_at: "2026-10-04T10:00:00+00:00", unchanged: false }] }));
    open();
    expect(await screen.findByText(D.signed)).toBeInTheDocument();
    expect(screen.getByText(D.signedBy("Sam Sponsor", "Sponsor", "3 October 2026"))).toBeInTheDocument();
    expect(screen.getByText(D.signedBy("Hana Head", "Head of data", "4 October 2026"))).toBeInTheDocument();
    expect(screen.getByText(D.fingerprint(sha), { exact: false })).toBeInTheDocument();
    expect(screen.getByText(D.same)).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(D.changed);
    expect(screen.getByRole("button", { name: D.bundle })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Leave out/ })).toBeNull();
  });
  it("an older answer without a checklist or documents still draws the screen", async () => {
    serve(view());
    open();
    expect(await screen.findByText(T.readiness.ready)).toBeInTheDocument();
    expect(screen.queryByText(G.title)).toBeNull();
    expect(screen.queryByText(D.title)).toBeNull();
  });
});
