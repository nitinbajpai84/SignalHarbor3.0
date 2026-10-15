import type { ReactElement } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import TicketPage from "./TicketPage";
import TicketsPage from "./TicketsPage";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

const row = { id: "TCK-0001", title: "Which column is the fee?", project: "prj-0000abcd", project_title: "Monthly pack", stage: "build", stage_name: "Build centre",
  assigned_to: "Leela Raman", assigned_name: "Leela Raman", raised_by: "flow", raised_name: "Flow", state: "open", priority: "normal", due: null,
  created_at: "2026-10-08T10:42:00+00:00", last_change: { at: "2026-10-08T10:42:00+00:00", text: "Flow raised it to Leela Raman on 8 Oct 10:42." }, age_days: 0 };
const full = { ...row, body: "Two columns look like fees.", can_act: true, links: [
  { kind: "line", ref: "prj-0000abcd:build_pack:2.1", label: "Build pack, line 2.1", href: "/centre/project/prj-0000abcd?artefact=build_pack&line=2.1", locked: false },
  { kind: "artefact", ref: "prj-1:design", label: "x", href: null, locked: true, preview: "Private project, designed, owner Priya Nair" }],
  log: [{ at: "2026-10-08T10:42:00+00:00", by: "flow", action: "raised", from: null, to: "Leela Raman", note: "", text: "Flow raised it to Leela Raman on 8 Oct 10:42." }] };

function mock(sent: string[]) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Leela Raman", company_id: "neera", roles: ["analyst"] });
    if (init?.method && init.method !== "GET") sent.push(`${init.method} ${url} ${String(init.body ?? "")}`);
    if (url.startsWith("/api/v1/tickets/people")) return json(200, { people: ["Dev Sharma"], agents: {} });
    if (url.endsWith("/delegate")) return json(200, { ...full, assigned_to: "Dev Sharma", assigned_name: "Dev Sharma" });
    if (url === "/api/v1/tickets/TCK-0001") return json(200, full);
    if (url.startsWith("/api/v1/tickets")) return json(200, { tickets: [row], stages: {} });
    return json(404, { error: "not_found", message: "Not found." });
  }));
}
const wrap = (el: ReactElement, at: string) => render(<MemoryRouter initialEntries={[at]}><ThemeProvider><SessionProvider>
  <Routes><Route path="/centre/tickets" element={el} /><Route path="/centre/tickets/:id" element={el} /></Routes></SessionProvider></ThemeProvider></MemoryRouter>);

test("the list asks for my tickets by default and shows number, project and stage", async () => {
  mock([]);
  wrap(<TicketsPage />, "/centre/tickets");
  expect(await screen.findByRole("link", { name: "TCK-0001" })).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "Build centre" })).toBeInTheDocument();
  const asked = (fetch as unknown as { mock: { calls: string[][] } }).mock.calls.map((c) => c[0]).find((u) => u?.startsWith("/api/v1/tickets?"));
  expect(asked).toContain("assignee=me");
});

test("the ticket page shows the log, a locked link and delegates with a note", async () => {
  const sent: string[] = [];
  mock(sent);
  wrap(<TicketPage />, "/centre/tickets/TCK-0001");
  expect((await screen.findAllByText("Flow raised it to Leela Raman on 8 Oct 10:42.")).length).toBeGreaterThan(0);
  expect(screen.getByRole("link", { name: "Build pack, line 2.1" })).toHaveAttribute("href", expect.stringContaining("line=2.1"));
  expect(screen.getByText(/Locked: Private project/)).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("A note"), "he owns the custodian file");
  await userEvent.type(screen.getByLabelText("Delegate to"), "Dev Sharma");
  await userEvent.click(screen.getByRole("button", { name: "Delegate" }));
  expect(sent[0]).toMatch(/^POST \/api\/v1\/tickets\/TCK-0001\/delegate .*Dev Sharma.*custodian/);
});
