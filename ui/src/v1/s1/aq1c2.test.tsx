import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import { AgentRuns, stepLine } from "./SettingsPage";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

test("TS1c-05, RC2-2, SS-5: masking, a check with no stronger model, the SQL kind and the replaced figure's kind are said in words", () => {
  expect(stepLine({ kind: "model", n: 1, tier: "specialist", ms: 10, ok: true, masked: 3, escalation: "no stronger model in this mode" }))
    .toBe("Model step 1: specialist model, 10 ms. 3 names were masked before it left. A check failed and was not asked again: no stronger model in this mode.");
  expect(stepLine({ kind: "tool", tool: "dry_run_sql", result_chars: 40, ms: 2, sql: { starts_with: "SELECT", tables: ["gold_x"] } }))
    .toBe("Tool dry_run_sql: answer of 40 characters, 2 ms. Ran a SELECT statement on gold_x.");
  expect(stepLine({ kind: "guard", numbers_replaced: 1, replaced: [{ kind: "number_in_words", counts: "trade" }] }))
    .toBe("Number check: 1 figure the agent could not source was replaced (a number in words of trade).");
});

test("lumen-memory-c1-06: a chat turn says whom the agent answered", async () => {
  const loops = { loops: [{ trace_id: "tr-span-ab12cd34-1a2b3c4d", agent: "Span", person: "Mei Chen", at: "2026-10-10T09:52:00+08:00", steps: 3, tokens: 150, ms: 900, outcome: "done" }] };
  vi.stubGlobal("fetch", vi.fn(async (url: string) => url === "/api/auth/me" ? json(200, { display_name: "Admin", company_id: "c", roles: ["company_admin"] })
    : url.includes("/loops") ? json(200, loops) : json(200, { by_agent_day: [], runs: [] })));
  render(<MemoryRouter><ThemeProvider><SessionProvider><Routes><Route path="/" element={<AgentRuns />} /></Routes></SessionProvider></ThemeProvider></MemoryRouter>);
  expect(await screen.findByRole("list", { name: "Chat turns" })).toHaveTextContent("Span answering Mei Chen on");
});
