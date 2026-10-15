import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import App from "../../../App";
import { setSessionExpiredHandler } from "../../../api/client";
import { truthText as t } from "./copy";

// The Moment of truth in five states, the result pills, the restricted row, the two signer states and the crumbs. fetch is stubbed.

const BASE = "/api/modules/m3_connect";
const AID = "a".repeat(32);
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const rows = [
  { measure: "K1", name: "Net return", restricted: false, our_figure: 1, their_figure: 1, unit: "%", result: "matches" },
  { measure: "K2", name: "Manager performance", restricted: false, our_figure: 0.63, their_figure: 0.67, unit: "%", result: "gap", likely_reason: "Your figure leaves out fees. Fix: fees from the ledger." },
  { measure: "K3", name: "Excess return", restricted: false, our_figure: null, their_figure: 1.2, result: "cannot", missing: "Index levels missing." },
  { measure: "K4", name: "Secret pay", restricted: true },
];
const sig = (slot: string, label: string) => ({ slot, label, name: "Pat", at: "2026-10-04T10:00:00Z", restricted_covered: 0, note: null });
const risk = (kind: string, state: string) => ({ id: `${kind}${Math.random()}`, kind, text: "x", restricted: false, measures: [], pain_points: [], state, decision: null });
const plan = (sigs: unknown[]) => ({
  drafted: true, waiting: null, drafted_at: null, signed_at: null, outcome_id: null, signatures: sigs, waiting_for: [], risks_undecided: 0, can_sign: true, restricted_hidden: 0, effort: {},
  bands_info: { now: { label: "Weeks 0-3", weeks: "" }, next: { label: "Weeks 3-8", weeks: "" }, later: { label: "Week 8 and later", weeks: "" } },
  bands: { now: [{ key: "i1", band: "now", restricted: false, summary: "Connect the custodian file", measures: [{ id: "K1", name: "Net return" }], pain_points: [], team: ["Ana"], blocked_by: [], who_unblocks: [] }],
    next: [{ key: "i2", band: "next", restricted: false, summary: "x", measures: [{ id: "K2", name: "Manager performance" }], pain_points: [], team: [], blocked_by: ["Fees from the ledger."], who_unblocks: [] },
      { key: "i3", band: "next", restricted: true, summary: "A restricted measure", measures: [{ id: "K3", name: "Excess return" }], pain_points: [], team: [], blocked_by: [], who_unblocks: [] }], later: [] },
  viewer: { name: "Pat", slot: "sponsor", can_edit: true },
});

interface World { hold?: boolean; status?: number; empty?: boolean; sigs?: unknown[]; full?: boolean; signed?: boolean }
const puts: { url: string; body: string }[] = [];
function mock(w: World) {
  puts.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "PUT") { puts.push({ url, body: String(init.body) }); return json(200, { source: {} }); }
    if (url === "/api/auth/me") return json(200, { display_name: "Ana", company_id: "c", roles: ["analyst"] });
    if (url === "/api/company") return json(200, { company_id: "c", name: "Harbor Test Co", industry: "family_office" });
    if (url === "/api/modules") return json(200, []);
    if (url === `${BASE}/assessments/${AID}/trial`) {
      if (w.hold) return new Promise<Response>(() => undefined);
      if (w.status) return json(w.status, { error: w.status === 403 ? "forbidden" : "unreadable", message: "x" });
      return json(200, { compiled: !w.empty, run: !w.empty, measures: w.empty ? [] : rows });
    }
    if (url === `${BASE}/assessments/${AID}/plan`) return json(200, w.signed ? { ...plan(w.sigs ?? []), signed_at: "2026-10-04T10:00:00Z", viewer: { name: "Pat", slot: null, can_edit: false } } : plan(w.sigs ?? []));
    if (url === `${BASE}/assessments/${AID}/risks`) return json(200, { risks: [risk("risk", "accepted"), risk("risk", "accepted"), risk("unknown", "accepted"), risk("risk", "open")], counts: { open: 0, accepted: 3, sent_back: 0, rechecked: 0 }, signed: false, locked: false, ready: true });
    if (w.full && url === `${BASE}/assessments/${AID}/sources`) return json(200, { scored_at: "x", zones: {}, sources: [
      { id: "S1", name: "Custodian file", restricted: false, kind: "spreadsheet", measures_fed: 2, impact: 0.6, readiness: 0.7, zone: "p1", zone_label: "", marks: {}, summary: "", override: null },
      { id: "S2", name: "Index feed", restricted: false, kind: "outside feed", measures_fed: 1, impact: 0.4, readiness: -0.5, zone: "unknown", zone_label: "", marks: {}, summary: "", override: null }] });
    if (w.full && url === `${BASE}/assessments/${AID}/intake/requests`) return json(200, { requests: [], from_profile: [{ source_id: "S1", source_name: "Custodian file", from: "profile", files: ["a.csv", "b.csv"] }],
      period: { from: "2026-09-01", to: "2026-09-30", label: "September 2026" }, not_yet_asked: [], summary: { asked: 0, arrived: 0 } });
    return json(404, {});
  }));
}
const open = () => render(<MemoryRouter initialEntries={[`/centre/intent/truth/${AID}`]}><App /></MemoryRouter>);

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  sessionStorage.clear();
  setSessionExpiredHandler(null);
});

