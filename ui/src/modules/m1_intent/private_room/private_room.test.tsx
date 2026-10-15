import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import App from "../../../App";
import { setSessionExpiredHandler } from "../../../api/client";
import type { Library, Room, RoomNote } from "./roomApi";
import { m1PrivateRoom as t } from "../copy";

// M1-P04 screens: the private room with North, read-back, correction, industry practice card, problem library,
// the refused state outside the rooms stage, and the five states. fetch is stubbed; nothing leaves the page.

const SID = "a".repeat(32);
const ROOM = `/api/modules/m1_intent/sessions/${SID}/room`;
const NORTH = { practice_on: true, library_on: true, available: true };
const note = (over: Partial<RoomNote> = {}): RoomNote => ({
  id: "n1", text: "Renewals slipped in April", state: "draft", source: { kind: "typed" }, priority: null,
  practice: null, practice_added: [], created_at: "2026-10-03T10:00:00+00:00", updated_at: "2026-10-03T10:00:00+00:00",
  fields: {}, labels_suggested: [], anonymous: false, missing: [], ...over,
});
const card = { problem_id: "P-1", label: "Industry practice (suggestion)", company_decides: "Your company decides.",
  items: ["Split the slip by region first"], decision: "offered" as const };
const emptyRoom = (over: Partial<Room> = {}): Room => ({ open: true, message: null, title: "", turns: [], notes: [], form: [], north: NORTH, ...over });
const busyRoom = (over: Partial<Room> = {}): Room => ({
  ...emptyRoom(),
  turns: [
    { id: "t1", role: "person", text: "Renewals slipped in April", at: "x" },
    { id: "t2", role: "north", text: "Who is affected?", at: "x", answered: true, readback: { note_id: "n1", text: "Renewals slipped in April" } },
  ],
  notes: [note({ practice: card })],
  ...over,
});
const NO_LIB = "There is no problem library for your industry yet.";
const OFF = "The organiser has not switched on the problem library for this session.";
const LIB: Library = { on: true, available: true, label: "Industry practice (suggestion)", message: null,
  problems: [{ id: "P-1", text: "Where are renewals slipping behind plan?" }, { id: "P-2", text: "Which suppliers deliver late?" }] };

interface World {
  room?: Room;
  library?: Library;
  roomStatus?: number;
  roomBody?: unknown;
  hold?: boolean;
  postStatus?: number;
  postBody?: unknown;
  after?: Room;
}
const calls: { method: string; url: string; body: unknown }[] = [];
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function mock(w: World) {
  calls.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    if (url === "/api/auth/me") return json(200, { display_name: "Ann", company_id: "co-a", roles: ["company_admin"] });
    if (url === "/api/company") return json(200, { company_id: "co-a", name: "Harbor Test Co", industry: "none" });
    if (url === "/api/modules") return json(200, [{ id: "m1_intent", number: 1, name: "Intent", description: "d", agent: "North" }]);
    if (url === ROOM && method === "GET") {
      if (w.hold) return new Promise<Response>(() => undefined);
      return w.roomStatus ? json(w.roomStatus, w.roomBody ?? {}) : json(200, w.room ?? emptyRoom());
    }
    if (url.endsWith("/timer")) return json(200, { timed: false, stage: "private_rooms" }); // M1-UI1: the room shows the stage timer when there is one
    if (url === `${ROOM}/library`) return json(200, w.library ?? { ...LIB, on: false, problems: [], message: OFF });
    if (method !== "GET" && url.startsWith(ROOM)) {
      if (w.postStatus) return json(w.postStatus, w.postBody ?? {});
      return json(200, w.after ?? busyRoom());
    }
    return json(404, {});
  }));
}
const open = () => render(<MemoryRouter initialEntries={[`/modules/m1_intent/sessions/${SID}/room`]}><App /></MemoryRouter>);
const posts = () => calls.filter((c) => c.method !== "GET" && c.url.startsWith(ROOM));

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  sessionStorage.clear();
  setSessionExpiredHandler(null);
});

