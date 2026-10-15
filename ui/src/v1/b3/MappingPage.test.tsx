import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import MappingPage from "./MappingPage";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const row = (n: number, layer: string, status: string) => ({ n, layer, target_table: `t${n}`, target_field: "market_value", source_id: "custodian",
  source_table: "positions.csv", source_field: "Market Value", transformation: "Rename Market Value to market_value, cast to a decimal number.",
  rule: "", test: "Is a number; not empty.", status });
const view = { sheet: { intent_id: "i1", version: 1, rows: [row(1, "landing", "mapped"), row(2, "silver", "unclear")] }, fallback: true,
  message: "Span could not reach the model. The transformations come from the field types and names.", drafted_at: "2026-10-07T10:00:00+00:00" };

function mock(roles: string[], sheet: unknown, sent: string[]) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Leela Raman", company_id: "neera", roles });
    if (init?.method === "PUT") { sent.push(`${url} ${String(init.body)}`); return json(200, { row: row(2, "silver", "mapped") }); }
    if (init?.method === "POST") { sent.push(url); return json(200, view); }
    return sheet ? json(200, sheet) : json(404, { error: "not_found", message: "There is no mapping sheet for this intent yet." });
  }));
}
const wrap = () => render(<MemoryRouter initialEntries={["/centre/build/i1/mapping"]}><ThemeProvider><SessionProvider><Routes>
  <Route path="/centre/build/:iid/mapping" element={<MappingPage />} /></Routes></SessionProvider></ThemeProvider></MemoryRouter>);
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

test("the architect filters the sheet, edits a row and sees the fallback label", async () => {
  const sent: string[] = [];
  mock(["analyst"], view, sent);
  wrap();
  expect(await screen.findByText(/2 rows, 1 unclear/)).toBeInTheDocument();
  expect(screen.getByText(/could not reach the model/)).toBeInTheDocument();
  await userEvent.click(screen.getByText("Unclear", { selector: "button, a" }));
  expect(screen.queryByText("t1.market_value")).toBeNull();
  await userEvent.click(await screen.findByRole("button", { name: "Edit row 2" }));
  await userEvent.selectOptions(screen.getByLabelText("Status"), "mapped");
  await userEvent.click(screen.getByRole("button", { name: "Save row" }));
  expect(sent[0]).toMatch(/^\/api\/v1\/build\/i1\/mapping\/rows\/2 .*"status":"mapped"/);
});

test("no sheet yet: a sponsor sees the empty state and no draft button", async () => {
  mock(["sponsor"], null, []);
  wrap();
  expect(await screen.findByText("No mapping sheet yet")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Ask Span/ })).toBeNull();
});
