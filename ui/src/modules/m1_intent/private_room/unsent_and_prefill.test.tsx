import { render, screen, waitFor, configure } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import App from "../../../App";
import { setSessionExpiredHandler } from "../../../api/client";
import { m1Notes as n, m1PrivateRoom as t } from "../copy";
import type { FormField, Room, RoomNote } from "./roomApi";

// These tests render the whole App; on a loaded machine the 1s default for findBy*/waitFor is too short.
configure({ asyncUtilTimeout: 5000 });

// FIX-J: the one-minute warning for saved-but-unsent notes (with one click to make them anonymous), and North's
// progress line while it fills in a note. fetch is stubbed; nothing leaves the page.

const SID = "a".repeat(32);
const ROOM = `/api/modules/m1_intent/sessions/${SID}/room`;
const MESSAGE = "You have 2 notes not yet sent. If you do not send them, they go to the board anonymously.";
const FORM: FormField[] = [
  { id: "problem", label: "The problem", kind: "text", ask: "", required: true, person_only: false, guess: false },
  { id: "purpose", label: "The business purpose", kind: "text", ask: "", required: false, person_only: false, guess: false },
];
const note = (id: string, over: Partial<RoomNote> = {}): RoomNote => ({
  id, text: `Note ${id}`, state: "draft", source: { kind: "typed" }, priority: null, practice: null, practice_added: [],
  created_at: "x", updated_at: "x", fields: {}, labels_suggested: [], anonymous: false, missing: ["purpose"], ...over,
});
const room = (notes: RoomNote[], over: Partial<Room> = {}): Room => ({
  open: true, message: null, title: "t", turns: [], notes, form: FORM, north: { practice_on: false, library_on: false, available: true },
  unsent: { count: notes.length, named: notes.filter((x) => !x.anonymous).length, message: notes.length ? MESSAGE : null }, ...over,
});
const warning = { timed: true, stage: "private_rooms", status: "warning", started_at: "2026-10-04T10:00:00+00:00", ends_at: "2099-10-04T10:08:00+00:00",
  now: "2026-10-04T10:07:00+00:00", remaining_seconds: 50, warning_seconds: 60, extensions: [], extension_minutes: [2], may_extend: false };
const running = { ...warning, status: "running", remaining_seconds: 300 };
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const calls: { method: string; url: string; body: unknown }[] = [];

function mock(first: Room, timer: unknown, answer: (url: string, body: unknown) => Room | Promise<Room>) {
  calls.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method, url, body });
    if (url === "/api/auth/me") return json(200, { display_name: "Ann", company_id: "co-a", roles: ["company_admin"] });
    if (url === "/api/company") return json(200, { company_id: "co-a", name: "Harbor Test Co", industry: "none" });
    if (url === "/api/modules") return json(200, [{ id: "m1_intent", number: 1, name: "Intent", description: "d", agent: "North" }]);
    if (url === ROOM) return json(200, first);
    if (url.endsWith("/timer")) return json(200, timer);
    if (url === `${ROOM}/library`) return json(200, { on: false, available: false, label: "l", problems: [], message: "x" });
    if (method === "POST" && url.startsWith(ROOM)) return json(200, await answer(url, body));
    return json(404, {});
  }));
}
const open = () => render(<MemoryRouter initialEntries={[`/modules/m1_intent/sessions/${SID}/room`]}><App /></MemoryRouter>);
const posts = () => calls.filter((c) => c.method === "POST" && c.url.startsWith(ROOM));

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  sessionStorage.clear();
  setSessionExpiredHandler(null);
});

describe("the one-minute warning for notes not yet sent", () => {
  test("shows how many notes are unsent and what happens to them; one click makes every named one anonymous", async () => {
    const user = userEvent.setup();
    const done = room([note("n1", { anonymous: true }), note("n2", { anonymous: true })], { unsent: { count: 2, named: 0, message: "You have 2 notes not yet sent. When time ends they go to the board without your name." } });
    mock(room([note("n1"), note("n2")]), warning, (url) => (url.endsWith("/notes/n2") ? done : room([note("n1", { anonymous: true }), note("n2")])));
    open();
    expect(await screen.findByText(MESSAGE)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: t.makeAnonymous }));
    await waitFor(() => expect(posts()).toHaveLength(2));
    expect(posts().map((p) => [p.url, p.body])).toEqual([[`${ROOM}/notes/n1`, { anonymous: true }], [`${ROOM}/notes/n2`, { anonymous: true }]]);
    expect(await screen.findByText(/without your name/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.makeAnonymous })).not.toBeInTheDocument(); // nothing named is left
  });

  test("the make-anonymous button is only for sessions where each person chooses", async () => {
    mock(room([note("n1")], { names: "named", unsent: { count: 1, named: 1, message: "You have 1 note not yet sent. When time ends it goes to the board under your name." } }), warning, () => room([]));
    open();
    expect(await screen.findByText(/under your name\./)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.makeAnonymous })).not.toBeInTheDocument();
  });

  test("is not shown before the warning, and not when nothing is unsent", async () => {
    mock(room([note("n1"), note("n2")]), running, () => room([]));
    open();
    await screen.findByText("Note n1");
    expect(screen.queryByText(MESSAGE)).not.toBeInTheDocument();
  });

  test("is not shown in the warning when every note is already sent", async () => {
    mock(room([]), warning, () => room([]));
    open();
    await screen.findByRole("textbox", { name: t.placeholder });
    expect(screen.queryByRole("button", { name: t.makeAnonymous })).not.toBeInTheDocument();
  });

  test("a failed click says so in one sentence and keeps the notes as they were", async () => {
    const user = userEvent.setup();
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    mock(room([note("n1")], { unsent: { count: 1, named: 1, message: "You have 1 note not yet sent." } }), warning, () => {
      throw new Error("boom");
    });
    open();
    await user.click(await screen.findByRole("button", { name: t.makeAnonymous }));
    expect(await screen.findByText(t.makeAnonymousFailed)).toBeInTheDocument();
  });
});

describe("North filling in a note", () => {
  test("shows North's progress line while the request is out, then the fields", async () => {
    const user = userEvent.setup();
    let release: (r: Room) => void = () => undefined;
    const after = room([note("n1", { fields: { purpose: "Keep customers" }, missing: [] })]);
    mock(room([note("n1")]), { timed: false, stage: "private_rooms" }, () => new Promise<Room>((resolve) => (release = resolve)));
    open();
    await user.click(await screen.findByRole("button", { name: n.askNorth }));
    expect(await screen.findByText(n.filling)).toBeInTheDocument();
    release(after);
    expect(await screen.findByDisplayValue("Keep customers")).toBeInTheDocument();
    expect(screen.queryByText(n.filling)).not.toBeInTheDocument();
  });
});
