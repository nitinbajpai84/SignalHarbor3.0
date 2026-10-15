import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import App from "../../App";
import { setSessionExpiredHandler } from "../../api/client";
import type { AssessmentDetail, Step } from "./api";
import ConnectSteps from "./ConnectSteps";
import { m3, m3Nira, m3Steps } from "./copy";

// Module 3 scaffold screens: start page in five states, the six-step strip, Nira's next step. fetch is stubbed.

const BASE = "/api/modules/m3_connect";
const AID = "a".repeat(32);
const IDS: Step["id"][] = ["map", "request", "scan", "trial", "findings", "plan"];
const steps = (done = 0): Step[] => IDS.map((id, i) => ({ id, label: id, state: i < done ? "done" : i === done ? "in_progress" : "not_started",
  waiting_on: i < done ? "" : `Waiting on ${id} owners.` }));
const assessment = { id: AID, baseline_outcome_id: "b".repeat(32), charter_outcome_id: null, state: "draft" as const, created_by: "Pat", created_at: "2026-10-04T10:00:00+00:00" };
const detail = (done = 0): AssessmentDetail => ({ assessment, steps: steps(done), inputs: { measures: [{ id: "K1", name: "A restricted measure", restricted: true }],
  sources: [], pain_points: [], future_signals: [], levers: [] } });

interface World {
  list?: { assessments: (typeof assessment)[]; signed_baseline: boolean; can_start?: boolean; baseline_label?: string };
  listStatus?: number;
  hold?: boolean;
  startStatus?: number;
  detail?: AssessmentDetail;
  detailStatus?: number;
}
const calls: { method: string; url: string }[] = [];
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function mock(w: World) {
  calls.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ method, url });
    if (url === "/api/auth/me") return json(200, { display_name: "Pat Owner", company_id: "co-a", roles: ["company_admin"] });
    if (url === "/api/company") return json(200, { company_id: "co-a", name: "Harbor Test Co", industry: "family_office" });
    if (url === "/api/modules") return json(200, [{ id: "m3_connect", number: 3, name: "Assess and plan", description: "d", agent: "Lens" }]);
    if (url === `${BASE}/assessments` && method === "GET") {
      if (w.hold) return new Promise<Response>(() => undefined);
      return w.listStatus ? json(w.listStatus, { error: w.listStatus === 403 ? "forbidden" : "unreadable", message: "x" })
        : json(200, w.list ?? { assessments: [], signed_baseline: true });
    }
    if (url === `${BASE}/assessments` && method === "POST") {
      return w.startStatus ? json(w.startStatus, { error: "no_baseline", message: "There is no signed baseline yet. Sign the baseline in module 2 first." })
        : json(201, { assessment });
    }
    if (url === `${BASE}/assessments/${AID}`) return w.detailStatus ? json(w.detailStatus, { error: "x", message: "m" }) : json(200, w.detail ?? detail());
    return json(404, {});
  }));
}
const open = (path = "/modules/m3_connect") => render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);

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
    expect(await screen.findByRole("heading", { name: m3.title })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Loading");
  });

  test("empty company: honest words, no start button", async () => {
    mock({ list: { assessments: [], signed_baseline: false } });
    open();
    expect(await screen.findByText(m3.noBaseline)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: m3.start })).not.toBeInTheDocument();
  });

  test("error: one sentence and a way to try again", async () => {
    mock({ listStatus: 500 });
    open();
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  test("refused: plain words, no start button", async () => {
    mock({ listStatus: 403 });
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent("You do not have access to this. Ask your administrator.");
    expect(screen.queryByRole("button", { name: m3.start })).not.toBeInTheDocument();
  });

  test("populated: start from a signed baseline opens the map screen", async () => {
    mock({});
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: m3.start }));
    expect(await screen.findByRole("heading", { name: "Source map" })).toBeInTheDocument();
    expect(calls.some((c) => c.method === "POST" && c.url === `${BASE}/assessments`)).toBe(true);
  });

  test("starting with no signed baseline says so in plain words", async () => {
    mock({ startStatus: 409 });
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: m3.start }));
    expect(await screen.findByRole("alert")).toHaveTextContent("no signed baseline");
  });

  test("an existing assessment is listed and opened, and offers no second start", async () => {
    mock({ list: { assessments: [assessment], signed_baseline: true } });
    open();
    expect(await screen.findByRole("link", { name: m3.open })).toHaveAttribute("href", `/modules/m3_connect/map/${AID}`);
    expect(screen.queryByRole("button", { name: m3.start })).not.toBeInTheDocument();
  });
});

