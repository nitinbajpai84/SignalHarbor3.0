import { render, screen, waitFor, within, configure } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import App from "../../App";
import { setSessionExpiredHandler } from "../../api/client";
import type { Lists, Preparation, SessionView } from "./api";
import { m1Lean } from "./copy";
import type { Room, RoomNote } from "./private_room/roomApi";

// These tests render the whole App; on a loaded machine the 1s default for findBy*/waitFor is too short.
configure({ asyncUtilTimeout: 5000 });

// LI-M1: Prepare drafted from the profile (one button), North's drafts in the private room (Keep, Change, Anonymous), the vote's ticks.
// fetch is stubbed; nothing leaves the page. Synthetic family-office wording.

const BASE = "/api/modules/m1_intent";
const SID = "a".repeat(32);
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const calls: { method: string; url: string; body: unknown }[] = [];

const LISTS: Lists = {
  seats: { min: 1, max: 10 },
  time_presets_minutes: [5, 10, 20, 30],
  custom_length_minutes: { min: 5, max: 120 },
  min_stage_minutes: 1,
  default_length_minutes: 20,
  default_split: { briefing: 4, individual: 8, together: 8 },
  default_split_percent: { briefing: 20, individual: 40, together: 40 },
  briefing_video_options: ["standard", "none"],
  charter_templates: [{ id: "standard", name: "Standard charter", description: "Everything on each line." }],
  default_template: "standard",
  north: { problem_library_available: false, industry_practice_available: false, problem_count: 0, message: null },
  profile_draft: {
    available: true,
    fields: {
      purpose: { value: "Plan cash ahead of capital calls", source: "Investment policy statement, page 2" },
      outcome: { value: "Calls are planned three months out", source: "Interview with Sue Sponsor" },
      seats: { value: 3, source: "People list" },
      approver_name: { value: "Aaron Lyle", source: "Interview with Sue Sponsor" },
      names: { value: "choice", source: "Standing default: each person chooses" },
      length_minutes: { value: 20, source: "Standing default length" },
    },
    people: [{ name: "Sue Sponsor", role: "Chair", source: "People list" }],
  },
};
const PREP: Preparation = {
  purpose: "Plan cash ahead of capital calls", outcome: "Calls are planned three months out", charter_template: "standard", seats: 3,
  length_minutes: 20, split: { briefing: 4, individual: 8, together: 8 }, north_industry_practice: false, north_problem_library: false,
  briefing_video: "standard", approver_name: "Aaron Lyle", approver_account_id: null,
};
const made: SessionView = {
  id: SID, state: "draft", paused_from: null, is_solo: false, editable: true, preparation: PREP, outcome_id: "b".repeat(32),
  created_at: "2026-10-05T10:00:00+00:00", updated_at: "2026-10-05T10:00:00+00:00",
};

const note = (over: Partial<RoomNote> = {}): RoomNote => ({
  id: "n1", text: "Capital calls reach us too late", state: "draft", source: { kind: "interview", q: "Q2", from: "Interview with Mei Tan" },
  priority: null, practice: null, practice_added: [], created_at: "x", updated_at: "x", fields: {}, labels_suggested: [], anonymous: false,
  missing: [], kind: "pain_point", confirmed: false, ...over,
});
const room = (over: Partial<Room> = {}): Room => ({
  open: true, message: null, title: "", turns: [{ id: "t1", role: "north", text: "I have drafted 1 note from your interview.", at: "x", answered: true }],
  notes: [note()], form: [], names: "choice", interview: { drafted: true, gaps: [{ kind: "intent", ask: "What do you intend to do now?" }] },
  north: { practice_on: false, library_on: false, available: true }, ...over,
});

