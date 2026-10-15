import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import App from "../App";
import { setSessionExpiredHandler } from "../api/client";
import ProjectPicker, { ordered } from "../v1/s1/ProjectPicker";
import { redirectFor } from "./redirects";
import { centresFor } from "./roles";

// The new shell: the top bar, the redirects, and the three room cards of the home in each state. fetch is stubbed per route.

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const group = (id: number) => ({ id, key: `g${id}`, title: `G${id}`, required: true, state: "read", reason: "", files: [] });
const READY = { groups: [group(1)], percent: 40, read: 1, sentence: "x", asks: [] };
const MOD = (id: string, centre: string) => ({ id, number: 1, name: id, description: "", agent: "x", centre });
const LISTS = {
  seats: { min: 3, max: 12 }, time_presets_minutes: [60], custom_length_minutes: { min: 30, max: 240 }, min_stage_minutes: 5,
  default_length_minutes: 60, default_split: { briefing: 10, individual: 25, together: 25 }, default_split_percent: { briefing: 15, individual: 45, together: 40 },
  briefing_video_options: [], charter_templates: [], default_template: "", north: {},
};

interface World {
  roles?: string[]; signedIn?: boolean; modules?: object[]; sessions?: object[]; baselines?: object[]; assessments?: object;
}
const calls: { method: string; url: string }[] = [];
function mock(w: World = {}) {
  calls.length = 0;
  document.cookie = "sh_csrf=tok";
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ method, url });
    const me = { display_name: "Ann Lee", company_id: "co", roles: w.roles ?? ["company_admin"] };
    if (url === "/api/auth/me") return w.signedIn === false ? json(401, { error: "session_expired", message: "x" }) : json(200, me);
    if (url === "/api/auth/login") return json(200, me);
    if (url === "/api/company") return json(200, { company_id: "co", name: "Lakeside Test Co", industry: "family_office", brand: { logo: "logo.png" } });
    if (url === "/api/modules") return json(200, w.modules ?? [MOD("m1_intent", "intent"), MOD("m2_baseline", "intent"), MOD("m3_connect", "intent"), MOD("m4", "consume")]);
    if (url === "/api/profile") return json(200, { reported_figures: {}, governance: { field_rules: {}, restricted_areas: {} } });
    if (url === "/api/profile/readiness") return json(200, READY);
    if (url === "/api/interview") return json(200, { people: [] });
    if (url === "/api/modules/m1_intent/sessions" && method === "GET") return json(200, w.sessions ?? []);
    if (url === "/api/modules/m1_intent/sessions" && method === "POST") return json(200, { id: "s-new" });
    if (url === "/api/modules/m1_intent/lists") return json(200, LISTS);
    if (method === "POST" && url.startsWith("/api/modules/m1_intent/sessions/s-new/")) return json(200, { join_path: "/join/abc" });
    if (url.endsWith("/m2_baseline/baselines")) return json(200, { charters: [], baselines: w.baselines ?? [] });
    if (url === "/api/modules/m3_connect/assessments" && method === "GET") return json(200, w.assessments ?? { assessments: [], signed_baseline: false, can_start: false });
    if (url === "/api/modules/m3_connect/assessments" && method === "POST") return json(200, { assessment: { id: "a-new" } });
    return json(404, { error: "x", message: "x" });
  }));
}
const at = (path: string) => render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);

afterEach(() => { vi.unstubAllGlobals(); sessionStorage.clear(); localStorage.clear(); setSessionExpiredHandler(null); });

// The top bar per role (V5, 11 Oct): Action, Build, Consume, Map. Intent is step 1 of Build.
async function barOf(roles: string[], path = "/centre/settings/memory"): Promise<string[]> {
  mock({ roles });
  at(path);
  await screen.findByRole("link", { name: "Action" });
  const nav = screen.getByRole("navigation", { name: "Centres" });
  return Array.from(nav.querySelectorAll("a")).map((a) => a.textContent ?? "");
}
const accountLinks = async (): Promise<string[]> => {
  await userEvent.setup().click(screen.getByRole("button", { name: "Account menu" }));
  return screen.queryAllByRole("link").map((a) => a.textContent ?? "");
};

