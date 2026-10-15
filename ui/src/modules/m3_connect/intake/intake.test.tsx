import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import App from "../../../App";
import { setSessionExpiredHandler } from "../../../api/client";
import type { AssessmentDetail, Step } from "../api";
import type { Benchmarks, Intake, IntakeRequest } from "./api";
import { m3Intake as T } from "./copy";

// M3-P02 screens: the data request in five states, the profile and gap list, the benchmark mapping, and the owner's upload link. fetch is stubbed.

const BASE = "/api/modules/m3_connect";
const AID = "a".repeat(32);
const IDS: Step["id"][] = ["map", "request", "scan", "trial", "findings", "plan"];
const steps: Step[] = IDS.map((id, i) => ({ id, label: id, state: i < 1 ? "done" : "not_started", waiting_on: "Waiting." }));
const detail: AssessmentDetail = { assessment: { id: AID, baseline_outcome_id: "b".repeat(32), charter_outcome_id: null, state: "draft", created_by: "Pat", created_at: "2026-10-04T10:00:00+00:00" }, steps, inputs: null };
const period = { from: "2026-09-01", to: "2026-09-30", label: "September 2026" };
const request: IntakeRequest = {
  id: "r".repeat(32), source_id: "S01", source_name: "Performance workbook", owner: "Owen", zone: "p1", period, state: "opened", link: "open",
  expires_at: "2026-10-18T00:00:00+00:00", days_waiting: 2, reminders: [],
  tables: [{ table_id: "T01", name: "Performance table", row_means: null, columns: [
    { field_id: "F1", name: "Asset Cls", meaning: "The asset class", type: null, measures: [{ id: "K10", name: "Private-market allocation" }], personal: false },
    { field_id: "F2", name: "Fees Charged", meaning: "Fees taken", type: null, measures: [{ id: "K15", name: "Manager performance versus benchmark" }], personal: false }] }],
  benchmarks: [{ measure_id: "K10", measure_name: "Private-market allocation", ask: "Your own reported figure for Private-market allocation, same period (September 2026)" }],
  profile: { period, files: [{ file: "p.xlsx", kind: "xlsx", rows: 40, by: "Pat", at: "x" }], gaps: [
    { kind: "half_empty", text: "“Fees Charged” is only 50% full (20 empty of 40 rows).", measures: ["K15"] },
    { kind: "period_short", text: "The data stops on 22 September, but the period you asked for ends on 30 September.", measures: ["K12"] }],
  tables: [{ file: "p.xlsx", name: "Performance table", row_count: 40, date_column: null, date_range: { from: "2026-08-24", to: "2026-09-22" }, duplicate_key: null, columns: [
    { name: "Asset Cls", type: "string", fill: 0.9, nulls: 4, non_empty: 36, samples: ["Public Equity"], match: { confidence: "high", reasons: [] } },
    { name: "A restricted column", restricted: true }] }] },
};
const intake = (over: Partial<Intake> = {}): Intake => ({ requests: [request], period, not_yet_asked: [], summary: { asked: 1, arrived: 0 }, ...over });
const bench = (over: Partial<Benchmarks> = {}): Benchmarks => ({ file: null, measures: [], unmatched: [], choices: [{ id: "K09", name: "Single-issuer concentration" }], waiting_for: [], ...over });

