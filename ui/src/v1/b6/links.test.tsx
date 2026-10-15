import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import ProjectsPage from "./ProjectsPage";

const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());

// Guard: the Build list must keep reaching every older room, Ops and intake, Projects today (moved from Action, CR1) and Start a new intent (now New project, V5).
it("links to every Build room, Ops and intake", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => url === "/api/auth/me"
    ? json({ display_name: "Anna", company_id: "evergreen", roles: ["analyst"] })
    : json({ projects: [{ id: "EV-0003", intent_id: "IN-7", title: "Monthly", owner: "Priya", stage: "build", plan_state: "proposed" }] })));
  render(<ThemeProvider><MemoryRouter><SessionProvider><ProjectsPage /></SessionProvider></MemoryRouter></ThemeProvider>);
  await screen.findByText("Design with Span");
  const hrefs = screen.getAllByRole("link").map((a) => a.getAttribute("href"));
  for (const h of ["/centre/build/IN-7", "/centre/build/IN-7/scan", "/centre/build/IN-7/mapping", "/centre/build/IN-7/engineer", "/centre/build/IN-7/runs",
    "/centre/build/IN-7/deviations", "/centre/project/EV-0003", "/centre/build/ops", "/centre/data/intake", "/centre/action", "/centre/build/new"]) expect(hrefs).toContain(h);
  expect(hrefs).not.toContain("/centre/home"); // ROLE1: Pulse is no longer a destination
});
