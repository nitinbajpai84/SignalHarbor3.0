import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import ProjectsPage from "../b6/ProjectsPage";
import RoomSwitcher from "../b8/RoomSwitcher";
import { InStep, IntentByProject } from "./StepPages";
import { filterRows, viewRow, waitingForMe, type RowPlus } from "./progress";
import { events, stepViews, headline, currentStep } from "./overview";
import HandoverPage from "./HandoverPage";
import ProjectOverview from "./ProjectOverview";
import StepIcon from "./StepIcons";
import { STEPS } from "./steps";
import { EXPLAINER_SRC } from "./ExplainerVideo";

const json = (status: number, body: unknown, type = "application/json") => new Response(JSON.stringify(body), { status, headers: { "Content-Type": type } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

const ROWS: RowPlus[] = [
  { id: "P1", title: "Monthly investment report", owner: "Anna", stage: "live", plan_state: "live" },
  { id: "P2", title: "Exposure by manager", owner: "Mei", stage: "build", plan_state: "proposed" },
  { id: "P3", title: "Benchmark pack", owner: "Anna", stage: "intent", plan_state: null },
  { id: "P4", title: "Capital calls", owner: "Raj", stage: "build", plan_state: "approved" },
];

describe("step icons", () => {
  test("one shared component draws all four", () => {
    for (const s of STEPS) {
      const { container, unmount } = render(<StepIcon step={s.id} />);
      expect(container.querySelector(`svg[data-step-icon="${s.id}"]`)).not.toBeNull();
      unmount();
    }
  });
});

describe("where a project stands", () => {
  test("each stage reads as a step with plain words", () => {
    expect(viewRow(ROWS[0]!)).toMatchObject({ current: "dashboards", live: true, marks: ["done", "done", "done", "done"] });
    expect(viewRow(ROWS[1]!)).toMatchObject({ current: "architecture", marks: ["done", "waiting", "todo", "todo"], tag: "WITH THE DATA TEAM · ARCHITECTURE" });
    expect(viewRow(ROWS[2]!)).toMatchObject({ current: "intent", marks: ["here", "todo", "todo", "todo"] });
    expect(viewRow(ROWS[3]!)).toMatchObject({ current: "pipelines", marks: ["done", "done", "here", "todo"] });
  });

  test("the filters: waiting for me needs the approving role; mine matches the owner; live", () => {
    expect(filterRows(ROWS, "waiting", "Anna", true).map((r) => r.id)).toEqual(["P2"]);
    expect(filterRows(ROWS, "waiting", "Anna", false)).toEqual([]);
    expect(filterRows(ROWS, "mine", "Anna", true).map((r) => r.id)).toEqual(["P1", "P3"]);
    expect(filterRows(ROWS, "live", "Anna", true).map((r) => r.id)).toEqual(["P1"]);
    expect(waitingForMe({ ...ROWS[3]!, waiting_for_me: true }, false)).toBe(true); // the server's word wins
  });
});

function landing(rows: unknown[], film: Response | Error, roles = ["analyst", "head_of_data"]) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Anna", company_id: "evergreen", roles });
    if (url === EXPLAINER_SRC) { if (film instanceof Error) throw film; return film; }
    if (url === "/api/v1/build/projects") return json(200, { projects: rows });
    void init;
    return json(404, { error: "not_found", message: "Not found." });
  }));
  return render(<MemoryRouter initialEntries={["/centre/build"]}><ThemeProvider><SessionProvider><Routes><Route path="/centre/build" element={<ProjectsPage />} /></Routes></SessionProvider></ThemeProvider></MemoryRouter>);
}

