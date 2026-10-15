import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { setSessionExpiredHandler } from "../api/client";
import { ThemeProvider } from "../theme";
import { SessionProvider } from "../useSession";
import PipelinesPage from "./PipelinesPage";

const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
const PIPES = { pipelines: [
  { source: "bank", lands_at: "inbox/bank", pattern: "bank_*.csv", expected: "D+2 09:00", sla: "WD8", schema: [], rules: [], depends_on: ["ledger"], owner: "Ann", marts: ["gold.cash"] },
  { source: "fx", lands_at: "inbox/fx", pattern: "fx_*.csv", expected: "D+1 09:00", sla: "WD5", schema: [], rules: [], depends_on: [], owner: "Bo", marts: [] },
] };
const run = (id: string, source: string, status: string, rows: number, passed: boolean) => ({
  id, source, started: `2026-10-0${id}`, ended: "x", on_time: status === "ok", rows, schema_ok: true,
  rules: [{ rule: "r1", passed, count: 2 }], marts_ready: status === "ok" ? "2026-10-05T10:00" : null, sla_met: status === "ok" ? true : null, owner: "Ann", status,
});
const RUNS = { runs: [run("1", "bank", "failed", 10, false), run("2", "bank", "ok", 20, true), run("3", "fx", "late", 5, true), run("4", "payroll_file", "ok", 3, true)] };

let fetchMock: ReturnType<typeof vi.fn>;
function open() {
  fetchMock = vi.fn(async (url: string) => {
    if (url === "/api/auth/me") return json({ display_name: "Ann", company_id: "co-a", roles: ["company_admin"] });
    if (url === "/api/company") return json({ company_id: "co-a", name: "T", industry: "family_office" });
    if (url === "/api/company/build/pipelines") return json(PIPES);
    if (url === "/api/company/build/runs") return json(RUNS);
    if (url === "/api/company/build/schedule") return json({ plan: [{ source: "bank", expected: "D+2 09:00", state: "waiting" }] });
    if (url === "/api/company/build/pipelines/run-due") return json({ ran: [], skipped: [] });
    return json({});
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<MemoryRouter><ThemeProvider><SessionProvider><PipelinesPage /></SessionProvider></ThemeProvider></MemoryRouter>);
}
const posted = () => fetchMock.mock.calls.some(([u, i]) => u === "/api/company/build/pipelines/bank/run" && i?.method === "POST");
afterEach(() => { vi.unstubAllGlobals(); setSessionExpiredHandler(null); });

describe("Pipelines page", () => {
  test("cards render from the contract shape", async () => {
    open();
    expect(await screen.findByText("bank_*.csv")).toBeInTheDocument();
    expect(screen.getByText("By the eighth working day")).toBeInTheDocument();
    // the six-month strip is on the card, and a run for a source with no card (a sealed file) is not in the log
    expect(screen.getAllByLabelText("Last six months for Bank")[0]).toHaveTextContent("Oct: failed");
    expect(screen.queryByText("Payroll file")).toBeNull();
    expect(screen.getByText("Ledger")).toBeInTheDocument();
    expect(screen.getByText("Cash")).toBeInTheDocument();
  });

  test("Run now calls the route after confirm", async () => {
    open();
    const btns = await screen.findAllByRole("button", { name: "Run now" });
    vi.stubGlobal("confirm", vi.fn(() => false));
    await userEvent.click(btns[0]!);
    expect(posted()).toBe(false);
    vi.stubGlobal("confirm", vi.fn(() => true));
    await userEvent.click(btns[0]!);
    await waitFor(() => expect(posted()).toBe(true));
  });

  test("Drop a file and Run everything due post", async () => {
    open();
    expect(await screen.findByText(/Bank: arrives 09:00, two days after month end/)).toBeInTheDocument();
    await userEvent.upload(screen.getByLabelText("Drop a file for bank"), new File(["a,b\n1,2\n"], "bank.csv", { type: "text/csv" }));
    await waitFor(() => expect(fetchMock.mock.calls.some(([u, i]) => u === "/api/company/build/pipelines/bank/upload" && i?.method === "POST"
      && JSON.parse(i.body).filename === "bank.csv")).toBe(true));
    await userEvent.click(screen.getByRole("button", { name: "Run everything due" }));
    await waitFor(() => expect(fetchMock.mock.calls.some(([u, i]) => u === "/api/company/build/pipelines/run-due" && i?.method === "POST")).toBe(true));
  });

  test("after a confirmed Run now the log fills with the new run", async () => {
    open();
    const btns = await screen.findAllByRole("button", { name: "Run now" });
    RUNS.runs.push(run("4", "bank", "ok", 42, true));
    vi.stubGlobal("confirm", vi.fn(() => true));
    await userEvent.click(btns[0]!);
    expect(await screen.findByText("Run for Bank started.")).toBeInTheDocument();
    const rows = within(screen.getByRole("table")).getAllByRole("row");
    expect(rows[1]).toHaveTextContent("Bank");
    expect(rows[1]).toHaveTextContent("42");
    RUNS.runs.pop();
  });

  test("the log renders statuses, newest first, and filters", async () => {
    open();
    const table = await screen.findByRole("table");
    const rows = within(table).getAllByRole("row");
    expect(rows[1]).toHaveTextContent("Fx");
    expect(rows[1]).toHaveTextContent("late");
    expect(rows[2]).toHaveTextContent("1 passed, 0 failed");
    expect(rows[3]).toHaveTextContent("0 passed, 1 failed");
    await userEvent.click(within(screen.getByRole("group", { name: "Filter by source" })).getByRole("button", { name: "Fx" }));
    expect(within(table).getAllByRole("row")).toHaveLength(2);
  });

  test("run times are in the browser's own time zone and the owner is the source owner", async () => {
    RUNS.runs[0] = { ...RUNS.runs[0]!, started: "2026-10-06T19:12:00+00:00" };
    open();
    const local = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date("2026-10-06T19:12:00+00:00"));
    expect((await screen.findAllByText(new RegExp(local))).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Source owner").length).toBeGreaterThan(0);
  });
});
