import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import App from "../../../App";
import { setSessionExpiredHandler } from "../../../api/client";
import type { MapSource, SourceMapData, SourcePanelData } from "../api";
import { BASE } from "../api";
import { mapCopy as t } from "./copy";

const AID = "a".repeat(32);
const steps = (["map", "request", "scan", "trial", "findings", "plan"] as const).map((id) => ({ id, label: id, state: "not_started" as const, waiting_on: "Waiting." }));
const src = (o: Partial<MapSource>): MapSource => ({
  id: "S1", name: "Custodian portal", restricted: false, kind: "system", measures_fed: 2, impact: 0.5, readiness: 0.4, zone: "p1",
  zone_label: "Ready to scan, priority 1", marks: { effort: "medium" }, summary: "Ready and matters.", override: null, draft: { impact: 0.5, readiness: 0.4 }, ...o,
});
const MAP: SourceMapData = {
  scored_at: "now", zones: { p1: "", p2: "", identify: "", unknown: "" },
  sources: [
    src({}),
    src({ id: "S2", name: "Email inbox", kind: "email", impact: -0.5, readiness: -0.4, zone: "identify", measures_fed: 1, marks: { blocked_upstream: true, effort: "large" } }),
    src({ id: "S3", name: "A restricted source", restricted: true, kind: "hidden", measures_fed: 1, zone: "unknown", impact: 0.3, readiness: -0.3, marks: { restricted: true }, summary: "" }),
    src({ id: "S4", name: "Pricing feed", kind: "outside feed", impact: -0.2, readiness: 0.6, zone: "p2", override: { impact: -0.2, readiness: null, reason: "Contract signed", by: "Pat Owner", at: "x" } }),
  ],
};
const PANEL: SourcePanelData = {
  source: MAP.sources[0]!, tables: [{ name: "Calls table", kind: "Table", fields: [{ name: "notice_date", meaning: "When it was sent", type: "Date" }] }],
  measures: [{ id: "K1", name: "Capital call timeliness", priority: "Must", owners: { data: "Dee Owner" } }], missing: ["A sample of the data"],
  impact_reasons: [{ text: "It feeds 2 measures.", effect: "raises" }], readiness_reasons: [{ text: "No sample has been given yet.", effect: "lowers" }],
};

interface World { map?: SourceMapData; mapStatus?: number; hold?: boolean; panel?: SourcePanelData; panelStatus?: number; putStatus?: number }
const calls: { method: string; url: string; body?: string }[] = [];
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function mock(w: World) {
  calls.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ method, url, body: init?.body as string | undefined });
    if (url === "/api/auth/me") return json(200, { display_name: "Pat Owner", company_id: "co-a", roles: ["company_admin"] });
    if (url === "/api/company") return json(200, { company_id: "co-a", name: "Harbor Test Co", industry: "family_office" });
    if (url === "/api/modules") return json(200, [{ id: "m3_connect", number: 3, name: "Assess and plan", description: "d", agent: "Lens" }]);
    if (url === `${BASE}/assessments/${AID}`) return json(200, { assessment: { id: AID }, steps, inputs: null });
    if (url === `${BASE}/assessments/${AID}/sources` && method === "GET") {
      if (w.hold) return new Promise<Response>(() => undefined);
      return w.mapStatus ? json(w.mapStatus, { error: w.mapStatus === 403 ? "forbidden" : "x", message: "Please ask your administrator." }) : json(200, w.map ?? MAP);
    }
    if (url.endsWith("/sources/score")) return json(200, MAP);
    if (url.endsWith("/override")) return w.putStatus ? json(w.putStatus, { error: "bad", message: "Please say why." }) : json(200, { source: MAP.sources[0] });
    if (url.startsWith(`${BASE}/assessments/${AID}/sources/`)) return w.panelStatus ? json(w.panelStatus, { error: "x", message: "m" }) : json(200, w.panel ?? PANEL);
    return json(404, {});
  }));
}
const open = () => render(<MemoryRouter initialEntries={[`/modules/m3_connect/map/${AID}`]}><App /></MemoryRouter>);

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  sessionStorage.clear();
  setSessionExpiredHandler(null);
});

describe("source map: five states", () => {
  test("loading", async () => {
    mock({ hold: true });
    open();
    expect(await screen.findByRole("status")).toHaveTextContent("Loading");
  });
  test("empty company: honest words", async () => {
    mock({ map: { ...MAP, sources: [] } });
    open();
    expect(await screen.findByText(t.empty)).toBeInTheDocument();
  });
  test("error: one sentence and a way to try again", async () => {
    mock({ mapStatus: 500 });
    open();
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
  test("refused: plain words", async () => {
    mock({ mapStatus: 403 });
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent("You do not have access to this. Ask your administrator.");
  });
  test("populated: a dot per source, a legend, and each zone listed as text", async () => {
    mock({});
    open();
    const chart = await screen.findByRole("group", { name: t.chartLabel });
    expect(within(chart).getAllByRole("button")).toHaveLength(4);
    expect(within(chart).getByRole("button", { name: t.open("A restricted source") })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: t.legendTitle })).toHaveTextContent(t.legendLock);
    const zone = screen.getByRole("region", { name: t.zones.identify });
    expect(within(zone).getByText("Email inbox")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: t.zones.p2 })).getByText(/Moved by Pat Owner/)).toBeInTheDocument();
    expect(screen.queryByText("Custodian portal", { selector: "li *" })).toBeInTheDocument();
  });
});

