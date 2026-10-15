import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import AdminRules from "./AdminRules";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

const v = { rule_version_id: "v1", rule_code: "cash_tolerance", rule_type: "tolerance", owner: "Mei Tan", version_number: 2,
  definition_text: "Cash may differ by 5,000 USD per entity per day.", parameters: {}, effective_from: "2026-11-01", effective_to: null,
  state: "draft", approved_by: null, approved_at: null };

test("the table shows the rule in words and a waiting version can be approved", async () => {
  const sent: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Raj Iyer", company_id: "x", roles: ["analyst"] });
    if (init?.method === "POST") { sent.push(url); return json(200, { ...v, state: "approved" }); }
    if (url === "/api/v1/rules") return json(200, [{ ...v, in_force: false, waiting: 1 }]);
    if (url.endsWith("/history")) return json(200, [v]);
    return json(404, { error: "not_found", message: "Not found." });
  }));
  render(<MemoryRouter><ThemeProvider><SessionProvider><AdminRules /></SessionProvider></ThemeProvider></MemoryRouter>);
  expect(await screen.findByText("Cash may differ by 5,000 USD per entity per day.")).toBeInTheDocument();
  expect(screen.getByText(/1 new version waiting/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "cash tolerance" }));
  await userEvent.click(await screen.findByRole("button", { name: "Approve" }));
  expect(sent).toEqual(["/api/v1/rules/versions/v1/approve"]);
});

test("the approver reads the register, sees the benchmark versions, and is offered no proposing or signing (P15)", async () => {
  const bench = { ...v, rule_version_id: "benchmark:EG-OFFICE-BLEND", rule_code: "EG-OFFICE-BLEND", rule_type: "benchmark", owner: null, effective_from: "2026-10-01",
    definition_text: "Benchmark Evergreen office benchmark: version 1 (2026-01-01) approved; version 2 (2026-10-01) still in progress.", in_force: true, waiting: 1 };
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Raj Patel", company_id: "x", roles: ["approver"] });
    if (url === "/api/v1/rules") return json(200, [{ ...v, in_force: false, waiting: 1 }, bench]);
    if (url.endsWith("/history")) return json(200, [v]);
    return json(404, { error: "not_found", message: "Not found." });
  }));
  render(<MemoryRouter><ThemeProvider><SessionProvider><AdminRules /></SessionProvider></ThemeProvider></MemoryRouter>);
  expect(await screen.findByText(/version 2 \(2026-10-01\) still in progress/)).toBeInTheDocument();
  expect(screen.getByText("Benchmark EG-OFFICE-BLEND")).toBeInTheDocument();
  expect(screen.getByText("Each version is signed by a second person, named beside it")).toBeInTheDocument();   // analyst-uc4-03: not "Not named"
  expect(screen.queryByText("Agents and templates")).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "cash tolerance" }));
  expect(await screen.findByText(/Version 2, from 2026-11-01/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Send for signature" })).toBeNull();
});
