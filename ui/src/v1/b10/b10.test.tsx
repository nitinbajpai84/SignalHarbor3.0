import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import { lineLabel } from "../workbench/ChangeBar";
import ArchitectureStep from "./ArchitectureStep";
import type { Pack, PackView, Questions, Summary } from "./api";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

const SUMMARY: Summary = {
  project_id: "prj-1", title: "Monthly performance", readers: ["Family council"], needed_by: "5th business day", steps: 7, asked: ["source:src-idx"], not_asked: ["Access: inherited from the intent"],
  line: "I read the signed intent and the process map (7 steps). I only need to ask you 1 thing.",
  kpis: [{ code: "K1", name: "Portfolio return", definition: "x", signed: true, owner: "Mei" }],
  systems: [
    { id: "src-admin", code: "admin", name: "Administrator export", holds: "positions", owner: "Mei Tan", format: "excel", channel: "sftp", frequency: "daily", status: "connected", connector: "c1", from_intent: true,
      confirmed: false, corrected: [], intent: { holds: "", owner: "", format: "", channel: "sftp", frequency: "daily" }, found: { files: 1, documents: 0, columns: 14, rows: 462 } },
    { id: "src-idx", code: "idx", name: "Index levels", holds: "", owner: "", format: "", channel: "", frequency: "", status: "never_seen", connector: null, from_intent: false,
      confirmed: false, corrected: [], intent: { holds: "", owner: "", format: "", channel: "", frequency: "" } }],
};
const QS: Questions = {
  open: [], known: [], all: [{ id: "source:src-idx", topic: "Source", title: "How do Index levels arrive?", why: "Named, not connected.", proposal: "sftp", options: [], answer: null, state: "open", evidence: "" }],
};
QS.open = QS.all;
const PACK: Pack = {
  project_id: "prj-1", version: 1, state: "draft", base_version: null, created_by: "Leo Park", created_at: "", approved_by: null, approved_at: null, open_rows: 1, locked: false, notes: [],
  target: { silver: [{ name: "valuation_observations", status: "used", note: "Used as it is", history: [] }],
    gold: [{ name: "gold_x_monthly", purpose: "", grain: "monthly by entity", keys: ["month"], history: [], owner: "Mei", columns: [{ name: "month", type: "date", expr: "m", definition: "Month end", sensitivity: "internal", history: false }] }] },
  catalogue: [], mapping: [{ id: "m1", kind: "check", system: "Trading export", source_field: "", bronze: "", silver: "", gold: "", words: "", needs_person: "No approved mapping yet", resolved: false }],
  edits: [], rules: { checks: [{ id: "c1", kind: "control_total", text: "Total equals footer", tolerance: "exact", source: "process_map" }], history: [], refresh: { freq: "monthly", at: "06:00", day: null }, late_data: "x", benchmark: "later" },
  sources: [], counts: { sources: 2, gold: 1, silver: 1, mapping: 1, checks: 1 },
};
const view = (pack: Pack | null, can: Partial<PackView["can"]> = {}): PackView => ({
  project_id: "prj-1", pack, versions: pack ? [{ version: 1, state: pack.state, by: "Leo Park", at: "", approved_by: null, edits: 0, base_version: null, plan_version: null }] : [],
  can: { answer: true, generate: true, edit: true, submit: true, approve: false, reject: false, plan: false, ...can },
});

const calls: string[] = [];
function mock(v: PackView) {
  calls.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push(`${init?.method ?? "GET"} ${url}`);
    if (url === "/api/auth/me") return json(200, { display_name: "Leo Park", company_id: "evergreen", roles: ["analyst"] });
    if (url === "/api/v1/projects") return json(200, { projects: [{ id: "prj-1", title: "Monthly performance" }] });
    if (url.endsWith("/architecture/summary")) return json(200, SUMMARY);
    if (url.endsWith("/architecture/questions")) return json(200, QS);
    if (url.endsWith("/architecture/pack")) return json(200, v);
    if (url.includes("/architecture/questions/") || url.includes("/systems/confirm")) return json(200, url.includes("confirm") ? SUMMARY : QS);
    return json(404, { error: "not_found", message: "Not found." });
  }));
}
const page = () => render(<ThemeProvider><MemoryRouter initialEntries={["/centre/build/p/prj-1/architecture/pack"]}><SessionProvider>
  <Routes><Route path="/centre/build/p/:projectId/*" element={<ArchitectureStep />} /></Routes></SessionProvider></MemoryRouter></ThemeProvider>);

