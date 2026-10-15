import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { setSessionExpiredHandler } from "../api/client";
import { ThemeProvider } from "../theme";
import { SessionProvider } from "../useSession";
import CentrePage, { DOORS_GRID } from "./CentrePage";

// Intent Centre home (artboard 1). fetch is stubbed per route with SHAPES-shaped, synthetic data.

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const cell = (value: unknown) => ({ value });
const group = (id: number, title: string, state: string, files: string[] = []) => ({ id, key: `g${id}`, title, required: true, state, reason: `${title} is ${state}`, files });
const PROFILE = {
  reported_figures: { aum: { measure: cell("AUM"), owner: cell("Mei Tan") }, nav: { measure: cell("NAV") } },
  governance: { field_rules: { aum: { field: cell("AUM"), personal: cell("no"), may_see: cell(["Mei Tan"]) } }, restricted_areas: {} },
};
const READY = { groups: [group(1, "Reporting", "read", ["a.xlsx", "b.csv"]), group(2, "People", "missing"), group(3, "Systems", "partly", ["c.json"])], percent: 40, asks: [] };
const LISTS = {
  seats: { min: 3, max: 12 }, time_presets_minutes: [60], custom_length_minutes: { min: 30, max: 240 }, min_stage_minutes: 5,
  default_length_minutes: 60, default_split: { briefing: 10, individual: 25, together: 25 }, default_split_percent: { briefing: 15, individual: 45, together: 40 },
  briefing_video_options: [], charter_templates: [], default_template: "", north: {},
};
const WALLS = [
  { id: "w1", topic: "Treasury: capital calls", purpose: "p", state: "private_rooms", cards_count: 3, people_count: 2 },
  { id: "w2", topic: "Investment committee: performance", purpose: "p", state: "board", cards_count: 1, people_count: 1 },
];

interface World { roles?: string[]; walls?: object[]; sessions?: object[] }
function mock(w: World) {
  const posts: { url: string; body: Record<string, unknown> }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      posts.push({ url, body: init.body ? JSON.parse(String(init.body)) : {} });
      if (url.endsWith("/m1_intent/sessions")) return json(201, { id: "s9" });
      if (url.endsWith("/sessions/s9/start")) return json(200, { join_path: "/join/x" });
    }
    if (url === "/api/auth/me") return json(200, { display_name: "Janet Shaw", company_id: "co-a", roles: w.roles ?? ["company_admin"] });
    if (url === "/api/company") return json(200, { company_id: "co-a", name: "Lakeside Test Co", industry: "family_office" });
    if (url === "/api/profile") return json(200, PROFILE);
    if (url === "/api/profile/readiness") return json(200, READY);
    if (url === "/api/interview") return json(200, { people: [{ status: "done" }, { status: "in_progress" }, { status: "done" }], organiser: true });
    if (url.endsWith("/m1_intent/lists")) return json(200, LISTS);
    if (url.endsWith("/m1_intent/walls")) return json(200, { walls: w.walls ?? [] });
    if (url.endsWith("/m1_intent/sessions")) return json(200, w.sessions ?? [{ state: "closed", seats: 4 }]);
    if (url.endsWith("/m2_baseline/baselines")) return json(200, { charters: [], baselines: [{ id: "b1", state: "draft" }] });
    if (url.endsWith("/sessions/w3/charter")) return json(200, { charter: { status: "signed", signing: { signers: [{ name: "Daniel Kerr" }] } } });
    if (url.endsWith("/m3_connect/assessments")) return json(200, { assessments: [], signed_baseline: false, can_start: false });
    return json(404, {});
  }));
  return posts;
}
const open = () => render(
  <MemoryRouter initialEntries={["/centre/intent"]}>
    <ThemeProvider><SessionProvider>
      <Routes>
        <Route path="/centre/intent" element={<CentrePage />} />
        <Route path="/centre/intent/wall/:id" element={<p>Wall screen</p>} />
      </Routes>
    </SessionProvider></ThemeProvider>
  </MemoryRouter>,
);

afterEach(() => { vi.unstubAllGlobals(); setSessionExpiredHandler(null); });