describe("a newer baseline", () => {
  test("offers a new start, and rows are told apart by baseline and time", async () => {
    const older = { ...assessment, baseline_label: "Baseline signed 2026-09-01" };
    const other = { ...assessment, id: "c".repeat(32), baseline_label: "Second baseline" };
    mock({ list: { assessments: [older, other], signed_baseline: true, can_start: true, baseline_label: "Third baseline" } });
    const user = userEvent.setup();
    open();
    expect(await screen.findByText(/Baseline signed 2026-09-01 · Started .+:/)).toBeInTheDocument();
    expect(screen.getByText(/Second baseline · Started/)).toBeInTheDocument();
    expect(screen.getByText(/Third baseline/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: m3.startNew }));
    expect(calls.some((c) => c.method === "POST" && c.url === `${BASE}/assessments`)).toBe(true);
  });
});

describe("an assessment screen", () => {
  test("shows the six steps, linked, and Nira says what the first unfinished step waits on", async () => {
    mock({ detail: detail(1) });
    open(`/modules/m3_connect/trial/${AID}`);
    expect(await screen.findByRole("navigation", { name: m3Steps.label })).toBeInTheDocument();
    for (const l of [m3Steps.map, m3Steps.request, m3Steps.scan, m3Steps.trial, m3Steps.findings, m3Steps.plan]) {
      expect(screen.getByRole("link", { name: new RegExp(`^${l}`) })).toBeInTheDocument();
    }
    expect(screen.getByRole("link", { name: new RegExp(`^${m3Steps.request}`) })).toHaveAttribute("href", `/modules/m3_connect/intake/${AID}`);
    expect(screen.getByRole("link", { name: new RegExp(`^${m3Steps.findings}`) })).toHaveAttribute("href", `/modules/m3_connect/trial/${AID}`);
    expect(screen.getByRole("link", { name: new RegExp(`^${m3Steps.trial}`) }).className).toContain("active");
    expect(screen.getByText("Waiting on request owners.")).toBeInTheDocument();
    expect(screen.getByText(m3Nira.next)).toBeInTheDocument();
  });

  test("when every step is done Nira says so", async () => {
    mock({ detail: detail(6) });
    open(`/modules/m3_connect/trial/${AID}`); // the plan route is M3-P04's own screen (plan/plan.test.tsx)
    expect(await screen.findByText(m3Nira.allDone)).toBeInTheDocument();
  });

  test("error: a way to try again", async () => {
    mock({ detailStatus: 500 });
    open(`/modules/m3_connect/map/${AID}`);
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  test("refused: another company's assessment gives no content", async () => {
    mock({ detailStatus: 403 });
    open(`/modules/m3_connect/map/${AID}`);
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: m3Steps.label })).not.toBeInTheDocument();
  });
});

describe("step strip alone", () => {
  test("names each step's state in words, not colour only", () => {
    render(<MemoryRouter><ConnectSteps assessmentId={AID} steps={steps(1)} /></MemoryRouter>);
    expect(screen.getByText(m3Steps.state.done)).toBeInTheDocument();
    expect(screen.getByText(m3Steps.state.in_progress)).toBeInTheDocument();
    expect(screen.getAllByText(m3Steps.state.not_started)).toHaveLength(4);
  });
});
