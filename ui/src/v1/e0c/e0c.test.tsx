import type { ReactElement } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import FilePage from "./FilePage";
import IntakePage from "./IntakePage";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

const file = { id: "f1", name: "custodian_sep.xlsx", source_code: "custodian", source_label: "Custodian", state: "waiting_for_mapping", owner: "Mei", received_at: "2026-10-08T10:00:00+00:00", last_load_at: null };
const detail = { ...file, can_act: true,
  profile: { sheet: "Positions", header_row: 3, columns: [{ name: "Fund" }, { name: "Value (000)" }], units: "thousands", date_format: "day first" },
  mapping: { id: "m1", version: 2, state: "proposed", can_decide: true, columns: [{ source_column: "Value (000)", target_table: "position_snapshots", target_field: "market_value", transform: "times 1,000" }] },
  control_totals: [{ measure: "Row count", in_file: "120", loaded: "118", passed: false }],
  load_result: { state: "rejected_totals", message: "Row count differs: the file says 120, we loaded 118.", held_back: ["EG Growth Fund I"] } };

function mock(sent: string[]) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Mei", company_id: "evergreen", roles: ["analyst"] });
    if (init?.method && init.method !== "GET") { sent.push(`${init.method} ${url} ${String(init.body ?? "")}`); return json(200, detail.mapping); }
    if (url === "/api/v1/intake/files/f1") return json(200, detail);
    if (url === "/api/v1/intake/files") return json(200, { files: [file], can_upload: true });
    return json(404, { error: "not_found", message: "Not found." });
  }));
}
const wrap = (el: ReactElement, at: string) => render(<MemoryRouter initialEntries={[at]}><ThemeProvider><SessionProvider>
  <Routes><Route path="/centre/data/intake" element={el} /><Route path="/centre/data/intake/:fileId" element={el} /></Routes></SessionProvider></ThemeProvider></MemoryRouter>);

test("the list groups files by source and writes the state in words", async () => {
  mock([]);
  wrap(<IntakePage />, "/centre/data/intake");
  expect(await screen.findByRole("link", { name: "custodian_sep.xlsx" })).toHaveAttribute("href", "/centre/data/intake/f1");
  expect(screen.getByRole("heading", { name: "Custodian" })).toBeInTheDocument();
  expect(screen.getByText("Waiting for mapping approval")).toBeInTheDocument();
});

test("the file page shows profile, mapping, totals and load result, and Accept approves", async () => {
  const sent: string[] = [];
  mock(sent);
  wrap(<FilePage />, "/centre/data/intake/f1");
  expect(await screen.findByText("Positions")).toBeInTheDocument();
  expect(screen.getByText("position_snapshots.market_value")).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "118" })).toBeInTheDocument();
  expect(screen.getByText(/the file says 120, we loaded 118/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Accept" }));
  expect(sent[0]).toMatch(/^POST \/api\/v1\/model\/mappings\/m1\/approve/);
});

test("Not this asks why and sends the reason", async () => {
  const sent: string[] = [];
  mock(sent);
  wrap(<FilePage />, "/centre/data/intake/f1");
  await userEvent.click(await screen.findByRole("button", { name: "Not this" }));
  await userEvent.type(screen.getByLabelText(/Why not/), "wrong unit");
  await userEvent.click(screen.getByRole("button", { name: "Turn it down" }));
  expect(sent[0]).toMatch(/\/reject .*wrong unit/);
});

test("a proposed mapping line can be changed and is saved before Accept; waiting funds can be approved from the page", async () => {
  const sent: string[] = [];
  const d2 = { ...detail, state: "nothing_loaded", target_options: ["ignore", "position_snapshots.source_market_value"],
    mapping: { ...detail.mapping, can_edit: true, columns: [{ source_column: "Closing cash", target_table: "ignore", target_field: "", transform: null }] },
    needs_approval: { funds: [{ name: "Evergreen Growth I", identifier_id: "al1", status: "proposed", candidates: [] }], portfolios: ["EG-X"], can_approve: true } };
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Mei", company_id: "evergreen", roles: ["analyst"] });
    if (init?.method && init.method !== "GET") { sent.push(`${init.method} ${url} ${String(init.body ?? "")}`); return json(200, {}); }
    return url === "/api/v1/intake/files/f1" ? json(200, d2) : json(404, { error: "not_found", message: "Not found." });
  }));
  wrap(<FilePage />, "/centre/data/intake/f1");
  const target = await screen.findByLabelText("Goes to for Closing cash");
  await userEvent.clear(target);
  await userEvent.type(target, "position_snapshots.source_market_value");
  await userEvent.click(screen.getByRole("button", { name: "Accept" }));
  expect(sent[0]).toMatch(/^PUT \/api\/v1\/model\/mappings\/m1 .*position_snapshots\.source_market_value/);
  expect(sent[1]).toMatch(/^POST \/api\/v1\/model\/mappings\/m1\/approve/);
  expect(screen.getByText(/Portfolio EG-X/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Approve Evergreen Growth I" }));
  expect(sent[2]).toMatch(/^POST \/api\/v1\/evidence\/aliases\/al1\/approve/);
});

test("a portfolio is chosen once for the whole file and sent as a fixed value", async () => {
  const sent: string[] = [];
  const d3 = { ...detail, state: "nothing_loaded", mapping: { ...detail.mapping, state: "approved", can_decide: false, can_fix: true },
    needs_approval: { funds: [], portfolios: [], choose_portfolio: [{ entity: "EG-TRUST", options: ["EG-FUNDS", "EG-LIQUID"] }], can_approve: true } };
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Mei", company_id: "evergreen", roles: ["analyst"] });
    if (init?.method && init.method !== "GET") { sent.push(`${init.method} ${url} ${String(init.body ?? "")}`); return json(200, {}); }
    return url === "/api/v1/intake/files/f1" ? json(200, d3) : json(404, { error: "not_found", message: "Not found." });
  }));
  wrap(<FilePage />, "/centre/data/intake/f1");
  await userEvent.selectOptions(await screen.findByLabelText("Portfolio for EG-TRUST"), "EG-LIQUID");
  expect(sent[0]).toMatch(/^PUT \/api\/v1\/model\/mappings\/m1 .*"fixed":\{"portfolios\.portfolio_code":"EG-LIQUID"\}/);
});

test("a month of files goes in one request and each result is listed", async () => {
  const sent: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Mei", company_id: "evergreen", roles: ["analyst"] });
    if (url === "/api/v1/intake/month") { sent.push(url); return json(200, { files: { "a.csv": { file_id: "f9", state: "waiting_for_mapping", message: "One has been proposed" } }, trade_files: 0, other_files: 1 }); }
    return url === "/api/v1/intake/files" ? json(200, { files: [], can_upload: true }) : json(404, { error: "not_found", message: "Not found." });
  }));
  wrap(<IntakePage />, "/centre/data/intake");
  const input = await screen.findByLabelText(/Load a month of files/);
  await userEvent.upload(input, [new File(["a"], "a.csv"), new File(["b"], "b.csv")]);
  expect(await screen.findByText(/One has been proposed/)).toBeInTheDocument();
  expect(sent).toEqual(["/api/v1/intake/month"]);
});
