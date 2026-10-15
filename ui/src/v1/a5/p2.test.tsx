import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import { routes } from "./routes";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

// REAL shapes: sh_platform/v1/p2_assign.landing() and history() (see tests/v1/test_p2_assign.py).
const mine = { id: "a1", event: "assign", pid: "prj-1", title: "Monthly performance vs benchmark", steps: ["Architecture", "Pipelines"], to: "Leo Park", by: "Mei Chen",
  assigned_by: "Mei Chen", message: "Please use the administrator file.", due: "2026-10-16", at: "2026-10-11T11:12:00+00:00", link: "/centre/build/p/prj-1" };
const landing = (over: object = {}) => ({ viewer: "Leo Park", needs_me: [], worth_a_look: [], assigned_to_me: [mine], assigned_by_me: [], waiting_approval: [
  { kind: "plan", title: "Plan v2: Exposure by manager", project: "Exposure by manager", from: "Mei Chen", since: "2026-10-11", link: "/centre/build/p/prj-2/architecture" }],
  counts: { needs_me: 0, assigned_to_me: 1, assigned_by_me: 0, waiting_approval: 1, worth_a_look: 0 }, ...over });
const proj = { project: { id: "prj-1", title: "Monthly performance vs benchmark", owner: "Mei Chen" }, steps: [{ id: "architecture", label: "Architecture" },
  { id: "pipelines", label: "Pipelines" }, { id: "dashboards", label: "Dashboards and delivery" }], open: [], history: [] };

function mock(sent: string[], over: { landing?: object; fail?: boolean; review?: object } = {}) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Leo Park", company_id: "evergreen", roles: ["analyst"] });
    if (init?.method && init.method !== "GET") {
      sent.push(`${init.method} ${url} ${String(init.body ?? "")}`);
      return over.fail ? json(403, { error: "not_allowed", message: "Only the project owner can assign its steps." }) : json(200, mine);
    }
    if (url === "/api/v1/centre-map/review" && over.review) return json(200, over.review);
    if (url === "/api/v1/action/landing") return json(200, landing(over.landing));
    if (url.startsWith("/api/v1/pulse2/items")) return json(200, { role: "analyst", roles: ["analyst"], items: [] });
    if (url === "/api/v1/projects/prj-1/assignments") return json(200, proj);
    if (url === "/api/v1/comments/people") return json(200, [{ name: "Leo Park" }, { name: "Anita Rao" }]);
    return json(404, { error: "not_found", message: "Not found." });
  }));
}
const Where = () => <p data-testid="where">{useLocation().pathname}</p>;
function open(at: string) {
  render(<MemoryRouter initialEntries={[at]}><ThemeProvider><SessionProvider><Routes>
    {routes.map((r) => <Route key={r.path} path={`/centre/${r.path}`} element={r.element} />)}</Routes><Where /></SessionProvider></ThemeProvider></MemoryRouter>);
}

test("the landing shows Assigned to me with the message and due date, and Waiting for my approval", async () => {
  const sent: string[] = [];
  mock(sent);
  open("/centre/action");
  const assigned = await screen.findByRole("region", { name: /Assigned to me/ });
  expect(within(assigned).getByText(/Please use the administrator file/)).toBeInTheDocument();
  expect(within(assigned).getByText(/Due 16 Oct 2026/)).toBeInTheDocument();
  expect(within(assigned).getByRole("link", { name: "Open project" })).toHaveAttribute("href", "/centre/build/p/prj-1");
  expect(screen.getByRole("region", { name: /Waiting for my approval/ })).toHaveTextContent("Plan v2: Exposure by manager");
  expect(await screen.findByText(/2 things need you today/)).toBeInTheDocument();
  await userEvent.click(within(assigned).getByRole("button", { name: "Mark my part done" }));
  await waitFor(() => expect(sent).toEqual(["POST /api/v1/assignments/a1/done {}"]));
});

test("B5: the builder's card says it is new, who assigned it and the steps, and has Ask Mei a question", async () => {
  const sent: string[] = [];
  mock(sent);
  open("/centre/action");
  const assigned = await screen.findByRole("region", { name: /Assigned to me/ });
  expect(within(assigned).getByText("NEW · ASSIGNED TO YOU")).toBeInTheDocument();
  expect(within(assigned).getByText("Build · assigned by Mei Chen")).toBeInTheDocument();
  expect(within(assigned).getByRole("heading", { name: "Build: Monthly performance vs benchmark" })).toBeInTheDocument();
  expect(within(assigned).getByText("Architecture")).toBeInTheDocument();
  expect(await screen.findByText(/Before this: Mei Chen assigned you a step on .*Next: open the project and start architecture with Span\./)).toBeInTheDocument();
  await userEvent.click(within(assigned).getByRole("button", { name: "Ask Mei a question" }));
  await userEvent.type(within(assigned).getByLabelText("Your question to Mei"), "Which file is the administrator file?");
  await userEvent.click(within(assigned).getByRole("button", { name: "Send to Mei" }));
  await waitFor(() => expect(sent).toHaveLength(1));
  expect(sent[0]).toMatch(/^POST \/api\/v1\/projects\/prj-1\/comments /);
  expect(JSON.parse(sent[0]!.split(" ").slice(2).join(" "))).toEqual({ artefact: "intent", line_ref: null, to: "Mei Chen", text: "Which file is the administrator file?" });
  expect(await within(assigned).findByText(/Your question went to Mei/)).toBeInTheDocument();
});

