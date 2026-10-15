import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import { AgentRuns, dayLabel, stamp, stepLine, totalLine } from "./SettingsPage";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

const runs = { by_agent_day: [{ agent_type: "span", day: "2026-10-09", runs: 1, failures: 0, tool_calls: 1, cost_usd: null }],
  runs: [{ id: "r1", agent_type: "span", status: "done", started_at: "2026-10-09T08:00:00+08:00", tool_calls: 1, cost_usd: null, trace_id: "t1", exception_id: null }] };
const steps = { runs: [], steps: [{ trace_id: "t1", run_id: "r1", agent: "Span", status: "done", elapsed_ms: 900, steps: [
  { kind: "context", items: [{ kind: "summary", id: "s-1" }, { kind: "memory", id: "m-1" }, { kind: "passage", id: "a.txt:1-3" }] },
  { kind: "model", n: 1, tier: "small", tokens_in: 120, tokens_out: 30, ms: 400, ok: true },
  { kind: "tool", n: 1, tool: "get_plan", result_chars: 812, refused: false, ms: 20 },
  { kind: "tool", n: 2, tool: "dry_run_sql", result_chars: 0, refused: true, reason: "argument_check:sql", ms: 3 },
  { kind: "guard", numbers_replaced: 0 }] }] };

test("a run's steps are listed in plain words, with the context items used", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => url === "/api/auth/me" ? json(200, { display_name: "Admin", company_id: "c", roles: ["company_admin"] })
    : url.includes("/trace/") ? json(200, steps) : json(200, runs)));
  render(<MemoryRouter><ThemeProvider><SessionProvider><Routes><Route path="/" element={<AgentRuns />} /></Routes></SessionProvider></ThemeProvider></MemoryRouter>);
  await userEvent.click(await screen.findByRole("button", { name: "Show steps" }));
  const list = await screen.findByRole("list", { name: "Steps of the run" });
  expect(list).toHaveTextContent("Context used: 1 earlier conversation, 1 remembered item, 1 document passage.");
  expect(list).toHaveTextContent("Model step 1: small model, 120 tokens in, 30 out, 400 ms.");
  expect(list).toHaveTextContent("Tool get_plan: answer of 812 characters, 20 ms.");
  expect(list).toHaveTextContent("Tool dry_run_sql: answer of 0 characters, 3 ms, refused (argument_check:sql).");
  expect(list).toHaveTextContent("Number check: no invented figure.");
});

test("chat turns are listed with agent, steps, tokens and time, and show their steps", async () => {
  const loops = { loops: [{ trace_id: "tr-north-ab12cd34-1", agent: "North", at: "2026-10-09T08:00:00+08:00", steps: 3, tokens: 150, ms: 900, outcome: "done" }] };
  vi.stubGlobal("fetch", vi.fn(async (url: string) => url === "/api/auth/me" ? json(200, { display_name: "Admin", company_id: "c", roles: ["company_admin"] })
    : url.includes("/trace/") ? json(200, steps) : url.includes("/loops") ? json(200, loops) : json(200, runs)));
  render(<MemoryRouter><ThemeProvider><SessionProvider><Routes><Route path="/" element={<AgentRuns />} /></Routes></SessionProvider></ThemeProvider></MemoryRouter>);
  const list = await screen.findByRole("list", { name: "Chat turns" });
  expect(list).toHaveTextContent("North");
  expect(list).toHaveTextContent("3 steps, 150 tokens, 900 ms, no price recorded.");
  await userEvent.click(within(list).getByRole("button", { name: "Show steps" }));
  expect(await screen.findByRole("list", { name: "Steps of the run" })).toHaveTextContent("Model step 1");
});

test("W14: one date style, per-step price and a run total; a run with no trace says no steps were recorded", async () => {
  expect(stamp("2026-10-09T09:12:00")).toBe("9 Oct 2026, 09:12");
  expect(dayLabel("2026-10-09")).toBe("9 Oct 2026");
  expect(stepLine({ kind: "model", n: 1, tier: "small", tokens_in: 10, tokens_out: 5, ms: 40, cost_usd: 0.0012 })).toBe("Model step 1: small model, 10 tokens in, 5 out, 40 ms, USD 0.0012.");
  expect(totalLine({ cost_usd: null, tokens: 15 })).toBe("Total for this run: 15 tokens (no price recorded).");
  const two = { ...runs, runs: [{ ...runs.runs[0], started_at: "2026-10-09T09:12:00" }, { ...runs.runs[0], id: "r2", trace_id: null }] };
  const priced = { ...steps, total: { cost_usd: 0.0015, tokens: 150 } };
  vi.stubGlobal("fetch", vi.fn(async (url: string) => url === "/api/auth/me" ? json(200, { display_name: "Admin", company_id: "c", roles: ["company_admin"] })
    : url.includes("/trace/") ? json(200, priced) : url.includes("/loops") ? json(200, { loops: [] }) : json(200, two)));
  render(<MemoryRouter><ThemeProvider><SessionProvider><Routes><Route path="/" element={<AgentRuns />} /></Routes></SessionProvider></ThemeProvider></MemoryRouter>);
  const list = await screen.findByRole("list", { name: "Recent runs" });
  expect(list).toHaveTextContent("Span on 9 Oct 2026, 09:12, done.");
  expect(screen.getByRole("table", { name: "Runs by agent and day" })).toHaveTextContent("9 Oct 2026");
  const buttons = within(list).getAllByRole("button", { name: "Show steps" });
  await userEvent.click(buttons[0]!);
  expect(await screen.findByText("Total for this run: USD 0.0015, 150 tokens.")).toBeInTheDocument();
  await userEvent.click(buttons[1]!);
  expect(await screen.findByText("No steps were recorded for this run.")).toBeInTheDocument();
});

test("AQ1 RC-10/RC-8: chat turns filter by agent, show their cost, and a refused step says why", async () => {
  const calls: string[] = [];
  const loops = { loops: [{ trace_id: "tr-span-1", agent: "Span", at: "2026-10-09T08:00:00+08:00", steps: 2, tokens: 50, ms: 10, outcome: "done", cost_usd: 0.0021, worded_by: "model" }], more: false };
  vi.stubGlobal("fetch", vi.fn(async (url: string) => { calls.push(url); return url === "/api/auth/me" ? json(200, { display_name: "Admin", company_id: "c", roles: ["company_admin"] })
    : url.includes("/loops") ? json(200, loops) : json(200, runs); }));
  render(<MemoryRouter><ThemeProvider><SessionProvider><Routes><Route path="/" element={<AgentRuns />} /></Routes></SessionProvider></ThemeProvider></MemoryRouter>);
  const list = await screen.findByRole("list", { name: "Chat turns" });
  expect(list).toHaveTextContent("USD 0.0021");
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Agent" }), "span");
  await screen.findByRole("list", { name: "Chat turns" });
  expect(calls.some((u) => u.includes("/loops") && u.includes("agent=span"))).toBe(true);
  expect(stepLine({ kind: "model", n: 2, ok: false, reason: "vault_name", ms: 9 })).toBe("Model step 2: 9 ms, failed: refused by the gateway (a protected name).");
  expect(stepLine({ kind: "rules", reason: "model_off" })).toBe("Answer worded by fixed rules, not the model (model off).");
});
