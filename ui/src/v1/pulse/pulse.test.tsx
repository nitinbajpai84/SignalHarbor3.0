import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { routes } from "./routes";

// P2 Pulse against GET /api/v1/pulse; fetch is stubbed with synthetic data.
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const AT = "2026-10-08T09:30:00+00:00";
const PULSE = {
  name: "Arjun Mehta", may_start: true, seats: [{ id: "decision_maker", name: "Decision maker" }],
  needs_you: { refreshed: AT, cards: [{ id: "p:sd:comment", kind: "comment", project: "Performance pack", pid: "prj-0a1b2c3d",
    text: "2 comments on the system design need your answer.", action: "Answer",
    href: "/centre/project/prj-0a1b2c3d?artefact=design&line=3.2&comment=c1", since: "3 October 2026" }] },
  projects: { refreshed: AT, lines: [{ pid: "prj-0a1b2c3d", intent_id: "i1", title: "Performance pack", stage: "built", on: true,
    href: "/centre/project/prj-0a1b2c3d", last_load: { period: "2026-09", state: "loaded", reason: null },
    moved: { code: "TWR", name: "Return", unit: "%", period: "2026-09", from: 1, to: 1.3, change: 0.3 }, open_comments: 2, open_tickets: 1 }] },
  worth_a_look: { refreshed: AT, items: [{ id: "review-queue", kind: "document", text: "1 document needs a look in the review queue.", href: "/centre/extract/review" }] },
};
const at = () => render(
  <ThemeProvider><MemoryRouter initialEntries={["/centre/home"]}><Routes>
    {routes.map((r) => <Route key={r.path} path={`/centre/${r.path}`} element={r.element} />)}
  </Routes></MemoryRouter></ThemeProvider>);

afterEach(() => vi.unstubAllGlobals());

test("the three bands show and a comment card opens the exact line", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(200, PULSE)));
  at();
  expect(await screen.findByText("Pulse, Arjun")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Answer/ })).toHaveAttribute("href", "/centre/project/prj-0a1b2c3d?artefact=design&line=3.2&comment=c1");
  expect(screen.getByText(/Return: 1.3 % \(\+30.0 %\)/)).toBeInTheDocument();
  expect(screen.getByText("2 open comments")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /review queue/ })).toHaveAttribute("href", "/centre/extract/review");
  expect(screen.getAllByText(/^refreshed /)).toHaveLength(3);
});

test("a refused read says so and shows no work", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(403, { error: "forbidden", message: "You do not have access to this." })));
  at();
  expect(await screen.findByText(/do not have access/i)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Start a project" })).toBeNull();
});