describe("private room: five states", () => {
  test("loading", async () => {
    mock({ hold: true });
    open();
    expect(await screen.findByRole("heading", { name: t.title })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Loading");
  });

  test("empty: an honest hint and a way to write the first note", async () => {
    mock({ room: emptyRoom() });
    open();
    expect(await screen.findByText(t.emptyChat)).toBeInTheDocument();
    expect(screen.getByText(t.notesEmpty)).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: t.placeholder })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: t.sendReply })).toBeDisabled(); // nothing to send yet
    expect(screen.getByRole("button", { name: t.sendNote })).toBeDisabled();
  });

  test("error: one sentence and a way to try again", async () => {
    mock({ roomStatus: 500, roomBody: { detail: "boom" } });
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent(t.loadFailed);
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  test("refused: a role without access is told so", async () => {
    mock({ roomStatus: 403, roomBody: { error: "forbidden", message: "x" } });
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent("You do not have access to this");
  });

  test("populated: the conversation, the read-back in the person's own words, and the note draft", async () => {
    mock({ room: busyRoom() });
    open();
    expect(await screen.findByText("Who is affected?")).toBeInTheDocument();
    expect(screen.getByText(t.readback)).toBeInTheDocument();
    expect(screen.getByText(t.readbackAsk)).toBeInTheDocument();
    const notes = screen.getByRole("region", { name: t.notesHeading });
    expect(within(notes).getByText("Renewals slipped in April")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: t.chatHeading })).toBeInTheDocument();
  });
});

describe("private room: the two help buttons (M1-UI1)", () => {
  test("Ask North how others do it only fills the box: nothing is sent until the person sends it", async () => {
    mock({ room: emptyRoom() });
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: t.askNorth }));
    expect(screen.getByRole("textbox", { name: t.placeholder })).toHaveValue(t.askNorthText);
    expect(posts()).toHaveLength(0);
  });

  test("a message sent after Ask North asks for how others do it; a plain message does not", async () => {
    mock({ room: emptyRoom(), after: busyRoom() });
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: t.askNorth }));
    await user.type(screen.getByRole("textbox", { name: t.placeholder }), "{Enter}");
    expect(posts()[0]).toMatchObject({ body: { text: t.askNorthText, ask_how_others: true } });
    await user.type(screen.getByRole("textbox", { name: t.placeholder }), "Calls arrive late{Enter}");
    expect(posts()[1]?.body).not.toHaveProperty("ask_how_others");
  });

  test("Ask Nira how this works asks her, and says so plainly when she cannot answer", async () => {
    mock({ room: emptyRoom() });
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: t.askNira }));
    expect(await screen.findByText(t.askNiraFailed)).toBeInTheDocument(); // the stub has no Nira answer
  });
});

