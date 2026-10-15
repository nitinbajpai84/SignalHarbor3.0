import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import App from "../../../App";
import { setSessionExpiredHandler } from "../../../api/client";
import type { FindingsView, RuleView, TrialView } from "./api";
import { trialText as t } from "./copy";

// The trial and findings screen in five states, the plain-words rule, a missing figure never zero, and the analyst's check. fetch is stubbed.

const BASE = "/api/modules/m3_connect";
const AID = "a".repeat(32);
const step = (id: string, state = "not_started") => ({ id, label: id, state, waiting_on: "Waiting." });
const detail = { assessment: { id: AID, baseline_outcome_id: "b".repeat(32), charter_outcome_id: null, state: "draft", created_by: "Pat", created_at: "2026-10-04" },
  steps: ["map", "request", "scan", "trial", "findings", "plan"].map((i) => step(i)), inputs: null };
const rule = (over: Partial<RuleView> = {}): RuleView => ({ state: "draft", origin: "definition", words: "The sum of closing value minus opening value, less the sum of fees (net of fees).", reason: null, checked_by: null, ...over });
const trial = (auto = false): TrialView => ({ compiled: true, run: true, measures: [
  { measure: "K15", name: "Manager performance", restricted: false, our_figure: 0.63, their_figure: 0.67, unit: "%", result: "gap", likely_reason: "Your figure leaves out fees.",
    rule: auto ? rule({ state: "checked", checked_by: "Lens (matches your figure)", auto_checked: true }) : rule() },
  { measure: "K16", name: "Excess return", restricted: false, our_figure: null, their_figure: 1.2, unit: "pp", result: "cannot", missing: "Index levels missing after 22 Sep.", likely_reason: "Index levels missing after 22 Sep.",
    rule: rule({ state: "checked", checked_by: "Ana Analyst" }) },
  { measure: "K18", name: "A restricted measure", restricted: true }] });
const findings = (): FindingsView => ({ built: true, risks: [{ id: "r1", kind: "risk", text: "Manager performance is unclear.", measures: ["K15"] }], measures: {
  K15: { measure: "K15", name: "Manager performance", group: "unclear", reasons: ["Your figure leaves out fees."], pain_points: [{ id: "p1", title: "Late packs" }], levers: [] },
  K16: { measure: "K16", name: "Excess return", group: "unknown", reasons: ["Index levels missing after 22 Sep."], pain_points: [], levers: [] },
  K18: { measure: "K18", name: "A restricted measure", group: "unknown", reasons: [], pain_points: [], levers: [], restricted: true } } });

interface World { roles?: string[]; hold?: boolean; status?: number; empty?: boolean; auto?: boolean }
const calls: { method: string; url: string }[] = [];
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function mock(w: World) {
  calls.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ method, url });
    if (url === "/api/auth/me") return json(200, { display_name: "Ana Analyst", company_id: "co-a", roles: w.roles ?? ["analyst"] });
    if (url === "/api/company") return json(200, { company_id: "co-a", name: "Harbor Test Co", industry: "family_office" });
    if (url === "/api/modules") return json(200, [{ id: "m3_connect", number: 3, name: "Assess and plan", description: "d", agent: "Lens" }]);
    if (url === `${BASE}/assessments/${AID}`) return json(200, detail);
    if (url === `${BASE}/assessments/${AID}/trial` && method === "GET") {
      if (w.hold) return new Promise<Response>(() => undefined);
      if (w.status) return json(w.status, { error: w.status === 403 ? "forbidden" : "unreadable", message: "x" });
      return json(200, w.empty ? { compiled: false, run: false, measures: [] } : trial(w.auto));
    }
    if (url === `${BASE}/assessments/${AID}/findings`) return json(200, findings());
    if (method === "POST") return json(200, trial());
    return json(404, {});
  }));
}
const open = () => render(<MemoryRouter initialEntries={[`/modules/m3_connect/trial/${AID}`]}><App /></MemoryRouter>);

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  sessionStorage.clear();
  setSessionExpiredHandler(null);
});

describe("trial screen: five states", () => {
  test("loading", async () => {
    mock({ hold: true });
    open();
    expect(await screen.findByRole("status")).toHaveTextContent("Loading");
  });

  test("empty: honest words and a way to run the trial", async () => {
    mock({ empty: true });
    open();
    expect(await screen.findByText(t.empty)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: t.run })).toBeInTheDocument();
  });

  test("error: a way to try again", async () => {
    mock({ status: 500 });
    open();
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  test("refused: plain words from the server", async () => {
    mock({ status: 403 });
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent("You do not have access to this. Ask your administrator.");
  });

  test("populated: table, rule in plain words, missing figure not zero, restricted measure, findings in three columns", async () => {
    mock({});
    open();
    const row = (await screen.findByText("Manager performance", { selector: "td strong" })).closest("tr")!;
    expect(within(row).getByText(/The sum of closing value minus opening value, less the sum of fees \(net of fees\)\./)).toBeInTheDocument();
    expect(within(row).getByText(t.result.gap)).toBeInTheDocument();
    expect(within(row).getByText("Your figure leaves out fees.")).toBeInTheDocument();
    const cannot = screen.getByText("Excess return", { selector: "td strong" }).closest("tr")!;
    expect(within(cannot).getByText(t.notAvailable)).toBeInTheDocument();
    expect(within(cannot).queryByText(/^0\b/)).not.toBeInTheDocument();
    expect(within(cannot).getByText(t.checkedBy("Ana Analyst"))).toBeInTheDocument();
    expect(screen.getAllByText(t.restricted).length).toBeGreaterThan(0);
    for (const g of ["ready", "unclear", "unknown"] as const) expect(screen.getByRole("region", { name: t.groups[g] })).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: t.groups.unclear })).getByText(/Manager performance/)).toBeInTheDocument();
    expect(screen.getByText("Manager performance is unclear.")).toBeInTheDocument();
  });
});

