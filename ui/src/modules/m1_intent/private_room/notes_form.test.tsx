import { cleanup, render, screen, configure } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import App from "../../../App";
import { setSessionExpiredHandler } from "../../../api/client";
import { m1Flow, m1Notes as n } from "../copy";
import type { FormField, Room, RoomNote } from "./roomApi";

// These tests render the whole App; on a loaded machine the 1s default for findBy*/waitFor is too short.
configure({ asyncUtilTimeout: 5000 });

// M1-P05 screens: the note form (fields from the contract, belief by the person, guess tag), By name / Anonymous per
// note, Submit, the person's own list. fetch is stubbed; nothing leaves the page.

const SID = "a".repeat(32);
const ROOM = `/api/modules/m1_intent/sessions/${SID}/room`;
const field = (id: string, label: string, over: Partial<FormField> = {}): FormField => ({
  id, label, kind: "text", ask: "", required: false, person_only: false, guess: false, ...over,
});
const FORM = [
  field("problem", "The problem", { required: true }), field("purpose", "The business purpose"),
  field("belief", "What you believe today", { kind: "number", person_only: true }),
  field("data_guess", "Where the data might be", { guess: true }), field("labels", "Labels", { kind: "labels" }),
];
const note = (over: Partial<RoomNote> = {}): RoomNote => ({
  id: "n1", text: "Renewals slipped in April", state: "draft", source: { kind: "typed" }, priority: null, practice: null,
  practice_added: [], created_at: "x", updated_at: "x", fields: {}, labels_suggested: [], anonymous: false,
  missing: ["purpose", "belief"], ...over,
});
const room = (notes: RoomNote[], over: Partial<Room> = {}): Room => ({
  open: true, message: null, title: "t", turns: [], notes, form: FORM, north: { practice_on: false, library_on: false, available: true }, ...over,
});
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const calls: { method: string; url: string; body: unknown }[] = [];

function mock(first: Room, after?: Room) {
  calls.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    if (url === "/api/auth/me") return json(200, { display_name: "Ann", company_id: "co-a", roles: ["company_admin"] });
    if (url === "/api/company") return json(200, { company_id: "co-a", name: "Harbor Test Co", industry: "none" });
    if (url === "/api/modules") return json(200, [{ id: "m1_intent", number: 1, name: "Intent", description: "d", agent: "North" }]);
    if (url === ROOM) return json(200, first);
    if (url === `${ROOM}/library`) return json(200, { on: false, available: false, label: "l", problems: [], message: "x" });
    if (method === "POST" && url.startsWith(ROOM)) return json(200, after ?? first);
    return json(404, {});
  }));
}
const at = (path: string) => render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
const posts = () => calls.filter((c) => c.method === "POST" && !c.url.endsWith("/nira")); // Nira's welcome is not a note call

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  sessionStorage.clear();
  setSessionExpiredHandler(null);
});

