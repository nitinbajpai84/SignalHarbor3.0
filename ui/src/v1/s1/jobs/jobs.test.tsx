import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { ThemeProvider } from "../../../theme";
import { SessionProvider } from "../../../useSession";
import JobsPage from "./JobsPage";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

const failed = { id: "j1", name: "d1.tick", state: "failed", tries: 3, max_tries: 3, error: "OSError: disk full", queued_at: "2026-10-11T08:00:00+00:00", started_at: null, finished_at: "2026-10-11T08:01:00+00:00" };
const view = { mode: "production", stats: { queued: 1, running: 0, retrying: 0, done: 4, failed: 1 }, failed: [failed],
  jobs: [failed, { ...failed, id: "j2", name: "b6.run", state: "done", error: null }], events: [{ id: 5, topic: "badge.action", at: "2026-10-11T08:02:00+00:00", payload: {} }] };

function mock(sent: string[]) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Mei", company_id: "evergreen", roles: ["analyst"] });
    if (init?.method === "POST") { sent.push(`${init.method} ${url}`); return json(200, { retried: "j1" }); }
    if (url === "/api/v1/jobs") return json(200, view);
    return json(404, { error: "not_found", message: "Not found." });
  }));
}
const wrap = () => render(<MemoryRouter><ThemeProvider><SessionProvider><JobsPage /></SessionProvider></ThemeProvider></MemoryRouter>);

test("shows the mode, what failed in words, and recent events", async () => {
  mock([]);
  wrap();
  expect(await screen.findByText(/Production mode: a worker runs the jobs/)).toBeInTheDocument();
  expect(screen.getByText("OSError: disk full")).toBeInTheDocument();
  expect(screen.getAllByText("Delivery check").length).toBeGreaterThan(0);
  expect(screen.getByText(/Something new in Action/)).toBeInTheDocument();
});

test("Send again posts the retry", async () => {
  const sent: string[] = [];
  mock(sent);
  wrap();
  await userEvent.click(await screen.findByRole("button", { name: "Send again" }));
  expect(sent[0]).toBe("POST /api/v1/jobs/j1/retry");
});

test("V6: in simple mode the pipeline runs that happened inside the server are listed, not 'No jobs yet'", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Mei", company_id: "evergreen", roles: ["analyst"] });
    if (url === "/api/v1/jobs") return json(200, { mode: "simple", stats: { queued: 0, running: 0, retrying: 0, done: 0, failed: 0 }, failed: [], jobs: [], events: [],
      runs: [{ project_id: "p1", title: "Monthly performance", run_id: "r2", mode: "live", status: "ok", started: "2026-10-11T05:10:00+00:00", finished: "2026-10-11T05:10:03+00:00" },
        { project_id: "p1", title: "Monthly performance", run_id: "r1", mode: "sandbox", status: "ok", started: "2026-10-11T04:40:00+00:00", finished: null }] });
    return json(404, { error: "not_found", message: "Not found." });
  }));
  wrap();
  expect(await screen.findByText("Live run")).toBeInTheDocument();
  expect(screen.getByText("Trial run on a copy")).toBeInTheDocument();
  expect(screen.getAllByText("Monthly performance")).toHaveLength(2);
  expect(screen.getByText(/In simple mode a pipeline run happens inside the server and is listed above/)).toBeInTheDocument();
});
