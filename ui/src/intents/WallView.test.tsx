import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, test, vi } from "vitest";

import { clockLabel, headerCopy } from "./IntentHeader";
import WallView from "./views/WallView";

// B12: the intent's wall. fetch is stubbed; synthetic text only.
const SID = "b".repeat(32);
const S = `/api/modules/m1_intent/sessions/${SID}`;
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const info = (extra: object = {}, people: object = {}) => ({
  intent_id: "i1", session_id: SID, role: "participant", can_add: true,
  intent: { title: "Cash by custodian", purpose: "See cash before 9am", state: "open", ends: new Date(Date.now() + 3 * 86_400_000 - 1000).toISOString() },
  stages: [{ key: "think_unfiltered", name: "Think unfiltered", state: "open" }, { key: "define_strategically", name: "Define strategically", state: "pending" }],
  wall: { rooms_closed_at: null, frozen_at: null }, people: { invited: 6, joined: 4, initials: ["AL", "KR"], ...people }, ...extra,
});
const BOARD = { stage: "private_rooms", organiser: false, can_edit: false, counts: { notes: 0 }, clusters: [], on_its_own: [] };
const ROOM = { open: true, message: null, title: "", turns: [], notes: [], form: [], north: { practice_on: false, library_on: false, available: true } };

const posts: string[] = [];
function mock(wall: () => Response) {
  posts.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") { posts.push(url); return json(200, { added: 0 }); }
    if (url === "/api/intents/i1/wall") return wall();
    if (url === "/api/intents/i1/clock") return json(200, { box: { state: "on_time", unit: "days", working_days_left: 10, hours_left: 240 } });
    if (url === `${S}/board`) return json(200, BOARD);
    if (url === `${S}/room`) return json(200, ROOM);
    if (url.endsWith("/library")) return json(200, { on: false, available: true, label: "", problems: [], message: null });
    return json(404, {});
  }));
}
const open = () => render(<MemoryRouter initialEntries={["/centre/intent/i1/wall"]}><Routes><Route path="/centre/intent/:intentId/wall" element={<WallView />} /></Routes></MemoryRouter>);
afterEach(() => vi.unstubAllGlobals());