describe("the note form", () => {
  test("shows the contract's fields, the belief number as the person's own and the data field as a guess", async () => {
    mock(room([note()]));
    at(`/modules/m1_intent/sessions/${SID}/room`);
    expect(await screen.findByLabelText(/What you believe today/)).toBeInTheDocument();
    expect(screen.getByText(n.beliefHelp)).toBeInTheDocument();
    expect(screen.getByText(n.guessTag)).toBeInTheDocument();
    expect(screen.getByLabelText(/The business purpose/)).toBeInTheDocument();
    expect(screen.getByText(new RegExp(`${n.stillToFill} The business purpose, What you believe today`))).toBeInTheDocument();
  });

  test("By name is the default; choosing Anonymous saves the choice, in plain words", async () => {
    const user = userEvent.setup();
    mock(room([note()]), room([note({ anonymous: true })]));
    at(`/modules/m1_intent/sessions/${SID}/room`);
    expect(await screen.findByRole("radio", { name: new RegExp(`^${n.byName}`) })).toBeChecked();
    expect(screen.getByText(n.anonymousHelp)).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: new RegExp(`^${n.anonymous}`) }));
    expect(posts()[0]).toMatchObject({ url: `${ROOM}/notes/n1`, body: { anonymous: true } });
    expect(await screen.findByRole("radio", { name: new RegExp(`^${n.anonymous}`) })).toBeChecked();
    expect(screen.getAllByText(n.anonymousPill).length).toBeGreaterThan(0); // the author's own list says it
  });

  test("the By name / Anonymous choice shows only when each person chooses; otherwise the organiser's rule is said", async () => {
    mock(room([note()], { names: "named" }));
    at(`/modules/m1_intent/sessions/${SID}/room`);
    expect(await screen.findByText(n.namesNamed)).toBeInTheDocument();
    expect(screen.queryByRole("radio", { name: new RegExp(`^${n.anonymous}`) })).not.toBeInTheDocument();
    vi.unstubAllGlobals();
    cleanup();
    mock(room([note({ anonymous: true })], { names: "anonymous" }));
    at(`/modules/m1_intent/sessions/${SID}/room`);
    expect(await screen.findByText(n.namesAnonymous)).toBeInTheDocument();
    expect(screen.queryByRole("radio", { name: new RegExp(`^${n.byName}`) })).not.toBeInTheDocument();
  });

  test("North may fill in what is empty; a number typed by the person is sent as a number", async () => {
    const user = userEvent.setup();
    mock(room([note()]), room([note({ fields: { purpose: "Keep customers" }, missing: ["belief"] })]));
    at(`/modules/m1_intent/sessions/${SID}/room`);
    await user.click(await screen.findByRole("button", { name: n.askNorth }));
    expect(posts()[0]?.url).toBe(`${ROOM}/notes/n1/prefill`);
    expect(await screen.findByDisplayValue("Keep customers")).toBeInTheDocument();
    await user.type(screen.getByLabelText(/What you believe today/), "35");
    await user.click(screen.getByRole("button", { name: n.save }));
    expect(posts().at(-1)!.body).toMatchObject({ fields: { belief: 35, purpose: "Keep customers" } });
  });

  test("Submit saves the details and submits, and a submitted note can no longer be changed", async () => {
    const user = userEvent.setup();
    mock(room([note()]), room([note({ state: "submitted" })]));
    at(`/modules/m1_intent/sessions/${SID}/room`);
    await user.click(await screen.findByRole("button", { name: n.submit }));
    expect(posts().map((c) => c.url)).toEqual([`${ROOM}/notes/n1`, `${ROOM}/notes/n1/submit`]);
    expect(await screen.findByText(n.submittedHelp)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: n.submit })).not.toBeInTheDocument();
    expect(screen.getByRole("radio", { name: new RegExp(`^${n.byName}`) })).toBeDisabled();
  });

  test("when the rooms are closed nothing can be submitted", async () => {
    mock(room([note()], { open: false, message: "closed" }));
    at(`/modules/m1_intent/sessions/${SID}/room`);
    await screen.findByText(/Renewals slipped in April/);
    expect(screen.queryByRole("button", { name: n.submit })).not.toBeInTheDocument();
  });
});

describe("walking the stages without typing an address", () => {
  test("the briefing of a session that has not started says so and offers no 'I'm clear'", async () => {
    calls.length = 0;
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/auth/me") return json(200, { display_name: "Ann", company_id: "co-a", roles: ["company_admin"] });
      if (url === "/api/company") return json(200, { company_id: "co-a", name: "Harbor Test Co", industry: "none" });
      if (url === "/api/modules") return json(200, [{ id: "m1_intent", number: 1, name: "Intent", description: "d", agent: "North" }]);
      if (url.endsWith("/briefing")) return json(200, { stage: "lobby", company_name: "Harbor", title: "Our session", rules: [], video: { mode: "placeholder" },
        read_aloud: { available: false }, me: { role: "organiser", status: "waiting" }, can_send: false, next: "briefing" });
      return json(200, { stage: "lobby", timed: false, now: "x" });
    }));
    at(`/modules/m1_intent/sessions/${SID}/briefing`);
    expect(await screen.findByText(m1Flow.briefingNotStarted)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /clear/i })).not.toBeInTheDocument();
  });

  test("after the send, the briefing shows the new stage and a link to the room", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/auth/me") return json(200, { display_name: "Ann", company_id: "co-a", roles: ["company_admin"] });
      if (url === "/api/company") return json(200, { company_id: "co-a", name: "Harbor Test Co", industry: "none" });
      if (url === "/api/modules") return json(200, [{ id: "m1_intent", number: 1, name: "Intent", description: "d", agent: "North" }]);
      if (url.endsWith("/briefing")) return json(200, { stage: "private_rooms", company_name: "Harbor", title: "Our session", rules: [], video: { mode: "placeholder" },
        read_aloud: { available: false }, me: { role: "organiser", status: "waiting" }, can_send: false, next: "room", confirmed: 1, seats: 2 });
      return json(200, { stage: "private_rooms", timed: false, now: "x" });
    }));
    at(`/modules/m1_intent/sessions/${SID}/briefing`);
    expect(await screen.findByText(m1Flow.nowRoomsOpen)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: m1Flow.toRoom })).toHaveAttribute("href", `/modules/m1_intent/sessions/${SID}/room`);
  });
});