describe("Intent Centre home", () => {
  test("doors lit in order with counts, bars, waiting list and counters", async () => {
    mock({ walls: WALLS.slice(0, 1) });
    open();
    expect(await screen.findByText("ROOM 1 · OPEN")).toBeInTheDocument();
    expect(screen.getByText("ROOM 2 · OPEN")).toBeInTheDocument();
    expect(screen.getByText("ROOM 3 · AFTER ROOM 2")).toBeInTheDocument();
    expect(Array.from(document.querySelectorAll(".ds-room__counts")).map((e) => e.textContent)).toContain("3 cards on the wall · 2 people have contributed");
    expect(Array.from(document.querySelectorAll(".ds-room__counts")).map((e) => e.textContent)).toContain("1 baseline · 0 signed");
    expect(screen.getByText("No signed baseline yet")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Named owner" })).toHaveAttribute("aria-valuenow", "50");
    expect(screen.getByText("0 of 2")).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "Nira, your guide · what is waiting" })).getByText("People")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ask for these, one by one" })).toHaveAttribute("href", "/centre/intent/bring");
    expect(screen.queryByRole("button", { name: /reminder/i })).toBeNull();
    expect(screen.getByText("1 of 3 inputs complete")).toBeInTheDocument();
    expect(screen.getByText("2 / 3")).toBeInTheDocument();
    expect(screen.getByText("40%")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "See the outcomes" })).toHaveAttribute("href", "/centre/intent/outcomes");
    expect(screen.getByRole("link", { name: "How my organisation connects" })).toHaveAttribute("href", "/centre/intent/graph");
  });

  test("start panel posts the topic, the purpose and the days, then opens the wall", async () => {
    const posts = mock({});
    open();
    fireEvent.click(await screen.findByRole("link", { name: "Start the wall" }));
    const panel = within(await screen.findByRole("region", { name: "How long should the wall stay open?" }));
    fireEvent.change(panel.getByLabelText("Topic or department"), { target: { value: "Treasury: capital calls" } });
    fireEvent.change(panel.getByLabelText("What are we here for?"), { target: { value: "Late notices" } });
    fireEvent.change(panel.getByDisplayValue("5"), { target: { value: "8" } });
    fireEvent.click(panel.getByRole("button", { name: "Start the wall" }));
    expect(await screen.findByText("Wall screen")).toBeInTheDocument();
    const draft = posts.find((p) => p.url.endsWith("/m1_intent/sessions"))!;
    expect(draft.body).toMatchObject({ topic: "Treasury: capital calls", purpose: "Late notices", wall_window_days: 8, drafted: true });
    expect(posts.some((p) => p.url.endsWith("/sessions/s9/start"))).toBe(true);
  });

  test("walls list: each running wall by topic with its cards and an Open; a second wall needs a topic", async () => {
    mock({ walls: WALLS });
    open();
    const list = within(await screen.findByRole("list", { name: "Walls running" }));
    expect(list.getByText("Treasury: capital calls · 3 cards")).toBeInTheDocument();
    expect(list.getByText("Investment committee: performance · 1 card")).toBeInTheDocument();
    expect(list.getByRole("link", { name: "Open Treasury: capital calls" })).toHaveAttribute("href", "/centre/intent/wall/w1");
    expect(screen.getByText(/2 walls, 4 cards/)).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("link", { name: "Start another wall" }));
    fireEvent.click(within(await screen.findByRole("region", { name: "How long should the wall stay open?" })).getByRole("button", { name: "Start the wall" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("needs a topic or department");
  });

  test("room 2 has a door to the baseline; a closed wall with a signed charter links to it with the signer", async () => {
    mock({ walls: [...WALLS, { id: "w3", topic: "Treasury: capital calls", purpose: "p", state: "closed", cards_count: 30, people_count: 8 }] });
    open();
    expect(await screen.findByRole("link", { name: "Open the baseline" })).toHaveAttribute("href", "/centre/intent/baseline/b1");
    expect(await screen.findByText("Treasury: capital calls · charter signed by Daniel Kerr")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open the charter Treasury: capital calls" })).toHaveAttribute("href", "/centre/intent/charter/w3");
  });

  test("sponsor sees the same page read-only: no start buttons, no Bring link", async () => {
    mock({ roles: ["sponsor"], walls: WALLS });
    open();
    expect(await screen.findByText("ROOM 1 · OPEN")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Walls running" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^Start/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /^Start/ })).toBeNull();
    expect(screen.queryByRole("link", { name: "Bring what you have" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Ask for these, one by one" })).toBeNull();
  });

  test("phone: the doors sit in one grid that stacks below two door widths, in room order", async () => {
    mock({});
    open();
    const doors = await screen.findByRole("list", { name: "Rooms" });
    expect(doors.style.gridTemplateColumns).toBe(DOORS_GRID);
    expect(within(doors).getAllByRole("listitem").map((li) => li.textContent?.slice(0, 6))).toEqual(["ROOM 1", "ROOM 2", "ROOM 3"]);
  });
});