describe("Build landing", () => {
  test("cards with a mini step strip, Go to step, New project, and filters with counts", async () => {
    landing(ROWS, json(404, {}));
    expect(await screen.findByText("Exposure by manager")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "New project" })).toHaveAttribute("href", "/centre/build/new");
    expect(screen.getByRole("heading", { level: 1, name: "Build something new, one step at a time" })).toBeInTheDocument();   // V6 (A1)
    expect(screen.getByRole("list", { name: "The four steps" }).querySelectorAll(".b9-stepcard")).toHaveLength(4);
    expect(screen.getByText("Dashboards and delivery")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "All · 4" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Waiting for me · 1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Mine · 2" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Live · 1" })).toBeInTheDocument();
    expect(screen.getAllByRole("list", { name: "Progress" })).toHaveLength(4);
    const hrefs = screen.getAllByRole("link", { name: "Go to step" }).map((a) => a.getAttribute("href"));
    expect(hrefs).toEqual(["/centre/build/p/P1/dashboards", "/centre/build/p/P2/architecture", "/centre/build/p/P3/intent", "/centre/build/p/P4/pipelines"]);
    expect(screen.getByText("WAITING FOR YOU · ARCHITECTURE")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Waiting for me · 1" }));
    expect(screen.queryByText("Benchmark pack")).toBeNull();
    expect(screen.getByText("Exposure by manager")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Live · 1" }));
    expect(screen.getByText("Monthly investment report")).toBeInTheDocument();
    expect(screen.queryByText("Exposure by manager")).toBeNull();
  });

  test("with no film served, the poster and the chapters show and nothing plays", async () => {
    const { container } = landing(ROWS, json(200, { html: true }));
    expect(await screen.findByText("From a need in your words to a report people receive")).toBeInTheDocument();
    expect(screen.getByText("Say what you need")).toBeInTheDocument();
    expect(screen.getByText("Deliver")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /film is not available/ })).toBeInTheDocument();   // V6 (A1): the poster has its play button and the four step icons
    expect(container.querySelectorAll(".b9-poster__steps svg")).toHaveLength(4);
    expect(container.querySelector("video")).toBeNull();
  });

  test("with the film served, it plays and a chapter jumps to its time", async () => {
    const { container } = landing(ROWS, new Response("", { status: 200, headers: { "Content-Type": "video/mp4" } }));
    await waitFor(() => expect(container.querySelector("video")).not.toBeNull());
    expect(container.querySelector("video")?.getAttribute("src")).toBe("/static/explainer.mp4");
    const v = container.querySelector("video") as HTMLVideoElement;
    v.play = vi.fn(async () => undefined);
    await userEvent.click(screen.getByRole("button", { name: /The data team builds/ }));
    expect(v.currentTime).toBe(20);
  });

  test("a film request that fails leaves the poster, not an error", async () => {
    landing([], new Error("offline"));
    expect((await screen.findAllByText("No projects yet.", { exact: false })).length).toBeGreaterThan(0);
    expect(screen.getByText("From a need in your words to a report people receive")).toBeInTheDocument();
  });
});

const PROJECT = {
  id: "P4", intent_id: "IN-4", title: "Monthly performance against benchmark", started_by: "Mei Chen", started_at: "2026-10-09T14:02:00Z", stage: "signed",
  artefacts: [{ kind: "intent", record_path: "x", version: 1, state: "signed", signed_by: "Daniel Foo", signed_at: "2026-10-11T10:40:00Z" }],
  people: { raiser: "Mei Chen", sponsor: "Daniel Foo", builder: null, head_of_data: "Anita Rao", ops: null },
};

function overviewWorld(assigns: unknown[], sent: string[], opts: { candidates?: boolean } = {}) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Mei Chen", account_id: "u-mei", company_id: "evergreen", roles: ["analyst"] });
    if (init?.method && init.method !== "GET") { sent.push(`${init.method} ${url} ${String(init.body ?? "")}`); return json(200, { assignments: [] }); }
    if (url === "/api/v1/projects/P4") return json(200, PROJECT);
    if (url === "/api/v1/projects/P4/assignments") return json(200, { assignments: assigns });
    if (url === "/api/v1/projects/P4/assign/candidates") return opts.candidates === false ? json(404, { error: "not_found", message: "x" }) : json(200, { people: [{ id: "u-leo", name: "Leo Park", role: "Data engineer", open_steps: 2 }] });
    if (url === "/api/v1/build/p/P4/plan") return json(200, { project_id: "P4", plan: null, state: null, intent_signed: true });
    if (url === "/api/v1/build/p/P4/runs") return json(200, { runs: [] });
    if (url === "/api/v1/build/p/P4/studio") return json(200, { can_make: true, dashboards: [] });
    if (url === "/api/v1/model/projects/P4/tables") return json(200, { bronze: [], silver: [], gold: [] });
    return json(404, { error: "not_found", message: "Not found." });
  }));
  return render(<MemoryRouter initialEntries={["/centre/build/p/P4/overview"]}><ThemeProvider><SessionProvider><Routes>
    <Route path="/centre/build/p/:projectId/overview" element={<ProjectOverview />} /></Routes></SessionProvider></ThemeProvider></MemoryRouter>);
}