interface World {
  intake?: Intake;
  intakeStatus?: number;
  hold?: boolean;
  bench?: Benchmarks;
  formStatus?: number;
}
const calls: { method: string; url: string; body?: string }[] = [];
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function mock(w: World) {
  calls.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ method, url, body: typeof init?.body === "string" ? init.body : undefined });
    if (url === "/api/auth/me") return json(200, { display_name: "Pat Owner", company_id: "co-a", roles: ["company_admin"] });
    if (url === "/api/company") return json(200, { company_id: "co-a", name: "Harbor Test Co", industry: "family_office" });
    if (url === "/api/modules") return json(200, [{ id: "m3_connect", number: 3, name: "Assess and plan", description: "d", agent: "Lens" }]);
    if (url === `${BASE}/assessments/${AID}`) return json(200, detail);
    if (url === `${BASE}/assessments/${AID}/intake/requests` && method === "GET") {
      if (w.hold) return new Promise<Response>(() => undefined);
      return w.intakeStatus ? json(w.intakeStatus, { error: w.intakeStatus === 403 ? "forbidden" : "unreadable", message: "x" }) : json(200, w.intake ?? intake());
    }
    if (url === `${BASE}/assessments/${AID}/intake/requests` && method === "POST") {
      return json(200, { new: 1, sent: [{ source_id: "S01", request, link_path: "/intake/di-abc", email: { subject: "Data for Performance workbook, September 2026", body: "Hello Owen,\nSend it here: {link}\nThank you,\nNira" } }] });
    }
    if (url === `${BASE}/assessments/${AID}/intake/sources/S01/upload`) return json(200, { profile: request.profile });
    if (url === `${BASE}/assessments/${AID}/intake/benchmarks` && method === "GET") return json(200, w.bench ?? bench());
    if (url === `${BASE}/assessments/${AID}/intake/benchmarks/map`) return json(200, bench({ measures: [{ measure_id: "K09", measure_name: "Single-issuer concentration", restricted: false, figure: 5, unit: "%", given_by: "Pat", matched: "person" }] }));
    if (url === `${BASE}/intake/link/form`) return w.formStatus ? json(w.formStatus, { error: "link_invalid", message: "This link is not working. Please ask for a new one." }) : json(200, { ...request, state: "opened" });
    return json(404, {});
  }));
}
const open = (path = `/modules/m3_connect/intake/${AID}`) => render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  sessionStorage.clear();
  setSessionExpiredHandler(null);
});

describe("the data request: five states", () => {
  test("loading", async () => {
    mock({ hold: true });
    open();
    expect(await screen.findByRole("heading", { name: T.title })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Loading");
  });

  test("empty: plain words, no source to ask yet", async () => {
    mock({ intake: intake({ requests: [], summary: { asked: 0, arrived: 0 } }) });
    open();
    expect(await screen.findByText(T.noSources)).toBeInTheDocument();
  });

  test("error: one sentence and a way to try again", async () => {
    mock({ intakeStatus: 500 });
    open();
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  test("refused: plain words", async () => {
    mock({ intakeStatus: 403 });
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent("You do not have access to this. Ask your administrator.");
  });

  test("populated: what we need, the three ways, the profile with its gaps, and a restricted column kept out", async () => {
    mock({});
    open();
    expect(await screen.findByRole("heading", { name: "Performance workbook" })).toBeInTheDocument();
    const need = screen.getByRole("columnheader", { name: T.why }).closest("table") as HTMLElement;
    expect(within(need).getByText("Asset Cls")).toBeInTheDocument();
    expect(within(need).getByText("Private-market allocation")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: T.threeWays })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: T.wayLink })).toBeInTheDocument();
    expect(screen.getByText(/only 50% full/)).toBeInTheDocument();
    expect(screen.getByText(/stops on 22 September/)).toBeInTheDocument();
    expect(screen.getByText(T.restricted)).toBeInTheDocument();
    expect(screen.getByText(T.state["opened"] as string)).toBeInTheDocument();
  });
});

describe("actions", () => {
  test("asking the owners shows Nira's message with the link once, ready to copy", async () => {
    mock({});
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: T.askAll }));
    expect(await screen.findByText(T.linkNote)).toBeInTheDocument();
    expect(screen.getByText(/Send it here: http:\/\/localhost(:\d+)?\/intake\/di-abc/)).toBeInTheDocument();
    expect(calls.some((c) => c.method === "POST" && c.url.endsWith("/intake/requests"))).toBe(true);
  });

  test("uploading a file sends its name and its text to the plane's upload route", async () => {
    mock({});
    const user = userEvent.setup();
    open();
    const input = (await screen.findByLabelText(`${T.wayUpload}: Performance workbook`)) as HTMLInputElement;
    await user.upload(input, new File(["a,b\n1,2\n"], "p.csv", { type: "text/csv" }));
    await user.click(screen.getByRole("button", { name: T.upload }));
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/sources/S01/upload"))).toBe(true));
    const sent = JSON.parse(calls.find((c) => c.url.endsWith("/sources/S01/upload"))?.body ?? "{}");
    expect(sent.filename).toBe("p.csv");
    expect(atob(sent.data)).toBe("a,b\n1,2\n");
  });

  test("an unmatched benchmark line is mapped with one dropdown", async () => {
    mock({ bench: bench({ unmatched: [{ index: 3, line: "Mystery number", figure: 5, unit: "%", period_end: null, came_from: null, problem: null }, { index: 4, line: "No figure", figure: null, unit: null, period_end: null, came_from: null, problem: "x" }] }) });
    const user = userEvent.setup();
    open();
    const pick = await screen.findByRole("combobox", { name: `${T.mapTo}: Mystery number` });
    expect(screen.queryByRole("combobox", { name: `${T.mapTo}: No figure` })).not.toBeInTheDocument();
    expect(screen.getByText(T.noFigure)).toBeInTheDocument();
    await user.selectOptions(pick, "K09");
    expect(await screen.findByText("Single-issuer concentration")).toBeInTheDocument();
    expect(JSON.parse(calls.find((c) => c.url.endsWith("/benchmarks/map"))?.body ?? "{}")).toEqual({ index: 3, measure_id: "K09" });
  });
});

