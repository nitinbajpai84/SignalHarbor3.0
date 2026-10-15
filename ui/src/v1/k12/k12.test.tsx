import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { routes } from "./routes";

const D = {
  source: "sample", total: 3, counts: { strong: 1, partial: 1, not_in_scope: 1 },
  clusters: [
    { cluster: "Liquidity", items: [
      { id: "A", cluster: "Liquidity", title: "Cash is slow", severity: "high", does: "One band.", coverage: "strong", reason: "", use_case: "Daily key numbers", link: "/centre/consume" },
      { id: "B", cluster: "Liquidity", title: "Calls are late", severity: "medium", does: "Flags calls.", coverage: "partial", reason: "", use_case: "Outlook", link: "/centre/consume/signals" }] },
    { cluster: "Operations", items: [
      { id: "C", cluster: "Operations", title: "Booking trades", severity: "high", does: "Reads positions.", coverage: "not_in_scope", reason: "Covered by your portfolio data management system.", use_case: "", link: "" }] },
  ],
};
const at = (path = "/centre/demo/painpoints") => render(
  <ThemeProvider><MemoryRouter initialEntries={[path]}><Routes>{routes.map((r) => <Route key={r.path} path={`/centre/${r.path}`} element={r.element} />)}</Routes></MemoryRouter></ThemeProvider>,
);
afterEach(() => vi.unstubAllGlobals());
const stub = (status = 200, seen: string[] = []) => vi.stubGlobal("fetch", vi.fn(async (u: string) => { seen.push(u); return new Response(JSON.stringify(status === 200 ? D : { message: "x" }), { status, headers: { "Content-Type": "application/json" } }); }));

test("walks clusters with coverage chips and Show me links", async () => {
  stub();
  at();
  expect(await screen.findByText("Cash is slow")).toBeTruthy();
  expect(screen.getByText("1 covered", { exact: false })).toBeTruthy();
  expect(screen.getByText("Covered")).toBeTruthy();
  expect(screen.getByText("Partly covered")).toBeTruthy();
  expect(screen.getByRole("link", { name: "Show me: Daily key numbers" }).getAttribute("href")).toBe("/centre/consume");
  fireEvent.click(screen.getByRole("button", { name: /Operations/ }));
  expect(await screen.findByText("Not in scope")).toBeTruthy();
  expect(screen.getByText("Covered by your portfolio data management system.")).toBeTruthy();
  expect(screen.queryByRole("link", { name: /Show me/ })).toBeNull();
});

test("passes ?name= to the server", async () => {
  const seen: string[] = [];
  stub(200, seen);
  at("/centre/demo/painpoints?name=acme");
  await screen.findByText("Cash is slow");
  expect(seen[0]).toBe("/api/v1/demo/painpoints?name=acme");
});

test("says so when the list cannot load", async () => {
  stub(500);
  at();
  expect((await screen.findByRole("alert")).textContent).toContain("could not load");
});