describe("private room: talking with North", () => {
  test("Enter sends a plain reply to North, not a note", async () => {
    mock({ room: emptyRoom(), after: busyRoom() });
    const user = userEvent.setup();
    open();
    await user.type(await screen.findByRole("textbox", { name: t.placeholder }), "Renewals slipped in April{Enter}");
    expect(posts()).toHaveLength(1);
    expect(posts()[0]).toMatchObject({ url: `${ROOM}/messages`, body: { text: "Renewals slipped in April", kind: "answer" } });
    expect(await screen.findByText("Who is affected?")).toBeInTheDocument();
  });

  test("Shift+Enter is a new line and sends nothing", async () => {
    mock({ room: emptyRoom() });
    const user = userEvent.setup();
    open();
    await user.type(await screen.findByRole("textbox", { name: t.placeholder }), "one{Shift>}{Enter}{/Shift}two");
    expect(posts()).toHaveLength(0);
    expect(screen.getByRole("textbox", { name: t.placeholder })).toHaveValue("one\ntwo");
  });

  test("making a note is an explicit action: posted as a note and the new conversation is shown", async () => {
    mock({ room: emptyRoom(), after: busyRoom() });
    const user = userEvent.setup();
    open();
    await user.type(await screen.findByRole("textbox", { name: t.placeholder }), "Renewals slipped in April");
    await user.click(screen.getByRole("button", { name: t.sendNote }));
    expect(posts()[0]).toMatchObject({ method: "POST", url: `${ROOM}/messages`, body: { text: "Renewals slipped in April", kind: "note" } });
    expect(await screen.findByText("Who is affected?")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: t.placeholder })).toHaveValue("");
  });

  test("the send button sends an answer, not a new note", async () => {
    mock({ room: busyRoom() });
    const user = userEvent.setup();
    open();
    await user.type(await screen.findByRole("textbox", { name: t.placeholder }), "Mostly the sales team");
    await user.click(screen.getByRole("button", { name: t.sendReply }));
    expect(posts()[0]?.body).toEqual({ text: "Mostly the sales team", kind: "answer" });
  });

  test("correcting a note: the note is named, the correction goes with its id", async () => {
    mock({ room: busyRoom() });
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: t.correct }));
    expect(screen.getByRole("status")).toHaveTextContent(t.correctingLabel);
    const box = screen.getByRole("textbox", { name: t.correctingField }); // the label says you are correcting
    expect(box).toHaveFocus(); // and focus moved to it
    await user.clear(box);
    await user.type(box, "It was in May");
    await user.click(screen.getByRole("button", { name: t.sendCorrection }));
    expect(posts()[0]?.body).toEqual({ text: "It was in May", kind: "correction", note_id: "n1" });
  });

  test("a refusal from the server is shown in plain words and the text stays", async () => {
    mock({ room: busyRoom(), postStatus: 409, postBody: { error: "rooms_closed", message: "The private rooms have closed, so new notes can no longer be added." } });
    const user = userEvent.setup();
    open();
    await user.type(await screen.findByRole("textbox", { name: t.placeholder }), "too late");
    await user.click(screen.getByRole("button", { name: t.sendNote }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The private rooms have closed");
    expect(screen.getByRole("textbox", { name: t.placeholder })).toHaveValue("too late");
  });

  test("when North did not answer the person is told their note is saved", async () => {
    mock({ room: busyRoom({ turns: [{ id: "t1", role: "person", text: "hi", at: "x" }, { id: "t2", role: "north", text: "", at: "x", answered: false }] }) });
    open();
    expect(await screen.findByText(t.noAnswer)).toBeInTheDocument();
  });

  test("North is not available is said once, not by the banner and the reply both", async () => {
    mock({ room: emptyRoom({ north: { ...NORTH, available: false }, turns: [
      { id: "t1", role: "person", text: "hi", at: "x" },
      { id: "t2", role: "north", text: "North is not available right now, but your note is saved. Please carry on.", at: "x", answered: false },
    ] }) });
    open();
    await screen.findByText(/but your note is saved/);
    expect(screen.getAllByText(/North is not available/)).toHaveLength(1);
  });

  test("when North is off a plain line says so and writing still works", async () => {
    mock({ room: emptyRoom({ north: { ...NORTH, available: false } }) });
    open();
    expect(await screen.findByText(t.northOff)).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: t.placeholder })).toBeEnabled();
  });
});

describe("private room: refused outside the rooms stage (M1-16)", () => {
  test("the plain message shows, there is no composer and no way to change a note, and reading still works", async () => {
    mock({ room: busyRoom({ open: false, message: "The private rooms have closed, so new notes can no longer be added." }) });
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent("The private rooms have closed");
    expect(screen.queryByRole("textbox", { name: t.placeholder })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.correct })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.practiceAdd })).not.toBeInTheDocument();
    expect(screen.getByText("Who is affected?")).toBeInTheDocument();
  });

  test("an empty closed room does not invite a first note", async () => {
    mock({ room: emptyRoom({ open: false, message: "The private rooms have closed, so new notes can no longer be added." }) });
    open();
    expect(await screen.findByText(t.emptyClosed)).toBeInTheDocument();
    expect(screen.queryByText(/Write your first note/)).not.toBeInTheDocument();
  });
});

