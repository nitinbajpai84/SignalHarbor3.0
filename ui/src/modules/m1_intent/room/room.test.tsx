import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import App from "../../../App";
import { setSessionExpiredHandler } from "../../../api/client";
import { createEventReader } from "../../../live/sse";
import type { JoinView, Preparation, RoomView, SeatMe, SessionView } from "../api";
import { m1Board, m1Flow, m1Nira, m1Room } from "../copy";
import { loadLink, loadToken, loadTokenByCode, saveToken } from "./guestToken";

const saveTokenForTest = () => saveToken({ token: FAKE_TOKEN, sessionId: SID, code: CODE });

// M1-P02 screens: the join page (no sign-in), the seat picker, the lobby, the organiser's start-room and room flows.
// fetch is stubbed; the live stream is a controllable fetch body. The token must travel only in a header.

const BASE = "/api/modules/m1_intent";
const CODE = "AbCdEfGhIjKlMnOpQrStUv"; // fake, 22 characters
const SID = "a".repeat(32);
const FAKE_TOKEN = `${SID}.${"x".repeat(43)}`; // fake
const PREP: Preparation = {
  purpose: "Agree what we want to know", outcome: "A signed charter", charter_template: "standard", seats: 3,
  length_minutes: 20, split: { briefing: 4, individual: 8, together: 8 }, north_industry_practice: false,
  north_problem_library: false, briefing_video: "standard", approver_name: "", approver_account_id: null,
};
const session = (over: Partial<SessionView> = {}): SessionView => ({
  id: SID, state: "draft", paused_from: null, is_solo: false, editable: true, preparation: PREP,
  outcome_id: "b".repeat(32), created_at: "2026-10-03T10:00:00+00:00", updated_at: "2026-10-03T10:00:00+00:00", ...over,
});
const ME: SeatMe = { seat: 2, name: "Ada", role: "Planner", late: false, see_briefing_first: false };
const picture = (states: ("free" | "taken" | "revoked")[]) => states.map((state, i) => ({ n: i + 1, state }));
const joinView = (over: Partial<JoinView> = {}): JoinView => ({
  session_id: SID, state: "lobby", signed_in: false, length_minutes: 20, token: null, me: null,
  seats: picture(["free", "taken", "free"]), ...over,
});
const roomView = (over: Partial<RoomView> = {}): RoomView => ({
  session_id: SID, state: "lobby", length_minutes: 20, is_solo: false, organiser: false, me: ME, arrived: 1,
  seat_count: 3,
  seats: [{ n: 1, state: "free", mine: false }, { n: 2, state: "taken", mine: true, name: "Ada", role: "Planner" },
    { n: 3, state: "free", mine: false }],
  ...over,
});

interface Call { method: string; url: string; headers: Record<string, string>; body: unknown }
const calls: Call[] = [];
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function liveStream() {
  let ctl: ReadableStreamDefaultController<Uint8Array> | null = null;
  const enc = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({ start: (c) => { ctl = c; } });
  return {
    response: () => new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } }),
    push: (v: unknown) => ctl?.enqueue(enc.encode(`data: ${JSON.stringify(v)}\n\n`)),
  };
}

interface World {
  signedIn?: boolean;
  savedLink?: string;          // M1-P05: the join link the server keeps for the organiser
  roles?: string[];
  join?: (body: { code: string; seat?: number; name?: string; role?: string }, headers: Record<string, string>) => Response | Promise<Response>;
  live?: () => Response | Promise<Response>;
  session?: SessionView;
  started?: SessionView;       // what the session answers once "start" has been called
  hold?: boolean;              // join never answers: the loading state
  network?: boolean;           // join cannot reach the service
  stage?: string;              // what the guest's stage check (/lobby) answers; none: not answered
}
let started = false;