test("B3: an intent waiting for the sponsor's signature opens the signing page", async () => {
  mock([], { landing: { assigned_to_me: [], waiting_approval: [{ kind: "intent", title: "Sign the intent: Monthly performance", project: "Monthly performance", from: "Mei Chen", since: "2026-10-11", link: "/centre/intent/i1/sign" }],
    counts: { needs_me: 0, assigned_to_me: 0, assigned_by_me: 0, waiting_approval: 1, worth_a_look: 0 } } });
  open("/centre/action");
  const waiting = await screen.findByRole("region", { name: /Waiting for my approval/ });
  expect(within(waiting).getByText(/Intent to sign from Mei Chen/)).toBeInTheDocument();
  expect(within(waiting).getByRole("link", { name: /Sign/ })).toHaveAttribute("href", "/centre/intent/i1/sign");
});

test("an empty landing says nothing needs you and shows no empty sections", async () => {
  mock([], { landing: { assigned_to_me: [], waiting_approval: [], counts: { needs_me: 0, assigned_to_me: 0, assigned_by_me: 0, waiting_approval: 0, worth_a_look: 0 } } });
  open("/centre/action");
  expect(await screen.findByText(/^Good (morning|afternoon|evening), Leo\. Nothing needs you today\./)).toBeInTheDocument();
  expect(screen.queryByRole("region", { name: /Assigned to me/ })).toBeNull();
});

test("Assign a step sends the chosen steps, person, message and due date, then returns to Action", async () => {
  const sent: string[] = [];
  mock(sent);
  open("/centre/action/assign/prj-1");
  await userEvent.click(await screen.findByLabelText("Dashboards and delivery"));  // all three start ticked; untick one
  await userEvent.selectOptions(await screen.findByLabelText("Who"), "Anita Rao");
  await userEvent.type(screen.getByLabelText("Message"), "Check the blend");
  await userEvent.type(screen.getByLabelText("Due date"), "2026-10-16");
  await userEvent.click(screen.getByRole("button", { name: "Assign to Anita Rao" }));
  await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("/centre/action"));
  expect((sent[0] ?? "").startsWith("POST /api/v1/projects/prj-1/assign ")).toBe(true);
  expect(JSON.parse((sent[0] ?? "").replace("POST /api/v1/projects/prj-1/assign ", ""))).toEqual(
    { steps: ["architecture", "pipelines"], to: "Anita Rao", message: "Check the blend", due: "2026-10-16" });
});

test("hand over needs a person, and a refusal is shown in plain words", async () => {
  const sent: string[] = [];
  mock(sent, { fail: true });
  open("/centre/action/assign/prj-1?mode=handover");
  const button = await screen.findByRole("button", { name: "Hand over" });
  expect(button).toBeDisabled();
  expect(screen.queryByLabelText("Architecture")).toBeNull();
  await userEvent.selectOptions(screen.getByLabelText("Who"), "Leo Park");
  await userEvent.click(screen.getByRole("button", { name: "Hand over to Leo Park" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Only the project owner can assign its steps.");
  expect(sent[0]).toContain("/api/v1/projects/prj-1/handover ");
  expect(screen.getByTestId("where")).toHaveTextContent("/centre/action/assign/prj-1");
});

test("a project the person may not read shows the refusal and no form", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => url === "/api/auth/me" ? json(200, { display_name: "Rina", company_id: "e", roles: ["participant"] })
    : url === "/api/v1/comments/people" ? json(200, []) : json(403, { error: "not_allowed", message: "This project is restricted. Ask for access if you need it." })));
  open("/centre/action/assign/prj-1");
  expect(await screen.findByRole("alert")).toHaveTextContent("Ask for access");
  expect(screen.queryByRole("button", { name: /Assign|Hand over/ })).toBeNull();
});

test("map items waiting for the head of data show under Waiting for my approval and link to the review page", async () => {
  mock([], { review: { allowed: true, can_review: true, projects: [], totals: { waiting: 4 } } });
  open("/centre/action");
  const waiting = await screen.findByRole("region", { name: /Waiting for my approval/ });
  await waitFor(() => expect(within(waiting).getByRole("link", { name: "Review 4" })).toHaveAttribute("href", "/centre/map/review"));
  expect(waiting).toHaveTextContent("Map review");
});