describe("project overview", () => {
  test("four steps with status and people, the timeline from records, and the next thing to do", async () => {
    overviewWorld([], []);
    expect(await screen.findByText("STEP 2 OF 4 · NEEDS A BUILDER")).toBeInTheDocument();
    const arch = screen.getByRole("region", { name: "Step 2: Architecture" });
    expect(within(arch).getByText("Needs a builder")).toBeInTheDocument();
    expect(within(arch).getByText("Not assigned yet")).toBeInTheDocument();
    expect(within(arch).getByText("Anita Rao")).toBeInTheDocument();
    const intent = screen.getByRole("region", { name: "Step 1: Intent" });
    expect(within(intent).getByText("Signed")).toBeInTheDocument();
    expect(within(intent).getByText("Daniel Foo")).toBeInTheDocument();
    expect(screen.getByText(/Daniel Foo signed the intent/)).toBeInTheDocument();
    expect(screen.getByText(/Mei Chen started the project with North/)).toBeInTheDocument();
    expect(screen.getByText("Choose who builds Architecture and Pipelines")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open dashboards" })).toHaveAttribute("href", "/centre/build/p/P4/dashboards");
  });

  test("Assign step: pick steps, a person, a note and a date; the call goes to the assign route", async () => {
    const sent: string[] = [];
    overviewWorld([], sent);
    await userEvent.click((await screen.findAllByRole("button", { name: "Assign step" }))[0]!);
    const dlg = await screen.findByRole("dialog");
    const send = within(dlg).getByRole("button", { name: "Assign" });
    expect(send).toBeDisabled(); // nobody chosen yet
    await userEvent.click(await within(dlg).findByRole("radio", { name: "Leo Park" }));
    await userEvent.click(within(dlg).getByRole("checkbox", { name: /Pipelines/ }));
    await userEvent.type(within(dlg).getByLabelText("Note to the builder"), "Use version 1 of the blend");
    await userEvent.type(within(dlg).getByLabelText("Due date"), "2026-10-16");
    await userEvent.click(within(dlg).getByRole("button", { name: "Assign to Leo Park" }));
    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0]).toMatch(/^POST \/api\/v1\/projects\/P4\/assign /);
    expect(JSON.parse(sent[0]!.split(" ").slice(2).join(" "))).toEqual({ steps: ["architecture", "pipelines"], to: "u-leo", note: "Use version 1 of the blend", due: "2026-10-16" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  test("Hand over opens the hand-over page (V6, design B4)", async () => {
    overviewWorld([], []);
    expect(await screen.findByRole("link", { name: "Hand over" })).toHaveAttribute("href", "/centre/build/p/P4/handover");
  });

  test("an assigned builder shows on the step and in the timeline; the next box waits for them", async () => {
    overviewWorld([{ step: "architecture", assignee: "u-leo", assignee_name: "Leo Park", note: "Check the blend", due: "2026-10-16", by_name: "Mei Chen", at: "2026-10-11T10:52:00Z" },
      { step: "pipelines", assignee: "u-leo", assignee_name: "Leo Park" }], []);
    expect(await screen.findByText("Assigned to Leo Park")).toBeInTheDocument();
    expect(screen.getByText("Assigned · starts after step 2")).toBeInTheDocument();
    expect(screen.getByText(/Mei Chen assigned Architecture to Leo Park, due 2026-10-16/)).toBeInTheDocument();
    expect(screen.getByText("Nothing for you until Leo Park sends the architecture")).toBeInTheDocument();
    expect(screen.queryByText("Choose who builds Architecture and Pipelines")).toBeNull();
  });

  test("pure: nothing is made up when records are missing", () => {
    const v = stepViews({ project: { ...PROJECT, stage: "talking", people: { raiser: null, sponsor: null, builder: null, head_of_data: null, ops: null }, artefacts: [] } as never, plan: null, runs: [], boards: [], assigns: [] });
    expect(v.map((s) => s.mark)).toEqual(["here", "todo", "todo", "todo"]);
    expect(headline(v)).toBe("STEP 1 OF 4 · BEING DEFINED WITH NORTH");
    expect(currentStep(v).id).toBe("intent");
    expect(events({ project: { ...PROJECT, artefacts: [], started_at: "" } as never, plan: null, runs: [], boards: [], assigns: [] })).toEqual([]);
  });
});

describe("the stepper", () => {
  const stub = () => vi.stubGlobal("fetch", vi.fn(async (url: string) => url === "/api/v1/projects/P4" ? json(200, PROJECT) : json(404, { error: "not_found", message: "x" })));

  test("a room inside it shows the step rail, links every step, and leaves out its own tile switcher", () => {
    stub();
    render(<MemoryRouter initialEntries={["/centre/build/p/P4/architecture"]}><Routes><Route path="/centre/build/p/:projectId/architecture" element={
      <InStep current="architecture"><RoomSwitcher pid="P4" facts={null} /><p>the room</p></InStep>} /></Routes></MemoryRouter>);
    const rail = screen.getByRole("list", { name: "Project steps" });
    expect(within(rail).getAllByRole("link").map((a) => a.getAttribute("href"))).toEqual(
      ["intent", "architecture", "pipelines", "dashboards"].map((s) => `/centre/build/p/P4/${s}`));
    expect(within(rail).getByRole("link", { name: /ARCHITECTURE/ })).toHaveAttribute("aria-current", "step");
    expect(screen.getByText("the room")).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Build rooms" })).toBeNull();
    expect(screen.getByRole("link", { name: "Project overview" })).toHaveAttribute("href", "/centre/build/p/P4/overview");
    expect(screen.getByRole("link", { name: /Project page: documents/ })).toHaveAttribute("href", "/centre/project/P4");
  });

  test("outside it the room keeps its own switcher (nothing dropped)", () => {
    stub();
    render(<MemoryRouter><RoomSwitcher pid="P4" facts={null} /></MemoryRouter>);
    expect(screen.getByRole("navigation", { name: "Build rooms" })).toBeInTheDocument();
  });

  test("step 1 for a project opens its intent conversation inside Build", async () => {
    stub();
    render(<MemoryRouter initialEntries={["/centre/build/p/P4/intent"]}><Routes>
      <Route path="/centre/build/p/:projectId/intent" element={<IntentByProject />} /><Route path="/centre/build/intent/:iid" element={<p>conversation IN-4</p>} /></Routes></MemoryRouter>);
    expect(await screen.findByText("conversation IN-4")).toBeInTheDocument();
  });

  test("a project with no intent says so in plain words", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(404, { error: "not_found", message: "x" })));
    render(<MemoryRouter initialEntries={["/centre/build/p/P9/intent"]}><Routes><Route path="/centre/build/p/:projectId/intent" element={<IntentByProject />} /></Routes></MemoryRouter>);
    expect(await screen.findByText("This project has no intent to show yet.")).toBeInTheDocument();
  });
});