function mock(w: World) {
  calls.length = 0;
  started = false;
  vi.stubGlobal("EventSource", function () { throw new Error("EventSource cannot send the token header"); });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      const headers = (init?.headers ?? {}) as Record<string, string>;
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      calls.push({ method, url, headers, body });
      if (url === "/api/auth/me")
        return w.signedIn ? json(200, { display_name: "Ann", company_id: "co-a", roles: w.roles ?? ["company_admin"] })
          : json(401, { error: "session_expired", message: "x", login_url: "/login" });
      if (url === "/api/company") return json(200, { company_id: "co-a", name: "Harbor Test Co", industry: "none" });
      if (url === "/api/modules")
        return json(200, [{ id: "m1_intent", number: 1, name: "Intent", description: "d", agent: "North" }]);
      if (url === `${BASE}/join`) {
        if (w.network) throw new TypeError("network");
        if (w.hold) return new Promise<Response>(() => undefined);
        return w.join ? w.join(body, headers) : json(404, { error: "link_invalid", message: m1Room.join.notWorking });
      }
      if (url.endsWith("/live")) return w.live ? w.live() : json(401, {});
      if (url === `${BASE}/sessions/${SID}/lobby`) return w.stage ? json(200, roomView({ state: w.stage })) : json(404, {});
      if (url.startsWith(`${BASE}/sessions/${SID}/board`)) return json(409, { error: "rooms_open", message: "The board opens when the private rooms close." });
      if (url === `${BASE}/lists`)
        return json(200, { seats: { min: 1, max: 10 }, time_presets_minutes: [5, 10, 20, 30], custom_length_minutes: { min: 5, max: 120 },
          min_stage_minutes: 1, default_length_minutes: 20, default_split: PREP.split, default_split_percent: { briefing: 20, individual: 40, together: 40 },
          briefing_video_options: ["standard", "none"], charter_templates: [{ id: "standard", name: "Standard charter", description: "d" }],
          default_template: "standard", north: { problem_library_available: false, industry_practice_available: false, problem_count: 0, message: null } });
      if (url === `${BASE}/templates`) return json(200, []);
      if (url === `${BASE}/sessions/${SID}/start`) { started = true; return json(201, { join_path: `/join/${CODE}`, state: "lobby" }); }
      if (url === `${BASE}/sessions/${SID}/link`) return json(200, { join_path: `/join/${"Z".repeat(22)}`, state: "lobby" });
      if (url === `${BASE}/sessions/${SID}/join-link`) // M1-P05: the saved link; by default nothing is saved
        return w.savedLink ? json(200, { join_path: w.savedLink, state: "lobby" }) : json(404, { error: "no_link", message: "This link was not saved. Make a new link to share it." });
      if (url === `${BASE}/sessions/${SID}/briefing`) return json(200, { state: "briefing" });
      if (url.startsWith(`${BASE}/sessions/${SID}/seats/`)) return json(200, roomView({ organiser: true, me: null, arrived: 0,
        seats: [{ n: 1, state: "revoked", mine: false }, { n: 2, state: "free", mine: false }, { n: 3, state: "free", mine: false }] }));
      if (url === `${BASE}/sessions/${SID}`) return json(200, started && w.started ? w.started : (w.session ?? session()));
      return json(404, {});
    }),
  );
}

function open(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  sessionStorage.clear();
  setSessionExpiredHandler(null);
});

/** The seat radios only: the page also has the theme choice. */
const seatRadios = async () => within(await screen.findByRole("group", { name: m1Room.join.chooseSeat })).getAllByRole("radio");
const joinCalls = () => calls.filter((c) => c.url === `${BASE}/join`);
const FORBIDDEN_WORDS = /token|json|http|uuid|stack|null|undefined|\bid\b|api|error:/i;

describe("the event reader", () => {
  test("reads events split across pieces, joins data lines and ignores comments", () => {
    const seen: string[] = [];
    const read = createEventReader((d) => seen.push(d));
    read('data: {"a"');
    read(':1}\n\n: keep-alive\n\ndata: x\r\ndata: y\r\n\r\n');
    expect(seen).toEqual(['{"a":1}', "x\ny"]);
  });
});