describe("top bar", () => {
  test("a participant sees Action, Build, Consume and Map (PF2: Consume is for everyone to read)", async () => {
    expect(await barOf(["participant"])).toEqual(["Action", "Build", "Consume", "Map"]);
    const menu = await accountLinks();
    expect(menu).toContain("Settings"); // ROLE1: everyone has their own Settings (memory, Testing or Real use, Activity trail)
    expect(menu).not.toContain("People and access");
    expect(menu).toContain("What the agents remember about you");
    expect(menu).toContain("Library");  // UX3
  });

  test.each(["participant", "owner", "approver", "sponsor", "analyst", "company_admin"])("a %s may open Consume", (role) => {
    expect(centresFor([role]).has("consume")).toBe(true);
  });

  test.each(["owner", "approver", "sponsor"])("a %s (the CIO side) sees Action, Build, Consume and Map", async (role) => {
    expect(await barOf([role])).toEqual(["Action", "Build", "Consume", "Map"]);
    const menu = await accountLinks();
    expect(menu).toContain("Settings");
    expect(menu).toContain("Activity trail");
    for (const admin of ["People and access", "Sources and data model", "Templates and skills", "Agent runs and cost"]) expect(menu).not.toContain(admin);
  });

  test.each(["analyst", "company_admin"])("%s (head of data, admin) sees all four and Settings", async (role) => {
    expect(await barOf([role])).toEqual(["Action", "Build", "Consume", "Map"]);
    expect(screen.getByRole("link", { name: "Build" })).toHaveAttribute("href", "/centre/build");
    // CR1: the bar tooltips say what each centre is for.
    expect(screen.queryByRole("link", { name: "Intent" })).toBeNull(); // V5: Intent is step 1 of Build, not a centre
    expect(screen.getByRole("link", { name: "Build" })).toHaveAttribute("title", "Start and follow projects");
    expect(screen.getByRole("link", { name: "Action" })).toHaveAttribute("title", "Things to do");
    expect(screen.getByRole("link", { name: "Consume" })).toHaveAttribute("title", "Reports and insights");
    await userEvent.setup().click(screen.getByRole("button", { name: "Account menu" }));
    expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute("href", "/centre/settings");
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  });

  test("a company admin sees the company name", async () => {
    await barOf(["company_admin"]);
    expect(await screen.findByText("Lakeside Test Co")).toBeInTheDocument();
  });

  test("the super admin lands on Control and sees no company centre", async () => {
    mock({ roles: ["super_admin"] });
    at("/");
    expect(await screen.findByRole("link", { name: "CONTROL" })).toHaveAttribute("aria-current", "page");
    const nav = screen.getByRole("navigation", { name: "Centres" });
    expect(Array.from(nav.querySelectorAll("a")).map((a) => a.textContent)).toEqual(["CONTROL"]);
  });
});