function mock(r: Room = room()) {
  calls.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    if (url === "/api/auth/me") return json(200, { display_name: "Ann", company_id: "co-a", roles: ["company_admin"] });
    if (url === "/api/company") return json(200, { company_id: "co-a", name: "Harbor Test Co", industry: "none" });
    if (url === "/api/modules") return json(200, [{ id: "m1_intent", number: 1, name: "Intent", description: "d", agent: "North" }]);
    if (url === `${BASE}/lists`) return json(200, LISTS);
    if (url === `${BASE}/templates`) return json(200, []);
    if (url === `${BASE}/sessions` && method === "POST") return json(201, made);
    if (url === `${BASE}/sessions/${SID}/start`) return json(201, { join_path: "/join/abc", expires_at: "x" });
    if (url === `${BASE}/sessions/${SID}`) return json(200, made);
    if (url === `${BASE}/sessions/${SID}/room` && method === "GET") return json(200, r);
    if (url === `${BASE}/sessions/${SID}/room/library`) return json(200, { on: false, available: false, label: "", problems: [], message: null });
    if (url.endsWith("/timer")) return json(200, { timed: false, stage: "private_rooms" });
    if (url.startsWith(`${BASE}/sessions/${SID}/room/`) && method === "POST") return json(200, room({ notes: [note({ confirmed: true })] }));
    return json(404, {});
  }));
}
const open = (path: string) => render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  sessionStorage.clear();
  setSessionExpiredHandler(null);
});

describe("Prepare drafted from the profile", () => {
  test("every line shows its source and one button makes the session and starts the room", async () => {
    mock();
    open("/modules/m1_intent/prepare");
    expect(await screen.findByRole("heading", { name: m1Lean.drafted.title })).toBeInTheDocument();
    expect(screen.getByText("Plan cash ahead of capital calls")).toBeInTheDocument();
    expect(screen.getByText(m1Lean.drafted.from("Investment policy statement, page 2"))).toBeInTheDocument();
    expect(screen.getAllByText(m1Lean.drafted.from("Interview with Sue Sponsor"))).toHaveLength(2); // the outcome and the approver
    await userEvent.click(screen.getByRole("button", { name: m1Lean.drafted.looksRight }));
    await waitFor(() => expect(calls.some((c) => c.url === `${BASE}/sessions/${SID}/start`)).toBe(true));
    const created = calls.find((c) => c.method === "POST" && c.url === `${BASE}/sessions`);
    expect(created?.body).toMatchObject({ purpose: "Plan cash ahead of capital calls", approver_name: "Aaron Lyle", seats: 3, drafted: true });
  });

  test("Change something opens today's wizard with the drafted values in it", async () => {
    mock();
    open("/modules/m1_intent/prepare");
    await userEvent.click(await screen.findByRole("button", { name: m1Lean.drafted.change }));
    expect(await screen.findByDisplayValue("Plan cash ahead of capital calls")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: m1Lean.drafted.looksRight })).not.toBeInTheDocument();
  });

  test("a company with nothing to draft from sees today's wizard", async () => {
    mock();
    LISTS.profile_draft = { available: false, fields: {}, people: [] };
    try {
      open("/modules/m1_intent/prepare");
      expect(await screen.findByLabelText(/What is this session for/i)).toBeInTheDocument();
    } finally {
      LISTS.profile_draft = undefined;
    }
  });
});

describe("the private room with North's drafts", () => {
  test("a draft from the interview names its source and Keep confirms it", async () => {
    mock();
    open(`/modules/m1_intent/sessions/${SID}/room`);
    const item = (await screen.findAllByLabelText("Capital calls reach us too late")).find((e) => e.tagName === "LI") as HTMLElement;
    expect(within(item).getByText(m1Lean.room.draftFrom("Interview with Mei Tan"))).toBeInTheDocument();
    expect(within(item).getByRole("button", { name: m1Lean.room.anonymous })).toBeInTheDocument(); // each person chooses, so Anonymous is offered
    expect(within(item).getByRole("button", { name: m1Lean.room.change })).toBeInTheDocument();
    await userEvent.click(within(item).getByRole("button", { name: m1Lean.room.keep }));
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/room/notes/n1") && JSON.stringify(c.body) === '{"keep":true}')).toBe(true));
    await waitFor(() => expect(screen.queryByRole("button", { name: m1Lean.room.keep })).not.toBeInTheDocument()); // kept: nothing left to decide
  });

  test("North asks only about what is still open and offers to write note cards", async () => {
    mock(room({ turns: [{ id: "t1", role: "person", text: "Calls are paid late", at: "x" }] }));
    open(`/modules/m1_intent/sessions/${SID}/room`);
    expect(await screen.findByText(/What do you intend to do now\?/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: m1Lean.room.writeCards }));
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/room/notes") && JSON.stringify(c.body) === '{"from_conversation":true}')).toBe(true));
  });
});
