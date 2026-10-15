import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { routes as p1 } from "../p1/routes";
import { routes as pulse } from "../pulse/routes";

// G1 screens: the lock with Request access, the owner's Approve / Not now card in Pulse, and the access answer in the project header.
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const LOCK = { id: "prj-1a2b3c4d", locked: true, access: "preview", sensitivity: "internal", can_request: true, title: "Fee review", stage: "signed", owner: "Priya Nair", request: null };
const PROJECT = {
  id: "prj-1a2b3c4d", intent_id: "ini-1", title: "Fee review", started_by: "Priya Nair", started_at: "2026-10-08T09:00:00Z", stage: "talking", artefacts: [],
  people: { raiser: "Priya Nair", sponsor: null, builder: null, head_of_data: null, ops: null },
};
const ACCESS = { id: "prj-1a2b3c4d", level: "full", sensitivity: "internal", can_manage: true, team: [{ name: "Priya Nair", role: "raiser", account_id: null }, { name: "Leela Raman", role: "builder", account_id: null }],
  requests: [{ id: "acc_1", requester: "Dev Sharma", reason: "I run the fee desk", at: "2026-10-08T09:00:00Z" }] };
const AT = "2026-10-08T09:30:00+00:00";
const PULSE = { name: "Priya Nair", may_start: false, seats: [], projects: { refreshed: AT, lines: [] }, worth_a_look: { refreshed: AT, items: [] },
  needs_you: { refreshed: AT, cards: [{ id: "acc", kind: "access", project: "Fee review", pid: "prj-1a2b3c4d", text: "Dev Sharma asks for access", action: "Approve / Not now", href: "/centre/project/prj-1a2b3c4d", since: null }] } };

function mock(project: unknown) {
  const calls: { method: string; url: string; body?: Record<string, unknown> }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    if (url === "/api/v1/pulse") return json(200, PULSE);
    if (url.endsWith("/access") && method === "GET") return json(200, ACCESS);
    if (url.includes("/access")) return json(200, {});
    if (url.includes("/artefacts/")) return json(404, {});
    return json(200, project);
  }));
  return calls;
}
const view = (at: string) => render(
  <ThemeProvider><MemoryRouter initialEntries={[at]}><Routes>
    {[...p1, ...pulse].map((r) => <Route key={r.path} path={`/centre/${r.path}`} element={r.element} />)}
  </Routes></MemoryRouter></ThemeProvider>);

afterEach(() => vi.unstubAllGlobals());

test("a locked project shows its title, stage and owner and sends a request to the owner", async () => {
  const calls = mock(LOCK);
  view("/centre/project/prj-1a2b3c4d");
  expect(await screen.findByRole("heading", { name: "Fee review" })).toBeInTheDocument();
  expect(screen.getByText(/Stage: signed. Owner: Priya Nair./)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Request access" }));
  fireEvent.change(screen.getByLabelText("Why you need this project"), { target: { value: "I run the fee desk" } });
  fireEvent.click(screen.getByRole("button", { name: "Send request" }));
  expect(await screen.findByText(/Requested: waiting for Priya Nair/)).toBeInTheDocument();
  expect(calls.find((c) => c.method === "POST")).toMatchObject({ url: "/api/v1/projects/prj-1a2b3c4d/access/request", body: { reason: "I run the fee desk" } });
});

test("a Restricted project shows only that it exists", async () => {
  mock({ ...LOCK, access: "none", sensitivity: "restricted", title: undefined, owner: undefined, stage: undefined });
  view("/centre/project/prj-1a2b3c4d");
  expect(await screen.findByRole("heading", { name: "A project you cannot see" })).toBeInTheDocument();
  expect(screen.queryByText(/Priya Nair/)).toBeNull();
});

test("the header answers Open, Internal or Restricted with the team, and the owner can change it", async () => {
  const calls = mock(PROJECT);
  view("/centre/project/prj-1a2b3c4d");
  expect(await screen.findByText(/Only the team and company administrators can read this project. Others see its title/)).toBeInTheDocument();
  expect(screen.getByText(/Team: Priya Nair, Leela Raman./)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Change who can see this project"), { target: { value: "restricted" } });
  await waitFor(() => expect(calls.find((c) => c.method === "PUT")).toMatchObject({ url: "/api/v1/projects/prj-1a2b3c4d/access", body: { sensitivity: "restricted" } }));
});

test("the owner answers a request from the Pulse card", async () => {
  const calls = mock(PROJECT);
  view("/centre/home");
  expect(await screen.findByText(/Dev Sharma asks to use Fee review/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Approve" }));
  await waitFor(() => expect(calls.find((c) => c.method === "POST")).toMatchObject({ url: "/api/v1/projects/prj-1a2b3c4d/access/answer/acc_1", body: { approve: true, days: 30 } }));
});

test("NU-16: the owner who lands on the project page from the access comment answers it there (Approve / Not now)", async () => {
  const calls = mock(PROJECT);
  view("/centre/project/prj-1a2b3c4d?artefact=intent&comment=c1");
  const box = await screen.findByRole("region", { name: "Requests to read this project" });
  expect(box).toHaveTextContent(/Dev Sharma asks to use Fee review\. "I run the fee desk"/);
  fireEvent.click(screen.getAllByRole("button", { name: "Not now" })[0]!);
  await waitFor(() => expect(calls.find((c) => c.method === "POST")).toMatchObject({ url: "/api/v1/projects/prj-1a2b3c4d/access/answer/acc_1", body: { approve: false } }));
});
