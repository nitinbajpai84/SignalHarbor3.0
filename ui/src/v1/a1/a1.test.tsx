import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { routes } from "./routes";

// A1 against a1_routes (synthetic data): the conversation, the four tabs, the approval; and a refused message shown in plain words.
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const BP = {
  intent_id: "i1", title: "Monthly performance pack", skill: "Architect playbook: a small family office",
  sow: { state: "signed", version: 1, signature: { name: "Arjun Mehta", role: "company_admin", at: "2026-10-07T10:00:00Z" },
    kpis: [{ code: "TWR", name: "Time-weighted return", status: "defined" }], sources: [{ id: "c", name: "Custodian positions", kind: "file" }],
    catalogue: [{ table: "positions", layer: "silver", meaning: "Positions typed" }] },
  turns: [
    { id: "t1", by: "person", name: "Leela Raman", text: "Please start.", at: "2026-10-08T09:00:00Z", did: [] },
    { id: "t2", by: "span", name: "Span", text: "I drafted the three layers.", at: "2026-10-08T09:00:05Z", did: ["Design drafted: 1 sources, 1 landing, 1 cleaned, 1 report tables."] },
  ],
  state: "ready", approved_by: null, approved_at: null, greeting: "",
  data_model: [{ table: "fact_account_month", kind: "fact", grain: "one row per account per month", keys: ["account_key"], relationships: ["joins dim_account on account_key"], history: "", measures: ["Time-weighted return"] },
    { table: "dim_account", kind: "dimension", grain: "one row per account per change", keys: ["account_key"], relationships: [], history: "type two: a row per change", measures: [] }],
  questions: [{ id: "q1", question: "Month-end: the custodian's statement date or the ledger close?", default: "the custodian statement date", why: "", answer: "", settled: false }],
  scope: ["TWR"],
  design: { lines: ["Landing keeps tables as they arrive."], fallback: false, message: null, counts: { gold: 1 }, at: "2026-10-08T09:00:05Z" },
  layers: { columns: [{ kind: "source", title: "Sources", items: [{ id: "source:c", label: "Custodian positions", about: "" }] },
    { kind: "bronze", title: "Landing", items: [] }, { kind: "silver", title: "Cleaned", items: [{ id: "silver:p", label: "silver.positions", about: "" }] },
    { kind: "gold", title: "Report", items: [{ id: "gold:twr", label: "gold.twr", about: "" }] }], links: [{ from: "source:c", to: "silver:p" }] },
  scan: { kpis: [{ code: "TWR", name: "Time-weighted return", status: "available", sources_used: ["c"], missing: [] }], agreed: null },
  mapping: { version: 1, rows: 3, unclear: 0, fallback: true },
  summary: ["Data model: 2 tables.", "Questions for the head of data: 1 open; approving accepts Span's defaults."],
  can_talk: true, can_approve: true,
};

function mock(chatStatus = 200) {
  const calls: { method: string; url: string }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ method, url });
    if (url.endsWith("/blueprint/chat") && method === "GET") return json(200, BP);
    if (url.endsWith("/blueprint/chat")) return chatStatus === 200 ? json(200, BP) : json(chatStatus, { error: "not_allowed", message: "Only the architect can do this." });
    if (url.endsWith("/benchmarks/sheet")) return json(200, { sheet: { version: 1, state: "draft", rows: [
      { id: "r1", code: "TWR", kpi: "Time-weighted return", dims: { period: "2026-09" }, reported: 1.2, expected: 1.2, tolerance: 0.1, dropped: false }] }, columns: [], sign_block: null, required: [], missing: [] });
    if (url.endsWith("/project")) return json(200, { id: "prj-1a2b3c4d" });
    if (url.endsWith("/blueprint/approve")) return json(200, { ...BP, state: "approved", approved_by: "Arjun Mehta", approved_at: "2026-10-08T10:00:00Z", can_approve: false });
    return json(404, {});
  }));
  return calls;
}
const view = () => render(
  <ThemeProvider><MemoryRouter initialEntries={["/centre/build/i1"]}><Routes>
    {routes.map((r) => <Route key={r.path} path={`/centre/${r.path}`} element={r.element} />)}
  </Routes></MemoryRouter></ThemeProvider>,
);

afterEach(() => vi.unstubAllGlobals());

test("the conversation, the four tabs and the head of data's approval", async () => {
  const calls = mock();
  view();
  expect(await screen.findByText("I drafted the three layers.")).toBeInTheDocument();
  expect(screen.getByRole("group", { name: "Design layers" })).toBeInTheDocument();
  expect(screen.getByText(/Skill: Architect playbook/)).toBeInTheDocument();
  expect(screen.getByRole("group", { name: "Data model diagram" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Answer in the conversation" }));
  expect((screen.getByLabelText("Your message") as HTMLTextAreaElement).value).toMatch(/^On "Month-end/);
  expect(screen.getByText(/These 1 of 1 can be built now/)).toBeInTheDocument();
  expect(await screen.findByText(/Time-weighted return \(2026-09\): reported 1.2, expect 1.2, within 0.1/)).toBeInTheDocument();  // Span reads the sheet
  expect(screen.getByRole("link", { name: "Open the benchmark sheet" })).toHaveAttribute("href", "/centre/project/prj-1a2b3c4d?artefact=benchmarks");
  fireEvent.click(screen.getByRole("button", { name: "Approve design and mapping for the engineer" }));
  expect(await screen.findByText(/Span handed the design and the mapping sheet to the build/)).toBeInTheDocument();
  expect(calls.some((c) => c.method === "POST" && c.url.endsWith("/blueprint/approve"))).toBe(true);
});

test("a refused message is shown in plain words", async () => {
  mock(403);
  view();
  fireEvent.change(await screen.findByLabelText("Your message"), { target: { value: "Draft it" } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Only the architect can do this."));
});