describe("crowded dots", () => {
  test("overlapping dots are spread, labels are limited and never take the click, and a dot still opens its panel", async () => {
    const crowd = Array.from({ length: 9 }, (_, i) => src({ id: `C${i}`, name: `Crowd ${i}`, impact: 0.5, readiness: 0.4, measures_fed: i + 1 }));
    mock({ map: { ...MAP, sources: crowd } });
    const user = userEvent.setup();
    const { container } = open();
    await screen.findByRole("button", { name: t.open("Crowd 0") });
    const dots = Array.from(container.querySelectorAll("svg g[role=button] > circle:first-of-type"));
    const at = dots.map((c) => [Number(c.getAttribute("cx")), Number(c.getAttribute("cy")), Number(c.getAttribute("r"))] as const);
    expect(at).toHaveLength(9);
    for (let i = 0; i < at.length; i++) for (let j = i + 1; j < at.length; j++) {
      expect(Math.hypot(at[i]![0] - at[j]![0], at[i]![1] - at[j]![1])).toBeGreaterThanOrEqual(at[i]![2] + at[j]![2]);
    }
    const labels = container.querySelectorAll("text[data-label]");
    expect(labels).toHaveLength(5);
    labels.forEach((l) => expect((l as SVGElement).style.pointerEvents).toBe("none"));
    await user.hover(screen.getByRole("button", { name: t.open("Crowd 0") }));
    expect(container.querySelectorAll("text[data-label]")).toHaveLength(6);
    await user.click(screen.getByRole("button", { name: t.open("Crowd 0") }));
    expect(await screen.findByText("Calls table")).toBeInTheDocument();
  });
});

describe("source panel and moving a source", () => {
  test("clicking a dot opens the panel with tables, measures, owners and what is missing", async () => {
    mock({});
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: t.open("Custodian portal") }));
    expect(await screen.findByText("Calls table")).toBeInTheDocument();
    expect(screen.getByText(/notice_date/)).toBeInTheDocument();
    expect(screen.getByText(/Capital call timeliness \(Must\)/)).toHaveTextContent("Dee Owner");
    expect(screen.getByText("A sample of the data")).toBeInTheDocument();
    expect(screen.getByText(/It feeds 2 measures/)).toBeInTheDocument();
    expect(screen.getByText(new RegExp(t.suggestion))).toBeInTheDocument();
  });

  test("a restricted source's panel says only that it is restricted", async () => {
    mock({ panel: { ...PANEL, source: MAP.sources[2]!, tables: [], measures: [], missing: [], impact_reasons: [], readiness_reasons: [] } });
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: t.open("A restricted source") }));
    expect(await screen.findByText(t.panel.restricted)).toBeInTheDocument();
    expect(screen.queryByRole("form", { name: t.move.title })).not.toBeInTheDocument();
  });

  test("moving a source needs a reason and sends the values", async () => {
    mock({});
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: t.open("Custodian portal") }));
    await user.type(await screen.findByLabelText(t.move.impact), "-0.5");
    await user.click(screen.getByRole("button", { name: t.move.save }));
    expect(calls.some((c) => c.method === "PUT")).toBe(false);
    await user.type(screen.getByLabelText(t.move.reason), "Board decision");
    await user.click(screen.getByRole("button", { name: t.move.save }));
    const put = calls.find((c) => c.method === "PUT");
    expect(put?.url).toBe(`${BASE}/assessments/${AID}/sources/S1/override`);
    expect(JSON.parse(put?.body ?? "{}")).toEqual({ impact: -0.5, reason: "Board decision" });
  });

  test("a value outside -1 to 1 is refused on the screen", async () => {
    mock({});
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: t.open("Custodian portal") }));
    await user.type(await screen.findByLabelText(t.move.readiness), "3");
    await user.type(screen.getByLabelText(t.move.reason), "x");
    await user.click(screen.getByRole("button", { name: t.move.save }));
    expect(await screen.findByRole("alert")).toHaveTextContent(t.move.range);
  });

  test("a failed save says what to do next", async () => {
    mock({ putStatus: 400 });
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: t.open("Custodian portal") }));
    await user.type(await screen.findByLabelText(t.move.impact), "0.2");
    await user.type(screen.getByLabelText(t.move.reason), "x");
    await user.click(screen.getByRole("button", { name: t.move.save }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Please say why.");
  });

  test("score again posts and shows the new map", async () => {
    mock({});
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: t.rescore }));
    expect(calls.some((c) => c.method === "POST" && c.url === `${BASE}/assessments/${AID}/sources/score`)).toBe(true);
  });
});