describe("the owner's link page", () => {
  test("shows what is asked of one source, with no sign-in", async () => {
    mock({});
    open("/intake/di-" + "a".repeat(32) + "-" + "b".repeat(43));
    expect(await screen.findByRole("heading", { name: T.ownerTitle })).toBeInTheDocument();
    expect(await screen.findByText("Performance workbook")).toBeInTheDocument();
    expect(screen.getByText("Fees Charged")).toBeInTheDocument();
    expect(calls.find((c) => c.url === `${BASE}/intake/link/form`)?.url).not.toContain("di-");
    // new look: product header and theme choice, no signed-in top bar
    expect(document.querySelector(".guest-header")).not.toBeNull();
    expect(document.querySelector(".n-topbar")).toBeNull();
    expect(screen.getByRole("radio", { name: "Dark" })).toBeInTheDocument();
  });

  test("the link shows only the one request: no other source, no company navigation, no signed-in calls", async () => {
    mock({ intake: intake({ not_yet_asked: [{ source_id: "S02", source_name: "Custodian file" }] }) });
    open("/intake/di-" + "a".repeat(32) + "-" + "b".repeat(43));
    expect(await screen.findByText("Performance workbook")).toBeInTheDocument();
    expect(screen.getAllByText("Performance workbook")).toHaveLength(1);
    expect(screen.queryByText("Custodian file")).toBeNull();
    expect(screen.queryByText("Harbor Test Co")).toBeNull();
    expect(screen.queryAllByRole("link").filter((l) => l.getAttribute("href")?.startsWith("/centre"))).toHaveLength(0);
    expect(calls.some((c) => c.url.includes("/assessments/"))).toBe(false);
    expect(screen.getAllByLabelText(T.chooseFile)).toHaveLength(2); // the source file and the reported figures, nothing else
  });

  test("a dead link says so in plain words", async () => {
    mock({ formStatus: 404 });
    open("/intake/di-" + "a".repeat(32) + "-" + "b".repeat(43));
    expect(await screen.findByRole("alert")).toHaveTextContent("This link is not working");
  });
});

describe("LI-M3: what the company profile already holds", () => {
  test("a sample from the profile shows where it came from and is not asked for again", async () => {
    mock({ intake: intake({ requests: [], summary: { asked: 0, arrived: 0 },
      from_profile: [{ source_id: "S01", source_name: "Performance workbook", from: "Sample file performance_workbook.xlsx, sheet 1", files: ["performance_workbook.xlsx"], profile: request.profile }] }) });
    open();
    expect(await screen.findByRole("heading", { name: T.fromProfileTitle })).toBeInTheDocument();
    expect(screen.getByText(T.from("Sample file performance_workbook.xlsx, sheet 1"))).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: T.threeWays })).toBeNull();
  });

  test("a sample Lens could not place asks which source, and sends the choice", async () => {
    mock({ intake: intake({ to_confirm: [{ key: "notes-csv", file: "notes.csv", from: "Sample file notes.csv", candidates: [{ source_id: "S04", source_name: "Index provider feed" }] }] }) });
    const user = userEvent.setup();
    open();
    await user.selectOptions(await screen.findByLabelText(T.placeFor("notes.csv")), "S04");
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.url.endsWith("/intake/sources/_auto/upload") && c.body?.includes("notes-csv"))).toBe(true));
  });

  test("the drop box needs no source to be chosen", async () => {
    mock({});
    open();
    expect(await screen.findByRole("heading", { name: T.dropTitle })).toBeInTheDocument();
    expect(screen.getByText(T.dropHelp)).toBeInTheDocument();
  });
});