describe("the wall inside an intent", () => {
  test("shows the intent header, the intent's stage bar and the existing wall for the resolved session", async () => {
    const fixedTimestamp = new Date("2026-10-07T12:00:00Z").getTime();
    const dateNowSpy = vi.spyOn(Date, "now").mockReturnValue(fixedTimestamp);
    try {
      mock(() => json(200, info()));
      open();
      expect(await screen.findByTestId("intent-title")).toHaveTextContent("Cash by custodian");
      expect(screen.getByTestId("intent-purpose")).toHaveTextContent("See cash before 9am");
      expect(screen.getByTestId("intent-clock")).toHaveTextContent("3 days left");
      expect(screen.getByTestId("intent-people")).toHaveTextContent("4 / 6 people");
      expect(screen.getByTestId("intent-people")).toHaveTextContent("ALKR");
      expect(screen.getByTestId("stage-bar")).toHaveTextContent("Think unfiltered");
      expect(screen.getByTestId("stage-bar")).toHaveTextContent("Define strategically");
      expect(await screen.findByTestId("lanes")).toBeInTheDocument(); // WallScreen, read by session id
      expect(screen.queryByTestId("read-only")).toBeNull();
      await waitFor(() => expect(posts).toEqual(["/api/intents/i1/suggestions/refresh"])); // North tops up for a person who adds cards
    } finally {
      dateNowSpy.mockRestore();
    }
  });

  test("the header's count is the clock's working days, not the calendar days to the end date", async () => {
    mock(() => json(200, info({ intent: { title: "Cash by custodian", purpose: "See cash before 9am", state: "open", ends: new Date(Date.now() + 14 * 86_400_000).toISOString() } })));
    open();
    expect(await screen.findByTestId("wall-clock")).toHaveTextContent("10 days left");
  });

  test("a reader's lanes come from the intent route, since the session routes do not serve readers", async () => {
    const card = { id: "c0", lane: "pain_point", text: "Late cash report", anonymous: false, author: "AL", mine: false, quarters: 3, guessed: 0, sealed: false };
    mock(() => json(200, info({ role: "observer", can_add: false, cards: [card] })));
    open();
    expect(await screen.findByText("Late cash report")).toBeInTheDocument();
    expect(screen.getByTestId("count-pain_point")).toHaveTextContent("1");
  });

  test("an observer reads: the banner shows and no top-up is asked for", async () => {
    mock(() => json(200, info({ role: "observer", can_add: false })));
    open();
    expect(await screen.findByTestId("read-only")).toHaveTextContent(/You can read this wall\. You do not add cards\./);
    expect(posts).toEqual([]);
  });

  test("a frozen wall shows when and links to the charter", async () => {
    mock(() => json(200, info({ wall: { rooms_closed_at: null, frozen_at: "2026-10-09T17:00:00Z" } })));
    open();
    expect(await screen.findByTestId("intent-frozen")).toHaveTextContent("Frozen on 9 Oct, 17:00");
    expect(screen.getByRole("link", { name: /frozen wall as charter page one/i })).toHaveAttribute("href", "/centre/intent/i1/charter");
  });

  test("Not this one hides a suggestion and Undo brings it back; cards show initials", async () => {
    const sug = { id: "s1", text: "Cash is chased by phone", kind: "pain_point", from: "the board paper" };
    const note = { id: "n1", text: "Late cash", state: "submitted", anonymous: false, kind: "pain_point", quarters: 3, author_name: "Aaron Lyle" };
    let hidden = false;
    mock(() => json(200, info()));
    const base = globalThis.fetch as unknown as (u: string, i?: RequestInit) => Promise<Response>;
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (url === `${S}/board`) return json(409, { error: "wrong_state", message: "not yet" });
      if (url === `${S}/room`) return json(200, { ...ROOM, notes: [note], suggestions: hidden ? [] : [sug] });
      if (init?.method === "POST" && url.endsWith("/hide")) { hidden = true; posts.push(url); return json(200, { ok: true }); }
      if (init?.method === "POST" && url.endsWith("/unhide")) { hidden = false; posts.push(url); return json(200, { ok: true }); }
      return base(url, init);
    }));
    open();
    expect(await screen.findByText("Cash is chased by phone")).toBeInTheDocument();
    expect(document.querySelector("[data-kind=card] .ds-wall-card__foot")).toHaveTextContent(/^AL/);
    expect(screen.queryByText(/Aaron Lyle/)).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Not this one" }));
    expect(posts).toContain("/api/intents/i1/suggestions/s1/hide");
    await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
    expect(posts).toContain("/api/intents/i1/suggestions/s1/unhide");
    expect(await screen.findByText("Cash is chased by phone")).toBeInTheDocument();
  });

  test("empty fields say what is missing, never a zero", async () => {
    mock(() => json(200, info({ session_id: null, intent: { title: "", purpose: "", state: "draft", ends: null } }, { joined: null, initials: [] })));
    open();
    expect(await screen.findByTestId("intent-title")).toHaveTextContent(headerCopy.untitled);
    expect(screen.getByTestId("intent-purpose")).toHaveTextContent(headerCopy.noPurpose);
    expect(screen.getByTestId("intent-clock")).toHaveTextContent("No clock yet");
    expect(screen.getByTestId("intent-people")).toHaveTextContent(/Not available yet/);
    expect(screen.getByTestId("stage-bar")).toHaveTextContent(headerCopy.startsWhenOpened);
    expect(screen.getByText(/the wall for this intent has not been opened/i)).toBeInTheDocument();
  });

  test("nobody joined yet reads as words", async () => {
    mock(() => json(200, info({}, { joined: 0 })));
    open();
    expect(await screen.findByTestId("intent-people")).toHaveTextContent(headerCopy.noJoined);
  });

  test("a refusal shows the server's sentence", async () => {
    mock(() => json(403, { error: "not_allowed", message: "You do not have access to this wall. Ask the organiser to add you." }));
    open();
    expect(await screen.findByText(/Ask the organiser to add you./)).toBeInTheDocument();
    expect(screen.queryByText("Try again")).toBeNull();
  });

  test("a named adviser on an unopened wall is told who opens it", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => (url === "/api/intents/i1/wall" ? json(404, { error: "not_found", message: "We could not find that." }) : url === "/api/intents/i1" ? json(200, { people: { organiser: { name: "Janet Lim" } } }) : json(404, {}))));
    open();
    expect(await screen.findByText("The wall is not open yet. Janet Lim opens it.")).toBeInTheDocument();
  });

  test("an unknown intent says so", async () => {
    mock(() => json(404, { error: "not_found", message: "We could not find that." }));
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent("We could not find that.");
  });
});

describe("the clock chip", () => {
  const now = Date.parse("2026-10-07T12:00:00Z");
  test.each([
    ["2026-10-10T12:00:00Z", "open", "3 days left"],
    ["2026-10-08T00:00:00Z", "open", "12 hours left"],
    ["2026-10-09T12:00:00Z", "open", "2 days left"],
    ["2026-10-07T06:00:00Z", "open", "Overdue by 6 hours"],
    ["2026-10-10T12:00:00Z", "closing", "Closing"],
    ["2026-10-05T12:00:00Z", "open", "Overdue by 2 working days"],
    ["2026-10-10T12:00:00Z", "draft", "No clock yet"],
    [null, "open", "No clock yet"],
  ])("%s %s reads %s", (ends, state, want) => expect(clockLabel(ends, state, now)).toBe(want));
});
