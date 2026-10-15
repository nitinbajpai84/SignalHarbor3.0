import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import { AgentRuns } from "./SettingsPage";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

// Real E6a shape (sh_platform/v1/e6_trace.summary).
const summary = {
  by_agent_day: [{ agent_type: "north", day: "2026-10-09", runs: 5, failures: 1, tool_calls: 12, cost_usd: 0.0421 },
    { agent_type: "lumen", day: "2026-10-08", runs: 2, failures: 0, tool_calls: 0, cost_usd: null }],
  runs: [{ id: "r1", agent_type: "north", model_id: "m", status: "failed", started_at: "2026-10-09T08:00:00+08:00", finished_at: null, tool_calls: 2, cost_usd: null,
    trace_id: "t1", exception_id: "e1", acting_for_user_id: "u1" }],
};
function show(reply: () => Response, urls: string[]) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => { if (url === "/api/auth/me") return json(200, { display_name: "Admin", company_id: "evergreen", roles: ["company_admin"] }); urls.push(url); return reply(); }));
  render(<MemoryRouter><ThemeProvider><SessionProvider><Routes><Route path="/" element={<AgentRuns />} /></Routes></SessionProvider></ThemeProvider></MemoryRouter>);
}

test("agent runs table shows runs, failures, tool calls and cost, 'Not available yet' when unknown, and failed runs", async () => {
  show(() => json(200, summary), []);
  expect(await screen.findByText("North, the industry expert")).toBeInTheDocument();
  expect(screen.getByText("Lumen, the consume agent")).toBeInTheDocument();
  expect(screen.getByText("USD 0.04")).toBeInTheDocument();
  expect(screen.getByText("Not available yet")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open the case" })).toHaveAttribute("href", "/centre/action/cases/e1");
});

test("choosing a day asks the server for that day; an empty day says so; a refusal is shown in words", async () => {
  const urls: string[] = [];
  show(() => json(200, { by_agent_day: [], runs: [] }), urls);
  await userEvent.type(await screen.findByLabelText("Day"), "2026-10-01");
  expect(await screen.findByText("No agent runs on that day.")).toBeInTheDocument();
  expect(urls.some((u) => u.endsWith("?day=2026-10-01"))).toBe(true);
});

test("a non-administrator sees the server's sentence", async () => {
  show(() => json(403, { error: "not_allowed", message: "Only the company administrator can see agent runs." }), []);
  expect(await screen.findByRole("alert")).toHaveTextContent("Only the company administrator can see agent runs.");
});