describe("moment of truth", () => {
  test("the data request link goes to the Intent Centre request screen", async () => {
    mock({});
    open();
    expect(await screen.findByRole("link", { name: t.dataRequest })).toHaveAttribute("href", `/centre/intent/truth/${AID}/request`);
    expect(screen.queryByText(/legacy/i)).not.toBeInTheDocument();
  });
  test("loading", async () => {
    mock({ hold: true });
    open();
    expect(await screen.findByRole("status")).toHaveTextContent("Loading");
  });
  test("empty", async () => {
    mock({ empty: true });
    open();
    expect(await screen.findByText(t.empty)).toBeInTheDocument();
  });
  test("error", async () => {
    mock({ status: 500 });
    open();
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
  test("refused", async () => {
    mock({ status: 403 });
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent("You do not have access");
  });
  test("populated: pills, restricted row, crumbs, plan, signer states", async () => {
    mock({ sigs: [sig("sponsor", "Sponsor")] });
    open();
    const row = (await screen.findByText("K2 Manager performance", { selector: "td strong" })).closest("tr")!;
    expect(within(row).getByText(t.pill.gap)).toBeInTheDocument();
    expect(within(screen.getByText("K1 Net return", { selector: "td strong" }).closest("tr")!).getByText(t.pill.matches)).toBeInTheDocument();
    const cannot = screen.getByText("K3 Excess return", { selector: "td strong" }).closest("tr")!;
    expect(within(cannot).getByText(t.pill.cannot)).toBeInTheDocument();
    expect(within(cannot).getByText(t.notYet)).toBeInTheDocument();
    const hr = screen.getByText(t.restricted).closest("tr")!;
    expect(within(hr).getByText(t.pill.restricted)).toBeInTheDocument();
    expect(screen.queryByText("Secret pay")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: t.crumbs[0] })).toHaveAttribute("href", "/centre/intent");
    expect(screen.getByText(t.feeds(["K1"], t.ready))).toBeInTheDocument();
    expect(screen.getByText(t.feeds(["K2"], "Fees from the ledger."))).toBeInTheDocument();
    expect(screen.getByText(t.feeds(["K3"], t.viaSource))).toBeInTheDocument();
    expect(screen.getByText(t.viaSourceCount(1))).toBeInTheDocument();
    expect(screen.getAllByText(t.emptyBand)).toHaveLength(1);
    expect(screen.getByText(t.risksLine(2, 0, 1, 0))).toBeInTheDocument();
    expect(screen.getByText(/Signed by Pat, Sponsor/)).toBeInTheDocument();
    expect(screen.getByText("Waiting for Head of data")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: t.signButton })).toBeInTheDocument();
  });
  test("a signed plan shows both names, offers no second signature and no new trial run", async () => {
    mock({ signed: true, sigs: [sig("sponsor", "Sponsor"), sig("head_of_data", "Head of data")] });
    open();
    expect(await screen.findByText(/Signed by Pat, Head of data/)).toBeInTheDocument();
    expect(screen.getByText(/Signed by Pat, Sponsor/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.signButton })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.run })).not.toBeInTheDocument();
  });
  test("tiles, header, source map and the table with the fix in amber, from a mock", async () => {
    mock({ full: true });
    open();
    const tiles = await screen.findByRole("region", { name: t.title });
    for (const r of ["matches", "gap", "cannot"] as const) {
      expect(within(tiles).getByText(t.tiles[r].label).closest(".ds-stat")).toHaveTextContent(`${t.tiles[r].label}1${t.tiles[r].note}`);
    }
    expect(within(tiles).getByText(t.restrictedCount(1))).toBeInTheDocument();
    expect(screen.getByText(t.header("September 2026", 2, 2))).toBeInTheDocument();
    const map = screen.getByRole("group", { name: t.mapLabel });
    expect(within(map).getByRole("img", { name: `Custodian file: ${t.zones.p1}` })).toBeInTheDocument();
    expect(within(map).getByRole("img", { name: `Index feed: ${t.zones.unknown}` })).toBeInTheDocument();
    const table = screen.getByRole("region", { name: t.tableTitle });
    for (const h of Object.values(t.head)) expect(within(table).getByRole("columnheader", { name: h })).toBeInTheDocument();
    const gap = within(table).getByText("K2 Manager performance").closest("tr")!;
    expect(within(gap).getByText("0.67 %")).toBeInTheDocument();
    expect(within(gap).getByText("0.63 %")).toBeInTheDocument();
    expect(within(gap).getByText("Fix: fees from the ledger.")).toHaveClass("ds-warn");
  });
  test("an admin moves a source with the keys and says why; the move is saved", async () => {
    mock({ full: true });
    open();
    const dot = await screen.findByRole("img", { name: `Custodian file: ${t.zones.p1}` });
    dot.focus();
    await userEvent.keyboard("{ArrowLeft}{ArrowLeft}{ArrowLeft}{ArrowLeft}{ArrowLeft}{ArrowLeft}{ArrowLeft}{ArrowLeft}");
    expect(screen.getByText(t.moveTo("Custodian file", t.zones.unknown))).toBeInTheDocument();
    await userEvent.type(screen.getByRole("textbox", { name: t.moveReason }), "No owner named yet");
    await userEvent.click(screen.getByRole("button", { name: t.moveSave }));
    await waitFor(() => expect(puts).toHaveLength(1));
    expect(puts[0]?.url).toBe(`${BASE}/assessments/${AID}/sources/S1/override`);
    expect(JSON.parse(puts[0]?.body ?? "{}")).toEqual({ impact: 0.6, readiness: -0.1, reason: "No owner named yet" });
  });
});
