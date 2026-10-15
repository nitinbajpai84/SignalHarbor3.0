import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import type { Kpi, KpiFull, Prov, WorkList } from "../modules/m2_baseline/api";
import { SessionProvider } from "../useSession";
import BaselinePage from "./BaselinePage";

const BID = "a".repeat(32);
const BASE = `/api/modules/m2_baseline/baselines/${BID}`;
const prov = (value: string | null, mark: Prov["mark"], by = "Lens", from = ""): Prov => ({ value, mark, by, from, at: "2026-10-03T10:00:00+00:00" });
const none = prov(null, "unknown");
const kpi = (id: string, name: string, def: Prov, over: Partial<KpiFull> = {}): KpiFull => ({
  id, name, restricted: false, state: "drafted", problem_ids: [], priority: "must", definition: def,
  owners: { business: none, data: none, process: none }, governance: { personal: "no", sensitive: false, may_see: [] },
  tracking: none, producer: none, gathered: none, questions: [], definition_proposal: null,
  triage: { definition: def, owner: none, producer: none, gathered: none, unknown: [] }, missing_owners: [], treated_as_personal: false, ...over,
});
const wl = (kpis: Kpi[]): WorkList => ({
  baseline: { id: BID, charter_outcome_id: null, state: "draft", created_at: "2026-10-03T10:00:00+00:00" }, charter: null, problems: [], kpis,
  suggestions: [], suggestion_label: "", pack: { available: true, label: "Family office" }, owners_complete: 0, lens_available: false,
});
const json = (b: unknown) => new Response(JSON.stringify(b), { status: 200, headers: { "Content-Type": "application/json" } });
const calls: { method: string; url: string; body: unknown }[] = [];

function mock(w: WorkList | null, governed?: unknown, parts?: unknown) {
  calls.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    if (url === "/api/auth/me") return json({ display_name: "Pat Owner", company_id: "co-a", roles: ["company_admin"] });
    if (url === BASE) return w ? json(w) : new Response(JSON.stringify({ error: "forbidden" }), { status: 403, headers: { "Content-Type": "application/json" } });
    if (parts && url === `${BASE}/my-parts`) return json(parts);
    if (method === "POST" && url === `${BASE}/confirm`) return json({});
    if (governed && url === `${BASE}/governed`) return json(governed);
    if (method === "PUT" && url.endsWith("/triage")) return json(w);
    return new Response("{}", { status: 404, headers: { "Content-Type": "application/json" } });
  }));
}
const open = (q = "") => render(<MemoryRouter initialEntries={[`/centre/intent/baseline/${BID}${q}`]}><SessionProvider><Routes><Route path="/centre/intent/baseline/:baselineId" element={<BaselinePage />} /></Routes></SessionProvider></MemoryRouter>);
afterEach(() => { vi.unstubAllGlobals(); sessionStorage.clear(); });

describe("baseline page", () => {
  test("lists measures with status and hides a restricted one's content", async () => {
    mock(wl([kpi("K1", "Capital calls due", prov("d", "guessed")), kpi("K2", "Cash held", prov("d", "stated")), kpi("K3", "Fees paid", prov("d", "stated"), { state: "signed", priority: "should" }),
      { id: "K4", name: "Salary bands", restricted: true, state: "drafted" }]));
    open();
    expect(await screen.findByRole("button", { name: "Open: Capital calls due" })).toBeInTheDocument();
    expect(screen.getByText("Drafted by Lens")).toBeInTheDocument();
    expect(screen.getByText("Confirmed")).toBeInTheDocument();
    expect(screen.getByText("Governed")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Open: Salary bands" })).not.toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "Should" }));
    expect(screen.queryByRole("button", { name: "Open: Capital calls due" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open: Fees paid" })).toBeInTheDocument();
  });

  test("open one measure and confirm its definition", async () => {
    mock(wl([kpi("K1", "Capital calls due", prov("Calls still to be paid", "guessed", "the pack"))]));
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: "Open: Capital calls due" }));
    await user.click(await screen.findByRole("button", { name: "Confirm" }));
    const put = calls.find((c) => c.method === "PUT" && c.url === `${BASE}/kpis/K1/triage`);
    expect(put?.body).toEqual({ definition: { text: "Calls still to be paid", mark: "stated" } });
  });

  test("a guessed value shows its source", async () => {
    mock(wl([kpi("K1", "Capital calls due", prov("Calls still to be paid", "guessed", "the pack", "Lakeside industry pack"))]));
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: "Open: Capital calls due" }));
    expect((await screen.findAllByText(/from Lakeside industry pack/)).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/^Guessed · by the pack/).length).toBeGreaterThan(0);
  });

  test("an owner landing on their measure confirms the guessed definition in one click", async () => {
    mock(wl([kpi("K1", "Capital calls due", prov("d", "stated")), kpi("K2", "Fees charged", prov("Fees taken by each manager", "guessed", "Lens", "fee schedule"))]));
    const user = userEvent.setup();
    open("?measure=K2");
    const measure = await screen.findByRole("region", { name: "Measure: Fees charged" });
    expect(measure).toHaveTextContent("Guessed · by Lens · from fee schedule");
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    const puts = calls.filter((c) => c.method === "PUT");
    expect(puts).toHaveLength(1);
    expect(puts[0]).toMatchObject({ url: `${BASE}/kpis/K2/triage`, body: { definition: { text: "Fees taken by each manager", mark: "stated" } } });
  });

  test("governed state counts only stated fields from the record and shows values in words", async () => {
    const c = (value: unknown, mark: string) => ({ value, mark });
    const state = { owners: c({ business: "Daniel", data: "Harvey", process: null }, "stated"), classification: c("open", "stated"), may_see: c(["CIO", "Fund Ops"], "stated"),
      resolving: c({ team: "Fund Ops", target_week: 8 }, "guessed"), affects: c(null, "unknown"), review_date: c("2027-01-01", "stated") };
    mock(wl([kpi("K1", "Capital calls due", prov("d", "stated"))]), { measures: [{ id: "K1", name: "Capital calls due", state, governed: false, missing: ["resolving", "affects"] }], percentages: {} });
    open("?measure=K1");
    expect(await screen.findByText(/Governed state · 4 of 6/)).toBeInTheDocument();
    expect(screen.getByText("Business: Daniel · Data: Harvey")).toBeInTheDocument();
    expect(screen.getByText("Fund Ops, by week 8")).toBeInTheDocument();
    expect(screen.getAllByText("Not available yet").length).toBeGreaterThan(0);
    expect(screen.queryByText(/object Object/)).toBeNull();
  });

  test("an owner refused the work list confirms their own definition part", async () => {
    mock(null, undefined, { status: "open", parts: [{ kpi_id: "K1", kpi_name: "Fund return", part: "definition", label: "Definition", confirmed: false }] });
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: "Confirm my part: Fund return: Definition" }));
    expect(calls.find((c) => c.method === "POST" && c.url === `${BASE}/confirm`)?.body).toEqual({ kpi_id: "K1", part: "definition" });
  });
});
