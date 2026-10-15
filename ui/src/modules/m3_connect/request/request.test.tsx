import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import App from "../../../App";
import { setSessionExpiredHandler } from "../../../api/client";
import type { Benchmarks, Intake, IntakeRequest } from "../intake/api";
import { requestText as t } from "./copy";

// The data request in the Intent Centre: five states, the cards in order, a restricted source, the counts. fetch is stubbed.

const BASE = "/api/modules/m3_connect";
const AID = "a".repeat(32);
const period = { from: "2026-09-01", to: "2026-09-30", label: "September 2026" };
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const src = (id: string, name: string, zone: string, restricted = false) => ({ id, name, restricted, kind: "spreadsheet", measures_fed: 1, impact: 0, readiness: 0, zone, zone_label: zone, marks: {}, summary: "", override: null });
const req = (over: Partial<IntakeRequest>): IntakeRequest => ({
  id: "r".repeat(32), source_id: "S2", source_name: "Custodian file", owner: "Owen", zone: "p1", period, tables: [], benchmarks: [], state: "arrived", link: "open",
  expires_at: "x", days_waiting: 0, reminders: [],
  profile: { period, files: [], gaps: [{ kind: "half_empty", text: "Fees is only 50% full.", measures: [] }],
    tables: [{ file: "f.csv", name: "Positions", row_count: 40, date_column: null, date_range: null, duplicate_key: null, columns: [{ name: "Fees", type: "number", fill: 0.5, match: null }] }] },
  ...over,
});
const intake = (over: Partial<Intake> = {}): Intake => ({ requests: [req({})], period, not_yet_asked: [{ source_id: "S1", source_name: "Performance workbook" }], summary: { asked: 1, arrived: 1 }, ...over });
const bench: Benchmarks = { file: null, measures: [{ measure_id: "K1", measure_name: "Net return", restricted: false, figure: 5, unit: "%", given_by: "Pat" }], unmatched: [], choices: [], waiting_for: [{ id: "K2", name: "Excess return" }] };

interface World { hold?: boolean; status?: number; intake?: Intake; sources?: unknown[]; signed?: boolean }
function mock(w: World) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Ana", company_id: "c", roles: ["analyst"] });
    if (url === "/api/company") return json(200, { company_id: "c", name: "Harbor Test Co", industry: "family_office" });
    if (url === "/api/modules") return json(200, []);
    if (url === `${BASE}/assessments/${AID}/intake/requests`) {
      if (w.hold) return new Promise<Response>(() => undefined);
      return w.status ? json(w.status, { error: w.status === 403 ? "forbidden" : "unreadable", message: "x" }) : json(200, w.intake ?? intake());
    }
    if (url === `${BASE}/assessments/${AID}/sources`) return json(200, { scored_at: "x", zones: {}, sources: w.sources ?? [src("S3", "Later feed", "unknown"), src("S2", "Custodian file", "p1"), src("S1", "Performance workbook", "p2"), src("S9", "A restricted source", "p2", true)] });
    if (w.signed && url === `${BASE}/assessments/${AID}/plan`) return json(200, { signed_at: "2026-10-04T10:00:00Z" });
    if (url === `${BASE}/assessments/${AID}/intake/benchmarks`) return json(200, bench);
    if (url === `${BASE}/assessments/${AID}/intake/sources/S2/profile`) return json(200, { profile: null, quality_rules: { K1: [{ id: "q1", kind: "fill_rate", text: "Fees must be 90% full.", state: "proposal" }], K2: [{ id: "q2", kind: "fill_rate", text: "Fees must be 90% full.", state: "proposal" }] } });
    return json(404, {});
  }));
}
const open = () => render(<MemoryRouter initialEntries={[`/centre/intent/truth/${AID}/request`]}><App /></MemoryRouter>);

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  sessionStorage.clear();
  setSessionExpiredHandler(null);
});

describe("data request in the Intent Centre", () => {
  test("loading", async () => {
    mock({ hold: true });
    open();
    expect(await screen.findByRole("status")).toHaveTextContent("Loading");
  });
  test("empty", async () => {
    mock({ intake: intake({ requests: [], not_yet_asked: [], summary: { asked: 0, arrived: 0 } }), sources: [] });
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
    expect(await screen.findByRole("alert")).toHaveTextContent("You do not have access to this. Ask your administrator.");
  });
  test("populated: counts, plan order, states, buttons, profile, quality rules, missing list", async () => {
    mock({});
    open();
    expect(await screen.findByText(t.counts(1, 1, 1))).toBeInTheDocument();
    expect(screen.getByText("Intent Centre")).toBeInTheDocument();
    const heads = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(heads.indexOf("Custodian file")).toBeLessThan(heads.indexOf("Performance workbook"));
    expect(heads.indexOf("Performance workbook")).toBeLessThan(heads.indexOf("Later feed"));
    const card = screen.getByRole("heading", { name: "Custodian file" }).closest("section") as HTMLElement;
    expect(within(card).getByText(t.state.profiled)).toBeInTheDocument();
    expect(within(card).getByText(t.owner("Owen"))).toBeInTheDocument();
    expect(within(card).getByText(t.profileRows(40))).toBeInTheDocument();
    expect(await within(card).findAllByText("Fees must be 90% full.")).toHaveLength(1);
    const fresh = screen.getByRole("heading", { name: "Performance workbook" }).closest("section") as HTMLElement;
    expect(within(fresh).getByRole("button", { name: t.send })).toBeInTheDocument();
    const missing = screen.getByRole("heading", { name: t.missingTitle }).closest("section") as HTMLElement;
    expect(within(missing).getByText(t.notAsked("Performance workbook"))).toBeInTheDocument();
    expect(within(missing).getByText(t.benchWaiting("Excess return"))).toBeInTheDocument();
    expect(within(missing).getByText(t.gap("Custodian file", "Fees is only 50% full."))).toBeInTheDocument();
  });
  test("a signed plan closes the request: no send, remind or upload", async () => {
    mock({ signed: true, intake: intake({ requests: [req({ state: "sent", profile: null })], summary: { asked: 1, arrived: 0 } }) });
    open();
    expect(await screen.findByText(t.locked)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.remind })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.send })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.upload })).not.toBeInTheDocument();
  });
  test("a waiting source offers Remind", async () => {
    mock({ intake: intake({ requests: [req({ state: "sent", profile: null })], summary: { asked: 1, arrived: 0 } }) });
    open();
    const card = (await screen.findByRole("heading", { name: "Custodian file" })).closest("section") as HTMLElement;
    expect(within(card).getByRole("button", { name: t.remind })).toBeInTheDocument();
  });
  test("a restricted source shows no name, owner or button", async () => {
    mock({ intake: intake({ requests: [req({ owner: "Secret Sam" })] }) });
    open();
    const el = (await screen.findByText(t.restrictedSource)).closest("article") as HTMLElement;
    expect(within(el).queryByRole("button")).toBeNull();
    expect(el).not.toHaveTextContent("Secret Sam");
    expect(el).not.toHaveTextContent("Owner");
  });
});