describe("join page: no sign-in, five states", () => {
  test("the four opening lines show before the seats, from the session", async () => {
    mock({ join: () => json(200, joinView()) });
    open(`/join/${CODE}`);
    const lines = await screen.findByRole("list", { name: "About this session" });
    expect(lines).toHaveTextContent("1 of 3 seats are taken");
    expect(lines).toHaveTextContent("What it is for");
    expect(lines).toHaveTextContent("What you can contribute");
    expect(lines).toHaveTextContent("Anything you upload stays with this company's agents.");
    expect(lines.compareDocumentPosition(await screen.findByRole("group", { name: m1Room.join.chooseSeat })) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  test("the guest header is present and there is no top bar", async () => {
    mock({ join: () => json(200, joinView()) });
    const { container } = open(`/join/${CODE}`);
    await screen.findByRole("heading", { name: m1Room.join.title });
    expect(container.querySelector("header.guest-header")).not.toBeNull();
    expect(container.querySelector(".n-topbar")).toBeNull();
  });

  test("loading", async () => {
    mock({ hold: true });
    open(`/join/${CODE}`);
    expect(await screen.findByRole("status")).toHaveTextContent("Loading");
  });

  test("a signed-out visitor sees the seats, not the sign-in page", async () => {
    mock({ join: () => json(200, joinView()) });
    open(`/join/${CODE}`);
    expect(await screen.findByRole("heading", { name: m1Room.join.title })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Sign in" })).not.toBeInTheDocument();
    const radios = await seatRadios();
    expect(radios).toHaveLength(3);
    expect(radios.map((r) => (r as HTMLInputElement).disabled)).toEqual([false, true, false]); // only free seats
    // opening the link only looks: the code is in the body, never in a URL
    expect(joinCalls()[0]?.body).toEqual({ code: CODE });
    expect(calls.every((c) => !c.url.includes(CODE))).toBe(true);
  });

  test("empty: no free seat says so in plain words", async () => {
    mock({ join: () => json(200, joinView({ seats: picture(["taken", "taken", "revoked"]) })) });
    open(`/join/${CODE}`);
    expect(await screen.findByText(m1Room.join.full)).toBeInTheDocument();
  });

  test("error: the service cannot be reached; one sentence and a way to try again", async () => {
    mock({ network: true });
    open(`/join/${CODE}`);
    expect(await screen.findByText(m1Room.join.network)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  test.each([
    [404, "link_invalid", m1Room.join.notWorking],
    [409, "link_closed", "This session has closed, so the link no longer works."],
    [409, "paused", "This session is paused. Please try again when the organiser resumes it."],
  ])("refused: %s %s shows the server's plain words", async (status, error, message) => {
    mock({ join: () => json(status, { error, message }) });
    open(`/join/${CODE}`);
    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(FORBIDDEN_WORDS);
  });

  test("refused: a person signed in to another company is told plainly and can sign out", async () => {
    const message = "You are signed in to a different company, so you cannot join this session. Sign out, then open the link again.";
    mock({ signedIn: true, join: () => json(403, { error: "other_company", message }) });
    open(`/join/${CODE}`);
    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: m1Room.join.signOut })).toBeInTheDocument();
  });

  test("a seat that was just taken: plain message and a fresh picture, nothing lost", async () => {
    const user = userEvent.setup();
    let looks = 0;
    mock({
      join: (body) => {
        if (body.seat !== undefined) return json(409, { error: "seat_taken", message: "That seat has just been taken. Please choose another." });
        looks += 1;
        return json(200, joinView({ seats: picture(looks === 1 ? ["free", "free", "free"] : ["taken", "free", "free"]) }));
      },
    });
    open(`/join/${CODE}`);
    await user.click((await seatRadios())[0] as HTMLElement);
    await user.type(screen.getByLabelText(m1Room.join.name), "Ada");
    await user.type(screen.getByLabelText(new RegExp(m1Room.join.role)), "Planner");
    await user.click(screen.getByRole("button", { name: m1Room.join.submit }));
    // shown as an error, not as a quiet note
    const message = await screen.findByText("That seat has just been taken. Please choose another.");
    expect(message).toHaveAttribute("role", "alert");
    expect(message.className).toContain("state-error");
    expect(((await seatRadios())[0] as HTMLInputElement).disabled).toBe(true);
    expect(loadToken(SID)).toBeNull();
  });

  test("each seat radio has a name a screen reader can use: seat number and state", async () => {
    mock({ join: () => json(200, joinView({ seats: picture(["free", "taken", "revoked"]) })) });
    open(`/join/${CODE}`);
    const radios = await seatRadios();
    expect(radios.map((r) => r.getAttribute("aria-label"))).toEqual(["Seat 1, free", "Seat 2, taken", "Seat 3, removed"]);
    expect(screen.getByRole("radio", { name: "Seat 1, free" })).toBeEnabled();
  });

  test("a seated guest follows the session to the board when the rooms close, instead of a closed room", async () => {
    mock({ join: () => json(200, joinView({ me: ME })), stage: "board" });
    open(`/join/${CODE}`);
    expect(await screen.findByRole("heading", { name: m1Board.title })).toBeInTheDocument();
  });

  test("an earlier seat that is gone is a quiet note, not an error", async () => {
    saveTokenForTest();
    mock({ join: () => json(200, joinView({ seats: picture(["free", "free", "free"]) })) });
    open(`/join/${CODE}`);
    const note = await screen.findByText(m1Room.join.earlierGone);
    expect(note.className).not.toContain("state-error");
  });

  test("a bad name is explained in plain words", async () => {
    const user = userEvent.setup();
    mock({
      join: (body) => body.seat === undefined ? json(200, joinView()) :
        json(422, { error: "invalid", message: "Your name can have at most 60 characters.", field: "name" }),
    });
    open(`/join/${CODE}`);
    await user.click((await seatRadios())[0] as HTMLElement);
    await user.type(screen.getByLabelText(m1Room.join.name), "x");
    await user.type(screen.getByLabelText(new RegExp(m1Room.join.role)), "y");
    await user.click(screen.getByRole("button", { name: m1Room.join.submit }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Your name can have at most 60 characters.");
  });

  test("choosing no seat asks for one", async () => {
    const user = userEvent.setup();
    mock({ join: () => json(200, joinView()) });
    open(`/join/${CODE}`);
    await seatRadios();
    await user.type(screen.getByLabelText(m1Room.join.name), "Ada");
    await user.type(screen.getByLabelText(new RegExp(m1Room.join.role)), "Planner");
    await user.click(screen.getByRole("button", { name: m1Room.join.submit }));
    expect(await screen.findByRole("alert")).toHaveTextContent(m1Room.join.needSeat);
    expect(joinCalls()).toHaveLength(1); // only the first look
  });
});

describe("join, lobby and rejoin: the token travels in a header only", () => {
  test("take a seat with no account: the token is kept in this tab and used only as a header; Nira greets by name", async () => {
    const user = userEvent.setup();
    const stream = liveStream();
    mock({
      join: (body) => body.seat === undefined ? json(200, joinView())
        : json(200, joinView({ token: FAKE_TOKEN, me: ME, seats: picture(["free", "taken", "free"]) })),
      live: stream.response,
    });
    open(`/join/${CODE}`);
    await user.click((await seatRadios())[2] as HTMLElement);
    await user.type(screen.getByLabelText(m1Room.join.name), "Ada");
    await user.type(screen.getByLabelText(new RegExp(m1Room.join.role)), "Planner");
    await user.click(screen.getByRole("button", { name: m1Room.join.submit }));
    const take = joinCalls()[1];
    expect(take?.body).toEqual({ code: CODE, seat: 3, name: "Ada", role: "Planner" });
    expect(loadToken(SID)).toEqual({ token: FAKE_TOKEN, sessionId: SID, code: CODE });
    // the lobby opens its live stream with the header; no EventSource, no token in any URL
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/live"))).toBe(true));
    const liveCall = calls.find((c) => c.url.endsWith("/live"));
    expect(liveCall?.headers["X-Session-Token"]).toBe(FAKE_TOKEN);
    expect(calls.every((c) => !c.url.includes(FAKE_TOKEN) && !c.url.includes(CODE) && !c.url.includes("x".repeat(43)))).toBe(true);
    act(() => stream.push(roomView()));
    expect(await screen.findByText(m1Room.lobby.greeting("Ada", 20))).toBeInTheDocument();
    const seats = screen.getByRole("list", { name: m1Room.seat.picture });
    expect(within(seats).getAllByRole("listitem")).toHaveLength(3);
    expect(within(seats).getByText(m1Room.seat.you)).toBeInTheDocument();
    expect(screen.getByText(m1Room.lobby.waiting)).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: (n) => n !== m1Nira.question }) /* Nira's own ask box is always there */).not.toBeInTheDocument(); // no notes in the lobby
    expect(document.body.textContent).not.toMatch(/token|json|uuid|null|undefined/i);
  });

  test("the same link and the stored token go straight back to the same seat, with no new token", async () => {
    const stream = liveStream();
    saveTokenForTest();
    mock({ join: () => json(200, joinView({ me: ME })), live: stream.response });
    open(`/join/${CODE}`);
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/live"))).toBe(true));
    expect(joinCalls()).toHaveLength(1);
    expect(joinCalls()[0]?.headers["X-Session-Token"]).toBe(FAKE_TOKEN);
    expect(joinCalls()[0]?.body).toEqual({ code: CODE });
    expect(await screen.findByText(m1Room.lobby.yourSeat(2, "Ada", "Planner"))).toBeInTheDocument();
    expect(loadToken(SID)?.token).toBe(FAKE_TOKEN);
  });

  test("a stored token that no longer works is dropped and the person is told, then picks a free seat", async () => {
    saveTokenForTest();
    mock({ join: () => json(200, joinView({ me: null })) });
    open(`/join/${CODE}`);
    expect(await screen.findByText(m1Room.join.earlierGone)).toBeInTheDocument();
    expect(loadToken(SID)).toBeNull();
  });

  test("a latecomer is told they will see the briefing first", async () => {
    const stream = liveStream();
    mock({ join: () => json(200, joinView({ me: { ...ME, late: true, see_briefing_first: true }, state: "briefing" })), live: stream.response });
    saveTokenForTest();
    open(`/join/${CODE}`);
    expect(await screen.findByText(m1Room.lobby.briefingFirst)).toBeInTheDocument();
  });

  test("live: an arrival and the start of the briefing appear without a reload", async () => {
    const stream = liveStream();
    saveTokenForTest();
    mock({ join: () => json(200, joinView({ me: ME })), live: stream.response });
    open(`/join/${CODE}`);
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/live"))).toBe(true));
    act(() => stream.push(roomView()));
    expect(await screen.findByText(m1Room.lobby.arrived(1, 3))).toBeInTheDocument();
    act(() => stream.push(roomView({ arrived: 2, seats: [{ n: 1, state: "taken", mine: false, name: "Bo", role: "Buyer" },
      { n: 2, state: "taken", mine: true, name: "Ada", role: "Planner" }, { n: 3, state: "free", mine: false }] })));
    expect(await screen.findByText(m1Room.lobby.arrived(2, 3))).toBeInTheDocument();
    expect(screen.getByText("Bo, Buyer")).toBeInTheDocument();
    act(() => stream.push(roomView({ state: "briefing" })));
    expect(await screen.findByText(m1Room.lobby.briefing)).toBeInTheDocument();
  });

  test("a removed seat: the stream is refused, the person is told in plain words and the token is dropped", async () => {
    const user = userEvent.setup();
    saveTokenForTest();
    let looks = 0;
    mock({
      join: () => json(200, looks++ === 0 ? joinView({ me: ME }) : joinView()),
      live: () => json(401, { error: "session_expired", message: "x", login_url: "/login" }),
    });
    open(`/join/${CODE}`);
    expect(await screen.findByText(m1Room.lobby.ended)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: m1Room.lobby.endedButton }));
    expect(await screen.findByRole("heading", { name: m1Room.join.title })).toBeInTheDocument();
    expect(loadToken(SID)).toBeNull();
  });

  test("a signed-in organiser joining with their account sends no token and keeps a way back to their page", async () => {
    const stream = liveStream();
    mock({ signedIn: true, join: () => json(200, joinView({ signed_in: true, me: ME })), live: stream.response });
    open(`/join/${CODE}`);
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/live"))).toBe(true));
    expect(calls.find((c) => c.url.endsWith("/live"))?.headers["X-Session-Token"]).toBeUndefined();
    act(() => stream.push(roomView({ organiser: true })));
    expect(await screen.findByRole("link", { name: m1Room.lobby.backToOrganiser })).toHaveAttribute(
      "href", `/modules/m1_intent/sessions/${SID}`);
  });
});

describe("organiser: start the room, the link, seats, revoke, briefing", () => {
  test("a saved draft offers Start the room, asks first, then keeps the link for this tab only", async () => {
    const user = userEvent.setup();
    const stream = liveStream();
    mock({ signedIn: true, session: session(), started: session({ state: "lobby", editable: false }), live: stream.response });
    open(`/modules/m1_intent/sessions/${SID}`);
    await user.click(await screen.findByRole("button", { name: m1Room.start.button }));
    expect(screen.getByText(m1Room.start.sure)).toBeInTheDocument();
    expect(calls.some((c) => c.url.endsWith("/start"))).toBe(false); // asked, not yet done
    await user.click(screen.getByRole("button", { name: m1Room.start.yes }));
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/start") && c.method === "POST")).toBe(true));
    expect(loadLink(SID)).toBe(`/join/${CODE}`);
    // now the room shows the link
    expect(await screen.findByDisplayValue(new RegExp(`/join/${CODE}$`))).toBeInTheDocument();
  });

  test("the room: link with a copy button, seats against arrivals live, no link in any API address", async () => {
    const user = userEvent.setup();
    const stream = liveStream();
    const writeText = vi.fn(async () => undefined);
    vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText } });
    sessionStorage.setItem(`sh.m1.link.${SID}`, `/join/${CODE}`);
    mock({ signedIn: true, session: session({ state: "lobby", editable: false }), live: stream.response });
    open(`/modules/m1_intent/sessions/${SID}`);
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/live"))).toBe(true));
    expect(calls.find((c) => c.url.endsWith("/live"))?.headers["X-Session-Token"]).toBeUndefined(); // the cookie is used
    act(() => stream.push(roomView({ organiser: true, me: null, arrived: 1, seats: [
      { n: 1, state: "taken", mine: false, name: "Bo", role: "Buyer", late: false }, { n: 2, state: "free", mine: false },
      { n: 3, state: "free", mine: false }] })));
    expect(await screen.findByText(m1Room.organiser.arrived(1, 3))).toBeInTheDocument();
    expect(screen.getByText("Bo, Buyer")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: m1Room.organiser.copy }));
    expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/join/${CODE}`);
    expect(await screen.findByText(m1Room.organiser.copied)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: m1Room.organiser.joinMyself })).toHaveAttribute("href", `/join/${CODE}`);
    expect(calls.every((c) => !c.url.includes(CODE))).toBe(true);
  });

  test("free a seat before the rooms open: asks first, then reopens it so the person can rejoin with the link", async () => {
    const user = userEvent.setup();
    const stream = liveStream();
    sessionStorage.setItem(`sh.m1.link.${SID}`, `/join/${CODE}`);
    mock({ signedIn: true, session: session({ state: "lobby", editable: false }), live: stream.response });
    open(`/modules/m1_intent/sessions/${SID}`);
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/live"))).toBe(true));
    act(() => stream.push(roomView({ organiser: true, me: null, seats: [
      { n: 1, state: "taken", mine: false, name: "Ada", role: "Planner" }, { n: 2, state: "free", mine: false },
      { n: 3, state: "free", mine: false }] })));
    const freeButton = { name: m1Room.freeLabel("Ada", 1) };
    await user.click(await screen.findByRole("button", freeButton));
    expect(screen.getByText(m1Room.organiser.freeSure("Ada", 1))).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: m1Room.organiser.removeNo }));
    expect(calls.some((c) => c.url.includes("/revoke"))).toBe(false); // asked, not done
    await user.click(screen.getByRole("button", freeButton));
    await user.click(screen.getByRole("button", { name: m1Room.organiser.freeYes }));
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/seats/1/revoke?reopen=1") && c.method === "POST")).toBe(true));
    expect(screen.getByText(m1Room.freedNote(1))).toBeInTheDocument();
  });

  test("once the rooms are open a taken seat can only be removed, not freed", async () => {
    const stream = liveStream();
    sessionStorage.setItem(`sh.m1.link.${SID}`, `/join/${CODE}`);
    mock({ signedIn: true, session: session({ state: "private_rooms", editable: false }), live: stream.response });
    open(`/modules/m1_intent/sessions/${SID}`);
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/live"))).toBe(true));
    act(() => stream.push(roomView({ state: "private_rooms", organiser: true, me: null, seats: [
      { n: 1, state: "taken", mine: false, name: "Ada", role: "Planner" }, { n: 2, state: "free", mine: false },
      { n: 3, state: "free", mine: false }] })));
    expect(await screen.findByRole("button", { name: m1Room.removeLabel("Ada", 1) })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: m1Room.freeLabel("Ada", 1) })).not.toBeInTheDocument();
  });

  test("the guest's seat is kept in this browser (not just this tab) so the same link brings them back", () => {
    saveTokenForTest();
    expect(localStorage.getItem(`sh.m1.guest.${SID}`)).not.toBeNull();
    expect(sessionStorage.getItem(`sh.m1.guest.${SID}`)).toBeNull();
    expect(loadTokenByCode(CODE)?.sessionId).toBe(SID);
  });

  test("remove a seat: asks first, then removes; keeping them does nothing", async () => {
    const user = userEvent.setup();
    const stream = liveStream();
    sessionStorage.setItem(`sh.m1.link.${SID}`, `/join/${CODE}`);
    mock({ signedIn: true, session: session({ state: "lobby", editable: false }), live: stream.response });
    open(`/modules/m1_intent/sessions/${SID}`);
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/live"))).toBe(true));
    act(() => stream.push(roomView({ organiser: true, me: null, seats: [
      { n: 1, state: "taken", mine: false, name: "Ada", role: "Planner" }, { n: 2, state: "free", mine: false },
      { n: 3, state: "free", mine: false }] })));
    const removeButton = { name: m1Room.removeLabel("Ada", 1) }; // the button says who and which seat to a screen reader
    await user.click(await screen.findByRole("button", removeButton));
    expect(screen.getByText(m1Room.organiser.removeSure("Ada", 1))).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: m1Room.organiser.removeNo }));
    expect(calls.some((c) => c.url.includes("/revoke"))).toBe(false);
    await user.click(screen.getByRole("button", removeButton));
    await user.click(screen.getByRole("button", { name: m1Room.organiser.removeYes }));
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/seats/1/revoke") && c.method === "POST")).toBe(true));
    expect(await screen.findByText(m1Room.seat.revoked)).toBeInTheDocument();
    // the removed person's name is not shown again, and the organiser is told to make a new link
    expect(screen.queryByText(/Ada/)).not.toBeInTheDocument();
    expect(screen.getByText(m1Room.removedNote(1))).toBeInTheDocument();
  });

  test("the new-link question can be answered 'Keep this link', which changes nothing", async () => {
    const user = userEvent.setup();
    const stream = liveStream();
    sessionStorage.setItem(`sh.m1.link.${SID}`, `/join/${CODE}`);
    mock({ signedIn: true, session: session({ state: "lobby", editable: false }), live: stream.response });
    open(`/modules/m1_intent/sessions/${SID}`);
    await user.click(await screen.findByRole("button", { name: m1Room.organiser.newLink }));
    await user.click(screen.getByRole("button", { name: m1Room.keepLink }));
    expect(calls.some((c) => c.url.endsWith("/link"))).toBe(false);
    expect(screen.getByDisplayValue(new RegExp(`/join/${CODE}$`))).toBeInTheDocument();
  });

  test("M1-P05: the organiser sees the saved link again in a fresh tab, without making a new one, and is told what a new one does", async () => {
    const stream = liveStream();
    // nothing in this tab's storage: the server's saved link is shown
    mock({ signedIn: true, session: session({ state: "lobby", editable: false }), live: stream.response, savedLink: `/join/${CODE}` });
    open(`/modules/m1_intent/sessions/${SID}`);
    expect(await screen.findByDisplayValue(new RegExp(`/join/${CODE}$`))).toBeInTheDocument();
    expect(screen.getByText(m1Flow.linkMakeHelp)).toBeInTheDocument();
    expect(calls.some((c) => c.method === "POST" && c.url.endsWith("/link"))).toBe(false);
  });

  test("the organiser's room and the start-room panel carry the class the dark-theme rules attach to", async () => {
    const stream = liveStream();
    mock({ signedIn: true, session: session({ state: "lobby", editable: false }), live: stream.response });
    open(`/modules/m1_intent/sessions/${SID}`);
    expect((await screen.findByRole("region", { name: m1Room.organiser.title })).className).toContain("m1-room");
  });

  test("start the briefing with empty seats; a new link asks first and replaces the shown link", async () => {
    const user = userEvent.setup();
    const stream = liveStream();
    sessionStorage.setItem(`sh.m1.link.${SID}`, `/join/${CODE}`);
    mock({ signedIn: true, session: session({ state: "lobby", editable: false }), live: stream.response });
    open(`/modules/m1_intent/sessions/${SID}`);
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/live"))).toBe(true));
    act(() => stream.push(roomView({ organiser: true, me: null, arrived: 0, seats: picture(["free", "free", "free"]).map((s) => ({ ...s, mine: false })) })));
    await user.click(await screen.findByRole("button", { name: m1Room.organiser.newLink }));
    expect(screen.getByText(m1Room.organiser.newLinkSure)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: m1Room.organiser.newLinkYes }));
    expect(await screen.findByDisplayValue(new RegExp(`/join/${"Z".repeat(22)}$`))).toBeInTheDocument();
    expect(loadLink(SID)).toBe(`/join/${"Z".repeat(22)}`);
    await user.click(screen.getByRole("button", { name: m1Room.organiser.startBriefing }));
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/briefing") && c.method === "POST")).toBe(true));
  });

  test("after a reload the link is not on screen: the page says why and offers a new one", async () => {
    const stream = liveStream();
    mock({ signedIn: true, session: session({ state: "lobby", editable: false }), live: stream.response });
    open(`/modules/m1_intent/sessions/${SID}`);
    expect(await screen.findByText(m1Room.organiser.linkGone)).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: (n) => n !== m1Nira.question }) /* Nira's own ask box is always there */).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: m1Room.organiser.newLink })).toBeInTheDocument();
  });

  test("a closed session shows no link and no remove buttons", async () => {
    const stream = liveStream();
    sessionStorage.setItem(`sh.m1.link.${SID}`, `/join/${CODE}`);
    mock({ signedIn: true, session: session({ state: "closed", editable: false }), live: stream.response });
    open(`/modules/m1_intent/sessions/${SID}`);
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/live"))).toBe(true));
    act(() => stream.push(roomView({ state: "closed", organiser: true, me: null, seats: [
      { n: 1, state: "taken", mine: false, name: "Ada", role: "Planner" }] })));
    expect(await screen.findByText(m1Room.organiser.sessionClosed)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: m1Room.organiser.remove })).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue(new RegExp(CODE))).not.toBeInTheDocument();
  });

  test("the wording of the organiser's room has no technical words", async () => {
    const stream = liveStream();
    sessionStorage.setItem(`sh.m1.link.${SID}`, `/join/${CODE}`);
    mock({ signedIn: true, session: session({ state: "lobby", editable: false }), live: stream.response });
    open(`/modules/m1_intent/sessions/${SID}`);
    await screen.findByRole("region", { name: m1Room.organiser.title });
    const text = within(screen.getByRole("region", { name: m1Room.organiser.title })).getByText(m1Room.organiser.linkHelp).parentElement?.textContent ?? "";
    expect(text).not.toMatch(FORBIDDEN_WORDS);
  });
});

describe("source rules", () => {
  test("no EventSource anywhere in the screens, and fetch stays in the one client file", async () => {
    const { readFileSync, readdirSync, statSync } = await import("node:fs");
    const SRC = `${process.cwd().replace(/\\/g, "/")}/src`;
    const walk = (dir: string): string[] =>
      readdirSync(dir).flatMap((n) => (statSync(`${dir}/${n}`).isDirectory() ? walk(`${dir}/${n}`) : [`${dir}/${n}`]));
    const mine = walk(SRC).filter((f) => /\/(live|room)\/|JoinPage/.test(f) && /\.(ts|tsx)$/.test(f) && !f.endsWith(".test.tsx"));
    expect(mine.length).toBeGreaterThan(8);
    for (const f of mine) {
      const src = readFileSync(f, "utf-8");
      expect(src, f).not.toMatch(/new EventSource|\bfetch\(/);
      expect(src, f).not.toMatch(/:\s*any\b|\bas any\b/);
    }
  });
});
