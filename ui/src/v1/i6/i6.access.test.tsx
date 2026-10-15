import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { routes } from "./routes";

// UC9-09: an approver or participant the page lets in never calls the context library (c4.permissions.yaml: admin, sponsor, analyst).
vi.mock("../../useSession", () => ({ useSessionIfAny: () => ({ user: { roles: ["approver"] } }) }));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const SOW = {
  id: "s1", intent_id: "i1", title: "Monthly report", state: "signed", version: 1,
  goal: { line: "Monthly report", why: "", readers: [], decisions: [], needed_by: "" }, process: { steps: [], handovers: [] }, catalogue: [], governance: [],
  sources: [], kpis: [], unclear: [], signature: { name: "Daniel Foo", role: "sponsor", at: "2026-10-03T09:00:00Z" },
};
const CHAT = { id: "i1", intent_id: "i1", project_id: null, state: "sow_ready", needs_done: [], sow: SOW, process_map: SOW.process, turns: [] };

afterEach(() => vi.unstubAllGlobals());

test("a reader without a context role opens a signed intent with no call to the context library", async () => {
  const urls: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string) => { urls.push(url); return url.endsWith("/chat") ? json(200, CHAT) : json(404, {}); }));
  render(<ThemeProvider><MemoryRouter initialEntries={["/centre/intent/i1"]}><Routes>
    {routes.map((r) => <Route key={r.path} path={`/centre/${r.path}`} element={r.element} />)}
  </Routes></MemoryRouter></ThemeProvider>);
  expect(await screen.findByRole("button", { name: "Read the procedure here" })).toBeInTheDocument();
  expect(urls.filter((u) => u.includes("/context"))).toEqual([]);
  expect(screen.queryByRole("button", { name: "Add context for a more relevant conversation" })).toBeNull();
});