describe("V6 B4: the hand-over page", () => {
  const signedProject = { ...PROJECT, artefacts: [{ kind: "intent", record_path: "x", version: 1, state: "signed", signed_by: "Daniel Foo", signed_at: "2026-10-11T11:05:00Z" }] };
  function handoverWorld(sent: string[]) {
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (url === "/api/auth/me") return json(200, { display_name: "Mei Chen", account_id: "u-mei", company_id: "evergreen", roles: ["analyst"] });
      if (init?.method && init.method !== "GET") { sent.push(`${init.method} ${url} ${String(init.body ?? "")}`); return json(200, { assignments: [] }); }
      if (url === "/api/v1/projects/P4") return json(200, signedProject);
      if (url === "/api/v1/intents/IN-4/sow") return json(200, { signature: { name: "Daniel Foo", role: "sponsor", at: "2026-10-11T11:05:00Z", note: "Good. Please show the SGD view as well." }, sources: [{ name: "Administrator file" }, { name: "Index levels" }], goal: null, kpis: [], process: null });
      if (url === "/api/v1/projects/P4/assign/candidates") return json(200, { people: [{ id: "u-leo", name: "Leo Park", role: "Data engineer", open_steps: 2 }] });
      if (url === "/api/v1/build/p/P4/plan") return json(200, { project_id: "P4", plan: null, state: null, intent_signed: true });
      if (url === "/api/v1/build/p/P4/runs") return json(200, { runs: [] });
      if (url === "/api/v1/build/p/P4/studio") return json(200, { can_make: true, dashboards: [] });
      if (url === "/api/v1/model/projects/P4/tables") return json(200, { bronze: [], silver: [], gold: [] });
      return json(404, { error: "not_found", message: "Not found." });
    }));
    return render(<MemoryRouter initialEntries={["/centre/build/p/P4/handover"]}><ThemeProvider><SessionProvider><Routes>
      <Route path="/centre/build/p/:projectId/handover" element={<HandoverPage />} /><Route path="/centre/build/p/:projectId/overview" element={<p>overview</p>} /></Routes></SessionProvider></ThemeProvider></MemoryRouter>);
  }

  test("one page: who signed and when, the sponsor's note, the steps, the people, the note and what they receive", async () => {
    handoverWorld([]);
    expect(await screen.findByRole("heading", { level: 1, name: "Hand the build to the data team" })).toBeInTheDocument();
    expect(screen.getByText("INTENT SIGNED · CHOOSE WHO BUILDS IT")).toBeInTheDocument();
    expect(screen.getByText(/Before this: Daniel Foo signed the intent on/)).toBeInTheDocument();
    expect(await screen.findByText(/Daniel's note: .Good\. Please show the SGD view as well\./)).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Architecture" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Pipelines" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Dashboards" })).not.toBeChecked();
    expect(screen.getByText("Span proposes the tables from the signed intent. Anita Rao approves.")).toBeInTheDocument();
    await userEvent.click(await screen.findByRole("radio", { name: "Leo Park" }));
    expect(screen.getByText("Leo receives")).toBeInTheDocument();
    expect(screen.getByText("The sources named in it: Administrator file, Index levels")).toBeInTheDocument();
    expect(screen.getByText("It lands at the top of Leo's Action page. You will see each step finish here.")).toBeInTheDocument();
  });

  test("Hand over sends the chosen steps with the note and date, marked as a hand-over, and goes back to the project", async () => {
    const sent: string[] = [];
    handoverWorld(sent);
    expect(await screen.findByRole("button", { name: "Hand over" })).toBeDisabled(); // nobody chosen yet
    await userEvent.click(await screen.findByRole("radio", { name: "Leo Park" }));
    await userEvent.type(screen.getByLabelText("Note to Leo"), "Use the administrator file.");
    await userEvent.type(screen.getByLabelText("Due"), "2026-10-16");
    await userEvent.click(screen.getByRole("button", { name: "Hand over to Leo Park" }));
    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0]).toMatch(/^POST \/api\/v1\/projects\/P4\/assign /);
    expect(JSON.parse(sent[0]!.split(" ").slice(2).join(" "))).toEqual({ steps: ["architecture", "pipelines"], to: "u-leo", note: "Use the administrator file.", due: "2026-10-16", handover: true });
    expect(await screen.findByText("overview")).toBeInTheDocument();
  });
});