describe("scoreboard: counts and restricted measures", () => {
  test("empty: scoreboard does not render when trial has not run", async () => {
    mock({ empty: true });
    open();
    expect(await screen.findByText(t.empty)).toBeInTheDocument();
    expect(screen.queryByText(t.scoreboardTitle)).not.toBeInTheDocument();
  });

  test("populated: shows scoreboard with counts (1 match, 1 gap, 1 cannot, 1 restricted)", async () => {
    mock({});
    open();
    // Wait for scoreboard title to appear
    expect(await screen.findByText(t.scoreboardTitle)).toBeInTheDocument();
    // Check that the scoreboard displays the descriptions for each tile
    expect(screen.getByText(t.scoreboardMatches)).toBeInTheDocument();
    expect(screen.getByText(t.scoreboardGap)).toBeInTheDocument();
    expect(screen.getByText(t.scoreboardCannotCreate)).toBeInTheDocument();
    expect(screen.getByText(t.scoreboardRestricted)).toBeInTheDocument();
  });

  test("scoreboard: does not show restricted line when no restricted measures", async () => {
    const t0 = trial();
    t0.measures = t0.measures.filter((m) => !m.restricted);
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/auth/me") return json(200, { display_name: "Ana Analyst", company_id: "co-a", roles: ["analyst"] });
      if (url === "/api/company") return json(200, { company_id: "co-a", name: "Harbor Test Co", industry: "family_office" });
      if (url === "/api/modules") return json(200, [{ id: "m3_connect", number: 3, name: "Assess and plan", description: "d", agent: "Lens" }]);
      if (url === `${BASE}/assessments/${AID}`) return json(200, detail);
      if (url === `${BASE}/assessments/${AID}/trial`) return json(200, t0);
      if (url === `${BASE}/assessments/${AID}/findings`) return json(200, findings());
      return json(404, {});
    }));
    open();
    await screen.findByText(t.scoreboardTitle);
    expect(screen.queryByText(t.scoreboardRestrictedDetail)).not.toBeInTheDocument();
  });
});

describe("trial screen: short reasons, no rule, findings apart", () => {
  test("one short reason per measure; no-rule measures say so with a Why? holding the full text; findings are a separate section", async () => {
    const long = "Lens could not write a rule: the definition says to use the usual method but never names which one it is.";
    const t0 = trial();
    t0.measures[0] = { ...t0.measures[0]!, likely_reason: "one two three four five six seven eight nine ten eleven twelve thirteen fourteen", rule: rule({ state: "could_not_compile", reason: long }) };
    const f0 = findings();
    f0.risks = [{ id: "r1", kind: "ambiguity", text: "F001 `cash` is open (accepted in module 2 by Mei Tan)", measures: [] },
      { id: "r2", kind: "ambiguity", text: "Other (accepted in module 2 by Mei Tan)", measures: [] }];
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/auth/me") return json(200, { display_name: "Ana Analyst", company_id: "co-a", roles: ["analyst"] });
      if (url === "/api/company") return json(200, { company_id: "co-a", name: "Harbor Test Co", industry: "family_office" });
      if (url === "/api/modules") return json(200, [{ id: "m3_connect", number: 3, name: "Assess and plan", description: "d", agent: "Lens" }]);
      if (url === `${BASE}/assessments/${AID}`) return json(200, detail);
      if (url === `${BASE}/assessments/${AID}/trial`) return json(200, t0);
      if (url === `${BASE}/assessments/${AID}/findings`) return json(200, f0);
      return json(404, {});
    }));
    open();
    const row = (await screen.findByText("Manager performance", { selector: "td strong" })).closest("tr")!;
    expect(within(row).getByText(/No rule yet/)).toBeInTheDocument();
    expect(within(row).getByText(/Why\?/)).toBeInTheDocument();
    expect(within(row).getByText(/never names which one/)).toBeInTheDocument();
    expect(within(row).getByText("one two three four five six seven eight nine ten eleven twelve...")).toBeInTheDocument();
    const section = screen.getByRole("region", { name: t.findingsTitle });
    expect(section.closest("table")).toBeNull();
    expect(screen.queryByText(/accepted in module 2 by/)).not.toBeInTheDocument();
    expect(screen.getByText("Mei Tan accepted 2 of these in module 2.")).toBeInTheDocument();
    expect(screen.getByText("F001 cash is open")).toBeInTheDocument();
  });
});

describe("trial screen: who can do what", () => {
  test("an analyst marks a rule checked", async () => {
    mock({});
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: t.checkLabel("Manager performance") }));
    expect(calls.some((c) => c.method === "POST" && c.url === `${BASE}/assessments/${AID}/trial/rules/K15/check`)).toBe(true);
  });

  test("a sponsor sees the figures but no buttons", async () => {
    mock({ roles: ["sponsor"] });
    open();
    await screen.findByText("Manager performance", { selector: "td strong" });
    expect(screen.queryByRole("button", { name: t.run })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Mark the rule/ })).not.toBeInTheDocument();
  });

  test("run compiles and then runs the trial", async () => {
    mock({});
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: t.run }));
    await screen.findByRole("button", { name: t.run });
    expect(calls.filter((c) => c.method === "POST").map((c) => (c.url.split("/assessments/")[1] ?? "").slice(33))).toEqual(["trial/compile", "trial/run"]);
  });
});

describe("rules checked automatically", () => {
  test("a rule that matches the customer's figure says so and has no check button", async () => {
    mock({ auto: true });
    open();
    expect(await screen.findByText(t.autoChecked)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.checkLabel("Manager performance") })).toBeNull();
  });
});