describe("private room: industry practice card (M1-10)", () => {
  test("labelled as a suggestion, says the company decides, and Add is recorded", async () => {
    mock({ room: busyRoom() });
    const user = userEvent.setup();
    open();
    const group = await screen.findByRole("group", { name: "Industry practice (suggestion)" });
    expect(within(group).getByText("Your company decides.")).toBeInTheDocument();
    expect(within(group).getByText("Illustrative")).toBeInTheDocument(); // pack content carries the tag
    expect(within(group).getByText("Split the slip by region first")).toBeInTheDocument();
    await user.click(within(group).getByRole("button", { name: t.practiceAdd }));
    expect(posts()[0]).toMatchObject({ url: `${ROOM}/notes/n1/practice`, body: { action: "add" } });
  });

  test("Dismiss is recorded too", async () => {
    mock({ room: busyRoom() });
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: t.practiceDismiss }));
    expect(posts()[0]).toMatchObject({ url: `${ROOM}/notes/n1/practice`, body: { action: "dismiss" } });
  });

  test("an added card shows what was added; a dismissed one only says so; no card means no card", async () => {
    mock({ room: busyRoom({ notes: [
      note({ id: "n1", practice: { ...card, decision: "added" }, practice_added: ["Split the slip by region first"] }),
      note({ id: "n2", text: "Second note", practice: { ...card, decision: "dismissed" } }),
      note({ id: "n3", text: "Third note", practice: null }),
    ] }) });
    open();
    expect(await screen.findByText(t.practiceAdded)).toBeInTheDocument();
    expect(screen.getByText(t.practiceDismissed)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.practiceAdd })).not.toBeInTheDocument();
    expect(screen.getByText("Third note")).toBeInTheDocument();
    expect(within(screen.getByRole("listitem", { name: "Third note" })).queryByRole("group", { name: "Industry practice (suggestion)" })).not.toBeInTheDocument();
  });

  test("a priority can be set on a note", async () => {
    mock({ room: busyRoom() });
    const user = userEvent.setup();
    open();
    await user.selectOptions(await screen.findByRole("combobox", { name: t.priority }), "must");
    expect(posts()[0]).toMatchObject({ method: "POST", url: `${ROOM}/notes/n1`, body: { priority: "must" } });
  });
});

describe("private room: problem library (M1-13)", () => {
  test("when the organiser has not switched it on (the default) the panel is not shown at all: North listens and checks", async () => {
    mock({ room: emptyRoom(), library: { ...LIB, on: false, problems: [], message: OFF } });
    open();
    await screen.findByRole("region", { name: t.chatHeading });
    expect(screen.queryByRole("region", { name: t.libraryHeading })).not.toBeInTheDocument();
    expect(screen.queryByText(OFF)).not.toBeInTheDocument();
  });

  test("the heading says it is a suggestion and the pack content is tagged Illustrative", async () => {
    mock({ room: emptyRoom(), library: LIB });
    open();
    expect(await screen.findByRole("heading", { name: "Common problems (suggestion)" })).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: t.libraryHeading })).getByText("Illustrative")).toBeInTheDocument();
  });

  test("offered as a suggestion; nothing is added until the person adds; reword and priority go with it", async () => {
    mock({ room: emptyRoom(), library: LIB });
    const user = userEvent.setup();
    open();
    const panel = await screen.findByRole("region", { name: t.libraryHeading });
    expect(within(panel).getByText("Industry practice (suggestion)")).toBeInTheDocument();
    await user.click(within(panel).getByRole("button", { name: /Use this: Which suppliers deliver late/ }));
    expect(posts()).toHaveLength(0); // choosing is not adding
    const box = within(panel).getByRole("textbox", { name: t.libraryReword });
    expect(box).toHaveFocus(); // focus moved to the form...
    expect(box.closest("li")).toHaveTextContent("Which suppliers deliver late?"); // ...which opened next to its item
    await user.clear(box);
    await user.type(box, "Our suppliers are late");
    await user.selectOptions(within(panel).getByRole("combobox", { name: t.priority }), "should");
    await user.click(within(panel).getByRole("button", { name: t.libraryAdd }));
    expect(posts()[0]).toMatchObject({ url: `${ROOM}/notes`, body: { from_library: "P-2", text: "Our suppliers are late", priority: "should" } });
  });

  test("the empty company, with no pack at all: no library panel and no organiser message", async () => {
    mock({ room: emptyRoom(), library: { on: false, available: false, label: "Industry practice (suggestion)", problems: [], message: NO_LIB } });
    open();
    await screen.findByRole("region", { name: t.chatHeading });
    expect(screen.queryByRole("region", { name: t.libraryHeading })).not.toBeInTheDocument();
    expect(screen.queryByText(/organiser/)).not.toBeInTheDocument();
  });

  test("switched on but the pack has no library: the screen says so", async () => {
    mock({ room: emptyRoom(), library: { ...LIB, available: false, problems: [], message: NO_LIB } });
    open();
    expect(await screen.findByText(NO_LIB)).toBeInTheDocument();
  });

  test("cancel closes the form without adding", async () => {
    mock({ room: emptyRoom(), library: LIB });
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: /Use this: Where are renewals/ }));
    await user.click(screen.getByRole("button", { name: t.libraryCancel }));
    expect(screen.queryByRole("textbox", { name: t.libraryReword })).not.toBeInTheDocument();
    expect(posts()).toHaveLength(0);
  });
});