describe("Architecture step (V6 H1-H6)", () => {
  it("shows each system from the intent with Confirm, and says what is not asked", async () => {
    mock(view(null)); page();
    expect(await screen.findByText(/I only need to ask you 1 thing/)).toBeInTheDocument();
    expect(screen.getByText("from the intent")).toBeInTheDocument();
    expect(screen.getByText(/Not known: one question/)).toBeInTheDocument();
    expect(screen.getByText(/Access: inherited from the intent/)).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole("button", { name: "Confirm" })[0]!);
    await waitFor(() => expect(calls).toContain("POST /api/v1/build/p/prj-1/architecture/systems/confirm"));
  });

  it("asks only what is missing with Span's proposal, accepted in one click", async () => {
    mock(view(null)); page();
    await userEvent.click(await screen.findByRole("button", { name: "The few questions" }));
    expect(await screen.findByText("How do Index levels arrive?")).toBeInTheDocument();
    expect(screen.getByText(/Span proposes \(suggestion\):/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Accept all and continue" }));
    await waitFor(() => expect(calls).toContain("POST /api/v1/build/p/prj-1/architecture/questions/accept-all"));
  });

  it("offers to draft the pack when there is none", async () => {
    mock(view(null)); page();
    await userEvent.click(await screen.findByRole("button", { name: "The design pack" }));
    expect(await screen.findByRole("button", { name: "Draft the design pack" })).toBeInTheDocument();
  });

  it("holds the send back while a mapping row needs a person, and only the head of data sees Approve", async () => {
    mock(view(PACK)); page();
    expect(await screen.findByLabelText("The design pack")).toBeInTheDocument();
    expect(screen.getByText("gold_x_monthly")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Send to the head of data/ })).toBeDisabled();
    expect(screen.queryByRole("button", { name: /^Approve version/ })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "ETL mapping sheet" }));
    expect(screen.getByText("No approved mapping yet")).toBeInTheDocument();
    expect(screen.getByText("1 rows need a person")).toBeInTheDocument();
  });

  it("shows Approve to the head of data on a pack sent for approval", async () => {
    mock(view({ ...PACK, state: "proposed", open_rows: 0 }, { approve: true, reject: true, submit: false })); page();
    await userEvent.click(await screen.findByRole("button", { name: "Approve version 1" }));
    await waitFor(() => expect(calls).toContain("POST /api/v1/build/p/prj-1/architecture/pack/approve"));
  });

  it("lists silver reused apart from silver proposed, with what was looked for, and offers the second approval when the plan was not approved", async () => {
    const pack: Pack = { ...PACK, state: "approved", locked: true, plan_state: "not_approved", plan_error: "The plan check refused a table.", model_change: 4,
      target: { gold: PACK.target.gold, silver: [
        { name: "cash_movements", status: "reused", note: "Used as it is", history: [], other_projects: ["Liquidity look"] },
        { name: "cash_movements", status: "proposed", note: "x", history: [], columns: ["notice_reference"], extends: true, looked_for: "a notice reference",
          considered: [{ table: "commitments", why_not: "holds the promise only" }], affects: ["Liquidity look: gold_l_x"] }] } };
    mock({ ...view(pack, { approve_plan: true }), model_change: { version: 4, state: "proposed", summary: "", tables: [{ name: "cash_movements" }] } });
    page();
    await userEvent.click(await screen.findByRole("button", { name: "The design pack" }));
    expect(await screen.findByRole("table", { name: "Silver reused" })).toHaveTextContent("Liquidity look");
    expect(screen.getByLabelText("Silver proposed")).toHaveTextContent(/Looked for: a notice reference.*commitments \(holds the promise only\)/s);
    expect(screen.getByRole("button", { name: "Approve the build plan" })).toBeInTheDocument();
  });

  it("words a changed line by its field, never the raw name", () => {
    expect(lineLabel("sow/goal/needed_by")).toBe("Goal: needed by");
    expect(lineLabel("sow/kpis/2/definition")).toBe("KPI: definition");
  });
});

describe("V6B: the full target model", () => {
  const FULL: Pack = {
    ...PACK, open_rows: 0, mapping: [],
    target: { silver: [{ name: "instruments", status: "extended", note: "Extended: manager name keeps its history (type 2)", history: ["manager_name"] }],
      gold: [{ name: "gold_x_benchmark_monthly", purpose: "", grain: "Portfolio, Benchmark, Month", keys: ["portfolio_code", "benchmark_code", "month"], history: [], owner: "Mei",
        columns: [{ name: "month", type: "DATE", expr: "m", definition: "x", sensitivity: "internal", history: false }, { name: "portfolio_return", type: "DECIMAL(9,6)", expr: "r", definition: "y", sensitivity: "internal", history: false }] }] },
    definitions: [{ name: "Benchmark return", definition: "Weighted sum of the legs of EG-OFFICE-BLEND", source: "Signed: benchmark version 1", signed: true, columns: [] }],
    benchmark: { portfolio: "EG-LIQUID", portfolio_name: "Evergreen Liquid portfolio", code: "EG-OFFICE-BLEND", version: 1, month: "2026-09",
      figures: [{ key: "portfolio_return", label: "Portfolio return", unit: "pct" }, { key: "benchmark_return", label: "Benchmark return", unit: "pct" }] },
  };
  it("shows typed columns, grain and key, the type 2 columns, the definitions and the benchmark check; Compare versions waits for a second version", async () => {
    mock(view(FULL)); page();
    const gold = await screen.findByRole("table", { name: "Gold tables" });
    expect(gold).toHaveTextContent("portfolio_return decimal(9,6)");
    expect(gold).toHaveTextContent("Key: portfolio_code + benchmark_code + month");
    expect(screen.getByRole("table", { name: "Silver reused" })).toHaveTextContent("manager name keeps its history");
    expect(screen.getByRole("table", { name: "Definitions" })).toHaveTextContent("Signed: benchmark version 1");
    expect(screen.getByRole("region", { name: "Benchmark check" })).toHaveTextContent("EG-LIQUID");
    expect(screen.getByRole("region", { name: "Benchmark check" })).toHaveTextContent("EG-OFFICE-BLEND, signed version 1, for 2026-09");
    expect(screen.getByRole("button", { name: "Compare versions" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Open the mapping sheet" }));
    expect(await screen.findByText(/No row is open./)).toBeInTheDocument();
  });
  it("is drawn on the dark tokens", async () => {
    mock(view(FULL)); const { container } = page();
    await screen.findByRole("table", { name: "Gold tables" });
    expect(container.querySelector(".ds-dark")).not.toBeNull();
  });
});
