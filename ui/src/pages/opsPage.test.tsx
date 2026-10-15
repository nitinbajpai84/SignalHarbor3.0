import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { setSessionExpiredHandler } from "../api/client";
import { ThemeProvider } from "../theme";
import { SessionProvider } from "../useSession";
import OpsPage from "./OpsPage";

// Ops page: alerts with their owner, and an empty day. fetch is stubbed.

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const DAY = { date: "2026-10-06", arrivals: [], failed_checks: [], range_breaks: [], alerts: [], run_book: [], history: [] };
const BUSY = {
  ...DAY,
  arrivals: [{ source: "custody", state: "late", owner: "Sara Lim", arrived: null, rows: null }],
  alerts: [{ id: "custody:late", source: "custody", kind: "late", owner: "Sara Lim", ask: "Hello Sara Lim, the file arrived late for custody.", state: "open", by: null, note: null }],
  run_book: [{ source: "custody", expected: "D+2 09:00", sla: "WD8", depends_on: [], marts: ["gold.aum"], owner: "Sara Lim" }],
};

function mock(body: unknown) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Ann", company_id: "co-a", roles: ["company_admin"] });
    if (url === "/api/company") return json(200, { company_id: "co-a", name: "Lakeside Test Co", industry: "family_office" });
    return json(200, body);
  }));
}
const open = () => render(<MemoryRouter><ThemeProvider><SessionProvider><OpsPage /></SessionProvider></ThemeProvider></MemoryRouter>);

afterEach(() => { vi.unstubAllGlobals(); setSessionExpiredHandler(null); });

describe("Ops page", () => {
  test("an alert shows its owner and the drafted ask", async () => {
    mock(BUSY);
    open();
    expect((await screen.findAllByText(/Source owner: Sara Lim/)).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Custody/, { selector: "strong" }).length).toBeGreaterThan(0);
    await userEvent.click(screen.getByRole("button", { name: "Ask the owner" }));
    expect(screen.getByText(/the file arrived late for custody/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy" })).toBeInTheDocument();
  });

  test("Acknowledge posts the note to the alert", async () => {
    mock(BUSY);
    open();
    await userEvent.type(await screen.findByLabelText("Note for custody"), "chasing");
    await userEvent.click(screen.getByRole("button", { name: "Acknowledge" }));
    const call = (fetch as unknown as { mock: { calls: [string, RequestInit][] } }).mock.calls.find(([u]) => u.endsWith("/ack"));
    expect(call?.[0]).toBe("/api/company/build/alerts/custody%3Alate/ack");
    expect(call?.[1].method).toBe("POST");
    expect(String(call?.[1].body)).toContain("chasing");
  });

  test("acknowledge posts a note and the next read shows who acknowledged", async () => {
    let acked = false;
    const done = { ...BUSY, alerts: [{ ...BUSY.alerts[0]!, state: "acknowledged", by: "Ann", note: "chasing Sara" }] };
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (url === "/api/auth/me") return json(200, { display_name: "Ann", company_id: "co-a", roles: ["analyst"] });
      if (url === "/api/company") return json(200, { company_id: "co-a", name: "Lakeside Test Co", industry: "family_office" });
      if (url.endsWith("/ack") && init?.method === "POST") { acked = String(init.body).includes("chasing Sara"); return json(200, {}); }
      return json(200, acked ? done : BUSY);
    }));
    open();
    await userEvent.type(await screen.findByLabelText("Note for custody"), "chasing Sara");
    await userEvent.click(screen.getByRole("button", { name: "Acknowledge" }));
    expect(await screen.findByText(/Acknowledged by Ann: chasing Sara/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Acknowledge" })).toBeNull();
  });

  test("the date, the seven run days and the schedule are in plain words", async () => {
    const hist = ["2026-09-01", "2026-08-01"].map((d) => ({ source: "custody", started: `${d}T08:35:00+00:00`, status: "ok" }));
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/auth/me") return json(200, { display_name: "Ann", company_id: "co-a", roles: ["analyst"] });
      if (url === "/api/company") return json(200, { company_id: "co-a", name: "T", industry: "family_office" });
      if (url === "/api/company/build/pipelines") return json(200, { pipelines: [{ source: "custody", title: "Custodian daily file", owner: "Harvey Rowley" }] });
      if (url === "/api/company/build/runs") return json(200, { runs: [...hist, { source: "payroll_file", started: "2026-09-01T08:35:00+00:00", status: "ok" }] });
      return json(200, { ...BUSY, date: "2026-09-01" });
    }));
    open();
    expect(await screen.findByText(/Report for 1 September 2026/)).toBeInTheDocument();
    expect((await screen.findAllByText(/Source owner: Harvey Rowley/)).length).toBeGreaterThan(0);
    expect(screen.getByText("By the eighth working day")).toBeInTheDocument();
    expect(screen.getByText(/09:00, two days after month end/)).toBeInTheDocument();
    const days = await screen.findByLabelText("Seven-day history");
    expect(days.querySelectorAll("li")).toHaveLength(2);
    expect(days).toHaveTextContent("1 August 2026: 1 ok");
    expect(screen.queryByText(/Payroll/)).toBeNull();
  });

  test("a measure outside its range shows its business owner from Feeds, not the source owner", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/auth/me") return json(200, { display_name: "Ann", company_id: "co-a", roles: ["analyst"] });
      if (url === "/api/company") return json(200, { company_id: "co-a", name: "T", industry: "family_office" });
      if (url === "/api/company/feeds") return json(200, { measures: [{ code: "K02", owner: "Daniel Kerr" }] });
      if (url === "/api/company/build/pipelines" || url === "/api/company/build/runs") return json(200, {});
      return json(200, { ...BUSY, range_breaks: [{ mart: "gold.k02", owner: "Harvey Rowley", latest: 1, mean: 2, margin: 1 }] });
    }));
    open();
    expect(await screen.findByText("Daniel Kerr")).toBeInTheDocument();
  });

  test("an empty day says so plainly", async () => {
    mock(DAY);
    open();
    expect(await screen.findByText(/Nothing is scheduled yet/)).toBeInTheDocument();
  });
});