describe("role gate", () => {
  test("a participant sent to Build lands on Action with a plain line", async () => {
    mock({ roles: ["participant"] });
    at("/centre/build/pipelines");
    expect(await screen.findByText(/not open to you/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Action" })).toHaveAttribute("aria-current", "page");
  });

  test("a sponsor may not open the data model in Settings", async () => {
    mock({ roles: ["sponsor"] });
    at("/centre/settings/model");
    expect(await screen.findByText(/not open to you/)).toBeInTheDocument();
  });
});

describe("redirects", () => {
  test("Pulse is not a destination: home, pulse and today all go to Action", () => {
    for (const p of ["/centre/home", "/centre/pulse", "/centre/today"]) expect(redirectFor(p)).toBe("/centre/action");
  });

  test("after sign-in the person lands on Action", async () => {
    mock({ signedIn: false });
    at("/login");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Email"), "a@b.co");
    await user.type(screen.getByLabelText("Password"), "pw");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("link", { name: "Action" })).toHaveAttribute("aria-current", "page");
  });

  test.each([
    ["/centre/today", "/centre/action"],
    ["/centre/pulse", "/centre/action"],
    ["/centre/desk", "/centre/action/cases"],
    ["/centre/desk/c-7", "/centre/action/cases/c-7"],
    ["/centre/evidence", "/centre/action/evidence"],
    ["/centre/evidence/d-1", "/centre/action/evidence/d-1"],
    ["/centre/admin/agents", "/centre/settings/templates"],
    ["/centre/admin/model", "/centre/settings/model"],
    ["/centre/admin/rules", "/centre/settings/rules"],
    ["/centre/admin/anything", "/centre/settings"],
    ["/centre/register", "/centre/settings/register"],
    ["/centre/memory", "/centre/settings/memory"],
  ])("%s goes to %s", (from, to) => { expect(redirectFor(from)).toBe(to); });

  test.each([
    ["/centre/intent", "/centre/build/new"],
    ["/centre/intent/int-9", "/centre/build/intent/int-9"],
    ["/centre/intent/", "/centre/build/new"],
  ])("V5: %s goes into Build at %s", (from, to) => { expect(redirectFor(from)).toBe(to); });

  test("V5: the other Intent pages keep their paths", () => {
    for (const p of ["/centre/intent/new", "/centre/intent/graph", "/centre/intent/past", "/centre/intent/bring", "/centre/intent/int-9/sow", "/centre/intent/int-9/extraction"]) expect(redirectFor(p)).toBeNull();
  });

  test("V5: an old Intent link opens Build's start page in the app, with its query kept", async () => {
    mock({ roles: ["analyst"] });
    at("/centre/intent?new=1");
    expect(await screen.findByRole("link", { name: "Build" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("list", { name: "Project steps" })).toBeInTheDocument());
  });

  test("the four centres and their project pages are not redirected", () => {
    for (const p of ["/centre/action", "/centre/build", "/centre/build/p/EV-1", "/centre/consume/p/EV-1", "/centre/settings", "/centre/build/ops/x", "/centre/tickets", "/centre/data/intake", "/centre/build/ops"]) expect(redirectFor(p)).toBeNull();
  });

  test("an old link opens its new home in the app", async () => {
    mock({ roles: ["company_admin"] });
    at("/centre/today");
    expect(await screen.findByRole("link", { name: "Action" })).toHaveAttribute("aria-current", "page");
  });
});

describe("project picker", () => {
  const P = (id: string, title: string, at: string, stage = "signed") => ({ id, title, started_at: at, stage, started_by: "ann", people: { sponsor: null } });
  const list = [P("EV-0001", "Quarterly review", "2026-01-01"), P("EV-0002", "Monthly investment report", "2026-02-01"), P("EV-0003", "Cash forecast", "2026-03-01", "live")];

  test("newest first, recently opened ahead of that, search by id or title", () => {
    expect(ordered(list, [], "").map((p) => p.id)).toEqual(["EV-0003", "EV-0002", "EV-0001"]);
    expect(ordered(list, ["EV-0001"], "").map((p) => p.id)[0]).toBe("EV-0001");
    expect(ordered(list, [], "0002").map((p) => p.id)).toEqual(["EV-0002"]);
    expect(ordered(list, [], "cash").map((p) => p.id)).toEqual(["EV-0003"]);
  });

  test("shows stage words and owner, and links to the project page of the centre", async () => {
    render(<MemoryRouter><ProjectPicker centre="build" projects={list} /></MemoryRouter>);
    expect(screen.getByText(/Live · Owner: ann/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /EV-0002/ })).toHaveAttribute("href", "/centre/build/p/EV-0002");
    await userEvent.setup().type(screen.getByRole("searchbox"), "report");
    expect(screen.queryByRole("link", { name: /EV-0003/ })).toBeNull();
    expect(screen.getByRole("link", { name: /EV-0002/ })).toBeInTheDocument();
  });
});

const live = (state: string, id = "s1") => ({ id, state, label: "L", seats: 6, outcome_id: "o", updated_at: "" });
const signed = { assessments: [], signed_baseline: true, can_start: true };

// the Intent home's own tests live in src/pages/centre.test.tsx (Q4)

test("W2: at 390px the top bar keeps the company badge and avatar whole and the brand on one line", async () => {
  const { barStyle } = await import("./barStyle");
  const phone = barStyle.slice(barStyle.indexOf("@media (max-width: 480px)"));
  expect(phone).toMatch(/\.cs-brand strong \{[^}]*clip: rect\(0 0 0 0\)/); // hidden to the eye, still read out: never display:none
  expect(barStyle).toMatch(/\.cs-chip, \.cs-avatar, \.cs-burger, \.cs-div \{ flex: none; \}/);
  expect(barStyle).toMatch(/\.cs-brand strong \{ white-space: nowrap; \}/);
});
