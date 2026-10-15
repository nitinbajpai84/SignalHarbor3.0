import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, test, vi } from "vitest";

import WallScreen from "./WallScreen";
import { wallCopy as t } from "./copy";

// IC-2c: the wall. fetch is stubbed; nothing leaves the page. Synthetic text only.
const SID = "b".repeat(32);
const S = `/api/modules/m1_intent/sessions/${SID}`;
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const bn = (id: string, kind: string, text: string, extra: object = {}) => ({ id, kind, text, anonymous: false, mine: false, ...extra });
const board = (notes: object[], extra: object = {}) => ({
  stage: "private_rooms", paused_from: null, organiser: false, status: "none", can_edit: false, can_restore: false, edited: false,
  counts: { notes: notes.length, clusters: 0, on_its_own: notes.length }, clusters: [], on_its_own: notes, ...extra,
});
const ROOM = { open: true, message: null, title: "", turns: [], notes: [], form: [], north: { practice_on: false, library_on: false, available: true } };
const LIB = { on: false, available: true, label: "", problems: [], message: null };

const posts: { url: string; body: unknown }[] = [];
function mock(boardRes: () => Response | Promise<Response>, room: object = ROOM) {
  posts.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") { posts.push({ url, body: init.body ? JSON.parse(String(init.body)) : undefined }); return json(200, room); }
    if (url === `${S}/board`) return boardRes();
    if (url === `${S}/room`) return json(200, room);
    if (url.endsWith("/library")) return json(200, LIB);
    if (url.endsWith("/timer")) return json(200, { timed: false, stage: "private_rooms" });
    return json(404, {});
  }));
}
const open = () => render(<MemoryRouter initialEntries={[`/wall/${SID}`]}><Routes><Route path="/wall/:sessionId" element={<WallScreen />} /></Routes></MemoryRouter>);
const lane = (name: string) => screen.getByRole("region", { name });
const SAMPLE = [
  bn("1", "intent", "Renewal rate by region", { author_name: "Ann", quarters: 4, guessed: 1, mine: true }),
  bn("2", "intent", "Secret one", { anonymous: true, quarters: 2 }),
  bn("3", "pain_point", "Pay bands", { sealed: true, area: "pay", quarters: 1 }),
  bn("4", "future_signal", "Competitor pricing", { quarters: 0 }),
  bn("5", "lever", "Suggested lever", { suggestion: { from: "the annual plan" } }),
];

afterEach(() => { vi.unstubAllGlobals(); window.innerWidth = 1024; });

describe("wall screen states", () => {
  test("loading", () => {
    mock(() => new Promise<Response>(() => undefined));
    open();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });
  test("empty wall keeps the lanes and says so", async () => {
    mock(() => json(200, board([])));
    open();
    expect(await screen.findByText(t.empty)).toBeInTheDocument();
    expect(lane("TRACKING NOW")).toBeInTheDocument();
  });
  test("error", async () => {
    mock(() => json(500, {}));
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent(t.error);
  });
  test("refused", async () => {
    mock(() => json(403, { error: "module_not_available" }));
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent(t.refused);
  });
});

describe("populated wall", () => {
  test("counts, cards, names, sealed, suggestion and edge", async () => {
    mock(() => json(200, board(SAMPLE)));
    open();
    expect(await screen.findByText(t.cards(5))).toBeInTheDocument();
    expect(screen.getByText(t.crumbHere)).toBeInTheDocument();
    expect(screen.getByText(t.live)).toBeInTheDocument();
    expect(screen.getByTestId("count-intent")).toHaveTextContent("2");
    expect(screen.getByTestId("count-pain_point")).toHaveTextContent("1");
    expect(screen.getByTestId("count-future_signal")).toHaveTextContent("1");
    expect(screen.getByTestId("count-lever")).toHaveTextContent("1");
    const tracking = lane("TRACKING NOW");
    const foot = within(tracking).getByText(/4 \/ 4/).closest("small")!; // the foot shows the author's initial, never the name
    expect(foot).toHaveTextContent(/^A/);
    expect(foot).not.toHaveTextContent("Ann");
    expect(foot).toHaveTextContent("· 1 guessed");
    expect(within(tracking).getByText(/Anonymous/)).toHaveTextContent("2 / 4");
    expect(within(tracking).getAllByTestId("edge").map((e) => e.getAttribute("data-filled"))).toEqual(["4", "2"]);
    expect(screen.getByText("A sealed card about pay")).toBeInTheDocument();
    expect(screen.queryByText("Pay bands")).toBeNull();
    expect(screen.getByText("Suggested by North · from the annual plan")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: t.pickUp })).toBeInTheDocument();
  });

  test("a restricted note renders as sealed; no quarters served hides the n / 4", async () => {
    mock(() => json(200, board([bn("9", "intent", "Hidden words", { restricted: true }), bn("8", "intent", "Plain card")])));
    open();
    expect(await screen.findByText(/A sealed card about/)).toBeInTheDocument();
    expect(screen.queryByText("Hidden words")).toBeNull();
    expect(within(lane("TRACKING NOW")).getByText("Anonymous")).not.toHaveTextContent("/ 4");
  });

  test("more than six cards shows + n more", async () => {
    mock(() => json(200, board(Array.from({ length: 8 }, (_, i) => bn(`m${i}`, "lever", `Lever ${i}`)))));
    open();
    expect(await screen.findByText("+ 2 more")).toBeInTheDocument();
    expect(screen.getByTestId("count-lever")).toHaveTextContent("8");
  });

  test("show only mine", async () => {
    mock(() => json(200, board(SAMPLE)));
    open();
    await screen.findByText(t.cards(5));
    await userEvent.click(screen.getByRole("button", { name: t.onlyMine }));
    expect(screen.getByText("Renewal rate by region")).toBeInTheDocument();
    expect(screen.queryByText("Competitor pricing")).toBeNull();
  });

  test("projector view: lanes and counts only, no text, names or panel", async () => {
    mock(() => json(200, board(SAMPLE)));
    open();
    await screen.findByText(t.cards(5));
    await userEvent.click(screen.getByRole("button", { name: t.projector }));
    expect(screen.getByTestId("count-intent")).toHaveTextContent("2");
    for (const x of ["Renewal rate by region", "Ann", "Anonymous", "A sealed card about pay", "Suggested by North"]) {
      expect(screen.queryByText(new RegExp(x))).toBeNull();
    }
    expect(screen.queryByRole("complementary")).toBeNull();
    expect(screen.queryByLabelText(t.sealBox)).toBeNull();
  });

  test("phone width shows one lane at a time with a switcher", async () => {
    window.innerWidth = 400;
    mock(() => json(200, board(SAMPLE)));
    open();
    await screen.findByText(t.cards(5));
    expect(screen.queryByRole("region", { name: "MISSING" })).toBeNull();
    await userEvent.click(screen.getByRole("tab", { name: "MISSING" }));
    expect(lane("MISSING")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "TRACKING NOW" })).toBeNull();
  });

  test("before the board opens the wall shows the viewer's own cards", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === `${S}/board`) return json(409, { message: "The board is not open yet." });
      if (url === `${S}/room`) return json(200, { ...ROOM, notes: [{ id: "n1", text: "My own card", kind: "lever", anonymous: true, confirmed: true }] });
      if (url.endsWith("/library")) return json(200, LIB);
      return json(200, { timed: false, stage: "private_rooms" });
    }));
    open();
    expect(await screen.findByText("My own card")).toBeInTheDocument();
    expect(screen.getByTestId("count-lever")).toHaveTextContent("1");
  });

  test("a closed wall shows named authors' initials and no North panel to answer", async () => {
    mock(() => json(200, board(SAMPLE, { stage: "closed" })));
    open();
    await screen.findByText(t.cards(5));
    expect(within(screen.getByTestId("participants")).getByText("A")).toBeInTheDocument(); // Ann; the anonymous author gives none
    expect(screen.queryByRole("complementary", { name: t.panelTitle })).toBeNull();
    expect(screen.queryByText(t.live)).toBeNull();
  });

  test("the viewer's own named card in the room says You and fills its edge from the answers given", async () => {
    const quarters = { q1: { text: "a", mark: "stated" }, q2: { text: "b", mark: "stated" }, q3: { text: "c", mark: "stated" }, q4: { text: "", mark: "unknown" } };
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === `${S}/board`) return json(409, { message: "The board is not open yet." });
      if (url === `${S}/room`) return json(200, { ...ROOM, notes: [{ id: "n1", text: "Named card", kind: "intent", anonymous: false, confirmed: null, quarters }] });
      if (url.endsWith("/library")) return json(200, LIB);
      return json(200, { timed: false, stage: "private_rooms" });
    }));
    open();
    const tracking = await screen.findByRole("region", { name: "TRACKING NOW" });
    await within(tracking).findByText("Named card");
    expect(within(tracking).getByText(t.you)).toBeInTheDocument();
    expect(within(tracking).queryByText(t.anonymous)).toBeNull();
    expect(within(tracking).getByTestId("edge")).toHaveAttribute("data-filled", "3");
  });

  test("a sealed card sent with quarters, text and author shows only the silhouette", async () => {
    mock(() => json(200, board([bn("s", "pain_point", "Bonus list", { sealed: true, area: "pay", quarters: 3, guessed: 2, author_name: "Zed", suggestion: { from: "a file" } })])));
    open();
    await screen.findByText(t.cards(1));
    const missing = lane("MISSING");
    expect(within(missing).getByText("A sealed card about pay")).toBeInTheDocument();
    expect(within(missing).queryByTestId("edge")).toBeNull();
    for (const x of ["Bonus list", "Zed", "/ 4", "guessed", "a file"]) expect(within(missing).queryByText(new RegExp(x))).toBeNull();
  });

  test("edge fills 1 and 3 quarters", async () => {
    mock(() => json(200, board([bn("a", "intent", "One", { quarters: 1 }), bn("b", "intent", "Three", { quarters: 3 })])));
    open();
    await screen.findByText(t.cards(2));
    expect(within(lane("TRACKING NOW")).getAllByTestId("edge").map((e) => e.getAttribute("data-filled"))).toEqual(["1", "3"]);
  });

  test("projector view clears show only mine", async () => {
    mock(() => json(200, board(SAMPLE)));
    open();
    await screen.findByText(t.cards(5));
    await userEvent.click(screen.getByRole("button", { name: t.onlyMine }));
    await userEvent.click(screen.getByRole("button", { name: t.projector }));
    await userEvent.click(screen.getByRole("button", { name: t.exitProjector }));
    expect(screen.getByText("Competitor pricing")).toBeInTheDocument();
  });

  test("pick up suggestion: click calls the route, card appears, suggestion disappears", async () => {
    let boardCallCount = 0;
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === `${S}/board`) {
        // First call returns initial board with suggestion, subsequent calls return board without suggestion but with new card
        if (boardCallCount === 0) {
          boardCallCount++;
          return json(200, board(SAMPLE));
        }
        // After picking up, return board with the card no longer marked as a suggestion
        return json(200, board([
          bn("1", "intent", "Renewal rate by region", { author_name: "Ann", quarters: 4, guessed: 1, mine: true }),
          bn("2", "intent", "Secret one", { anonymous: true, quarters: 2 }),
          bn("3", "pain_point", "Pay bands", { sealed: true, area: "pay", quarters: 1 }),
          bn("4", "future_signal", "Competitor pricing", { quarters: 0 }),
          bn("5", "lever", "Suggested lever", { mine: true, quarters: null }),
        ]));
      }
      if (url === `${S}/room`) return json(200, ROOM);
      if (url.endsWith("/library")) return json(200, LIB);
      if (url.endsWith("/timer")) return json(200, { timed: false, stage: "private_rooms" });
      if (url === `${S}/room/notes`) {
        return json(200, ROOM);
      }
      return json(404, {});
    }));
    open();
    await screen.findByText(t.cards(5));
    // Verify the suggestion is shown
    expect(screen.getByText("Suggested by North · from the annual plan")).toBeInTheDocument();
    const pickUpBtn = screen.getByRole("button", { name: t.pickUp });
    expect(pickUpBtn).toBeEnabled();
    // Click "Pick it up"
    await userEvent.click(pickUpBtn);
    // Wait for the card to appear (which happens when the board reloads)
    await screen.findByText("Suggested lever");
    // Suggestion label should disappear
    expect(screen.queryByText("Suggested by North · from the annual plan")).toBeNull();
    // Button should be gone since the card is no longer a suggestion
    expect(screen.queryByRole("button", { name: t.pickUp })).toBeNull();
  });

  test("pick up suggestion: error shows message and re-enables button", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === `${S}/board`) return json(200, board(SAMPLE));
      if (url === `${S}/room`) return json(200, ROOM);
      if (url.endsWith("/library")) return json(200, LIB);
      if (url.endsWith("/timer")) return json(200, { timed: false, stage: "private_rooms" });
      if (url === `${S}/room/notes`) return json(500, {});
      return json(404, {});
    }));
    open();
    await screen.findByText(t.cards(5));
    const pickUpBtn = screen.getByRole("button", { name: t.pickUp });
    await userEvent.click(pickUpBtn);
    // Wait for error message to appear
    await screen.findByText(t.pickUpError);
    // Button should be re-enabled after error
    expect(pickUpBtn).toBeEnabled();
    expect(pickUpBtn).toHaveTextContent(t.pickUp);
  });
});

describe("the seal", () => {
  const NOTE = { id: "n1", text: "Pay for finance is not tracked", state: "draft", source: { kind: "typed" }, priority: null, practice: null, practice_added: [],
    created_at: "x", updated_at: "x", fields: {}, labels_suggested: [], anonymous: false, missing: [] };
  const withNote = (extra: object = {}) => ({ ...ROOM, notes: [{ ...NOTE, ...extra }] });

  test("ticking the seal box saves restricted: true through the note route", async () => {
    mock(() => json(200, board([])), withNote());
    open();
    await userEvent.click(await screen.findByLabelText(t.sealBox));
    expect(posts.filter((p) => p.url.includes("/room/notes/"))).toEqual([{ url: `${S}/room/notes/n1`, body: { restricted: true } }]);
  });

  test("the author's own sealed note has its seal box ticked", async () => {
    mock(() => json(200, board([])), withNote({ restricted: true }));
    open();
    expect(await screen.findByLabelText(t.sealBox)).toBeChecked();
  });
});

describe("North's panel", () => {
  const cell = (text: string, mark = "stated") => ({ text, mark, from: text ? "you" : null });
  const quarters = (n: number) => Object.fromEntries(["q1", "q2", "q3", "q4"].map((q, i) => [q, i < n ? cell(`answer ${i + 1}`) : cell("", "unknown")]));
  const NOTE = { id: "n1", text: "x", state: "draft", source: { kind: "typed" }, priority: null, practice: null, practice_added: [],
    created_at: "x", updated_at: "x", fields: {}, labels_suggested: [], anonymous: false, missing: [] };
  const roomWith = (n: number, extra: object = {}) => ({
    ...ROOM, wall_questions: [{ id: "q1", lead: "What do you track?" }, { id: "q2", lead: "Who uses it?" }, { id: "q3", lead: "How often?" }, { id: "q4", lead: "Where is it kept?" }],
    notes: [{ ...NOTE, quarters: quarters(n), quarter_drafts: {}, ...extra }],
  });
  const noteCalls = () => posts.filter((p) => p.url.includes("/room/notes/"));

  test("the four bars reflect the quarters answered", async () => {
    mock(() => json(200, board([])), roomWith(3));
    open();
    expect(await screen.findByText(t.yourCard(3))).toBeInTheDocument();
    expect(screen.getAllByTestId("bar").map((b) => b.getAttribute("data-filled"))).toEqual(["true", "true", "true", "false"]);
  });

  test("below two answered the wall button is off and a plain line says why", async () => {
    mock(() => json(200, board([])), roomWith(1));
    open();
    expect(await screen.findByRole("button", { name: t.putOnWall })).toBeDisabled();
    expect(screen.getByText(t.needTwo)).toBeInTheDocument();
  });

  test("with two answered, Put it on the wall now calls submit", async () => {
    mock(() => json(200, board([])), roomWith(2));
    open();
    await userEvent.click(await screen.findByRole("button", { name: t.putOnWall }));
    expect(noteCalls()).toEqual([{ url: `${S}/room/notes/n1/submit`, body: undefined }]);
  });

  test("Yes, still right keeps the draft and shows where it was read from", async () => {
    mock(() => json(200, board([])), roomWith(1, { quarter_drafts: { q2: { text: "Finance, monthly", from: "Reporting guide" } } }));
    open();
    expect(await screen.findByText(t.readFrom("Reporting guide"))).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: t.stillRight }));
    expect(noteCalls()).toEqual([{ url: `${S}/room/notes/n1`, body: { quarters: { q2: { keep: true } } } }]);
  });

  test("Answer saves what was typed against the open question", async () => {
    mock(() => json(200, board([])), roomWith(1));
    open();
    await userEvent.type(await screen.findByLabelText(t.yourAnswer), "Weekly");
    await userEvent.click(screen.getByRole("button", { name: t.answer }));
    expect(noteCalls()).toEqual([{ url: `${S}/room/notes/n1`, body: { quarters: { q2: { text: "Weekly" } } } }]);
  });

  test("the Anonymous box saves with the note", async () => {
    mock(() => json(200, board([])), roomWith(2));
    open();
    await userEvent.click(await screen.findByLabelText(t.anonymous));
    expect(noteCalls()).toEqual([{ url: `${S}/room/notes/n1`, body: { anonymous: true } }]);
  });

  test("no legacy crumbs or header inside the wall", async () => {
    mock(() => json(200, board([])), roomWith(1));
    open();
    await screen.findByText(t.yourCard(1));
    expect(screen.queryByText("Modules")).toBeNull();
    expect(screen.queryByText("Intent Centre")).toBeNull();
    expect(screen.queryByRole("navigation")).toBeNull();
  });

  test("on a phone North is a sheet behind a Talk to North button", async () => {
    window.innerWidth = 400;
    mock(() => json(200, board([])), roomWith(1));
    open();
    await userEvent.click(await screen.findByRole("button", { name: t.talkToNorth }));
    expect(await screen.findByText(t.yourCard(1))).toBeInTheDocument();
  });
});

describe("layout, purpose and participants", () => {
  const withSession = (prep: object, label = "Q3 review") => (url: string) =>
    url === S ? json(200, { label, preparation: prep }) : null;
  const mockWith = (extra: object, sess: (url: string) => Response | null) => {
    mock(() => json(200, board(SAMPLE, extra)));
    const base = globalThis.fetch as unknown as (u: string, i?: RequestInit) => Promise<Response>;
    vi.stubGlobal("fetch", vi.fn(async (u: string, i?: RequestInit) => sess(u) ?? base(u, i)));
  };

  test("four lanes in a grid next to the North panel", async () => {
    mock(() => json(200, board(SAMPLE)));
    open();
    await screen.findByText(t.cards(5));
    expect(within(screen.getByTestId("lanes")).getAllByRole("region")).toHaveLength(4);
    expect(screen.getByTestId("lanes")).toHaveClass("ds-wall__lanes");
    expect(screen.getByRole("complementary")).toBeInTheDocument();
  });

  test("purpose line and topic chip when served", async () => {
    mockWith({}, withSession({ purpose: "Plan the year", topic: "Finance" }));
    open();
    expect(await screen.findByText("Plan the year")).toBeInTheDocument();
    expect(screen.getByTestId("topic")).toHaveTextContent("Finance");
    expect(screen.getByText(t.purposeLead)).toBeInTheDocument();
  });

  test("no topic: no chip; no purpose: the label is used", async () => {
    mockWith({}, withSession({}, "Q3 review"));
    open();
    expect(await screen.findByText("Q3 review")).toBeInTheDocument();
    expect(screen.queryByTestId("topic")).toBeNull();
  });

  test("participants: count, named initials only, hidden initials in projector", async () => {
    mockWith({ people: 12, people_total: 14 }, () => null);
    open();
    const p = await screen.findByTestId("participants");
    expect(p).toHaveTextContent("12 / 14 people");
    expect(p).toHaveTextContent(/^A12/);
    await userEvent.click(screen.getByRole("button", { name: t.projector }));
    expect(screen.getByTestId("participants")).toHaveTextContent(/^12 \/ 14/);
  });

  test("North panel leads with the question and the quarter bars", async () => {
    const note = { id: "n1", text: "x", state: "draft", quarters: { q1: { text: "", mark: "unknown", from: null }, q2: { text: "", mark: "unknown", from: null }, q3: { text: "", mark: "unknown", from: null }, q4: { text: "", mark: "unknown", from: null } } };
    mock(() => json(200, board([])), { ...ROOM, notes: [note], wall_questions: [{ id: "q1", lead: "What do you track?" }] });
    open();
    const q = await screen.findByTestId("north-question");
    expect(q).toHaveTextContent("What do you track?");
    expect(screen.getAllByTestId("bar")).toHaveLength(4);
  });
});

describe("organiser and phone", () => {
  const LOBBY = {
    session_id: SID, state: "private_rooms", length_minutes: 30, is_solo: false, organiser: true, me: null, arrived: 1, seat_count: 2,
    seats: [{ n: 1, state: "taken", mine: false, name: "Ann", role: "Lead" }, { n: 2, state: "free", mine: false }],
  };
  function mockOrganiser() {
    posts.length = 0;
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST") { posts.push({ url, body: undefined }); return json(200, { state: "board" }); }
      if (url === `${S}/board`) return json(200, board(SAMPLE, { closes_at: "2026-10-09T17:00:00" }));
      if (url === `${S}/lobby`) return json(200, LOBBY);
      if (url === `${S}/join-link`) return json(200, { join_path: "/join/abc", state: "private_rooms" });
      if (url === `${S}/room`) return json(200, ROOM);
      if (url.endsWith("/library")) return json(200, LIB);
      return json(404, {});
    }));
    vi.stubGlobal("location", { ...window.location, reload: vi.fn() });
  }

  test("stage bar: stages behind and the current one lit, the next step asks first", async () => {
    mockOrganiser();
    open();
    const bar = await screen.findByRole("navigation", { name: t.stagesLabel });
    expect(within(bar).getByText("Private rooms")).toHaveAttribute("aria-current", "step");
    expect(within(bar).getByText("Private rooms")).toHaveClass("ds-stagebar__stage--now");
    expect(within(bar).getByText("Briefing")).toHaveClass("ds-stagebar__stage--done");
    expect(within(bar).getByText("Together")).not.toHaveClass("ds-stagebar__stage--done");
    // the closing line comes from the board, which the server serves only once the rooms close; the wall no longer asks for it before (F50)
    await userEvent.click(within(bar).getByRole("button", { name: "Close the rooms and bring everyone to the wall" }));
    expect(posts).toHaveLength(0);
    expect(within(bar).getByRole("alertdialog", { name: t.sure })).toBeInTheDocument();
    await userEvent.click(within(bar).getByRole("button", { name: t.yes }));
    expect(posts.map((p) => p.url)).toEqual([`${S}/rooms/close`]);
  });

  test("invite panel: one line, then the link, new link and the seats", async () => {
    mockOrganiser();
    open();
    const invite = await screen.findByRole("region", { name: t.inviteLabel });
    const line = within(invite).getByRole("button", { name: t.inviteLine(2, 1) });
    expect(line).toHaveAttribute("aria-expanded", "false");
    expect(within(invite).getAllByRole("button")).toHaveLength(1);
    expect(within(invite).queryByLabelText(t.joinLink)).toBeNull();
    await userEvent.click(line);
    expect(within(invite).getByLabelText(t.joinLink)).toHaveValue(`${window.location.origin}/join/abc`);
    expect(within(invite).getByRole("button", { name: t.newLink })).toBeInTheDocument();
    expect(within(invite).getByRole("button", { name: t.revokeSeat(1) })).toBeInTheDocument();
  });

  test("phone: the switcher marks the chosen lane, and North opens as a sheet", async () => {
    window.innerWidth = 400;
    mock(() => json(200, board(SAMPLE)));
    open();
    await screen.findByText(t.cards(5));
    const tabs = screen.getByRole("tablist", { name: t.laneSwitcher });
    expect(within(tabs).getAllByRole("tab")).toHaveLength(4);
    expect(within(tabs).getByRole("tab", { name: "TRACKING NOW" })).toHaveAttribute("aria-selected", "true");
    await userEvent.click(within(tabs).getByRole("tab", { name: "WATCH" }));
    expect(within(tabs).getByRole("tab", { name: "WATCH" })).toHaveAttribute("aria-selected", "true");
    expect(within(tabs).getByRole("tab", { name: "TRACKING NOW" })).toHaveAttribute("aria-selected", "false");
    expect(within(lane("WATCH")).getByText("Competitor pricing")).toBeInTheDocument();
    expect(screen.queryByRole("complementary")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: t.talkToNorth }));
    expect(screen.getByRole("complementary", { name: t.panelTitle })).toHaveClass("ds-wall__sheet");
  });

  test("while the rooms are open the organiser sees how many cards are in, never their words", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === `${S}/board`) return json(409, { message: "The board appears when the private rooms close." });
      if (url === `${S}/board/counts`) return json(200, { stage: "private_rooms", submitted: 9, drafts: 2, people_with_drafts: 1 });
      if (url === `${S}/lobby`) return json(200, LOBBY);
      if (url === `${S}/room`) return json(200, ROOM);
      return json(404, {});
    }));
    open();
    expect(await screen.findByText(t.cards(9))).toBeInTheDocument();
    expect(screen.getByText(t.inRooms(9))).toBeInTheDocument();
    expect(screen.queryByText(t.empty)).toBeNull();
  });
});

describe("a seat holder while the rooms are open", () => {
  const quarters = { q1: { text: "a", mark: "stated" }, q2: { text: "b", mark: "stated" }, q3: { text: "c", mark: "stated" }, q4: { text: "", mark: "unknown" } };
  const draft = { id: "d1", text: "North's draft lever", kind: "lever", anonymous: false, confirmed: false, state: "draft", quarters, quarter_drafts: { q4: { text: "Per fund", from: "the workbook" } } };
  const roomWith = { ...ROOM, notes: [draft], wall: { others: { pain_point: 2, lever: 1 }, writers: ["Katie Menon", "Samuel Ong"] } };
  function stub(room: object = roomWith) {
    posts.length = 0;
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST") { posts.push({ url, body: init.body ? JSON.parse(String(init.body)) : undefined }); return json(200, room); }
      if (url === `${S}/board`) return json(409, { message: "The board appears when the private rooms close." });
      if (url === `${S}/room`) return json(200, room);
      if (url.endsWith("/library")) return json(200, LIB);
      return json(404, {});
    }));
  }

  test("sees silhouettes for other people's cards, the named writers' initials and their own draft marked", async () => {
    stub();
    open();
    const levers = await screen.findByRole("region", { name: "LEVERS" });
    await within(levers).findByText("North's draft lever");
    expect(within(levers).getByText(/Draft, only you see it/)).toBeInTheDocument();
    expect(screen.getByTestId("count-lever")).toHaveTextContent("2");
    expect(screen.getByTestId("count-pain_point")).toHaveTextContent("2");
    expect(within(lane("MISSING")).getAllByText("Someone's card")).toHaveLength(2);
    const who = screen.getByTestId("participants");
    expect(within(who).getByText("K")).toBeInTheDocument();
    expect(within(who).getByText("S")).toBeInTheDocument();
    expect(screen.getByText(t.cards(3))).toBeInTheDocument(); // the draft is not on the wall yet
  });

  test("Tell North something new sends the answer to North instead of the open draft", async () => {
    stub();
    open();
    const north = await screen.findByRole("complementary", { name: t.panelTitle });
    await userEvent.click(await within(north).findByRole("button", { name: "Tell North something new" }));
    await userEvent.type(within(north).getByRole("textbox"), "Managers pick their own benchmark");
    await userEvent.click(within(north).getByRole("button", { name: t.answer }));
    expect(posts.some((p) => p.url.endsWith("/room/messages") && (p.body as { kind: string }).kind === "answer")).toBe(true);
    expect(posts.some((p) => p.url.includes("/room/notes/d1"))).toBe(false);
  });
});

describe("inside an intent", () => {
  const inIntent = (quarters: Record<string, number> | null) => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === `${S}/board`) return json(200, board([bn("1", "intent", "Late cash", { author_name: "Ann", quarters: 4 })]));
      if (url === "/api/intents/i1/wall") return json(200, { quarters });
      if (url === `${S}/room`) return json(200, ROOM);
      return json(404, {});
    }));
    render(<MemoryRouter initialEntries={[`/wall/${SID}`]}><Routes><Route path="/wall/:sessionId" element={<WallScreen intentId="i1" />} /></Routes></MemoryRouter>);
  };
  test("the n / 4 shows only when the intent read serves it, and no initials chip sits beside the card count", async () => {
    inIntent({ "1": 4 });
    expect(await screen.findByText(/4 \/ 4/)).toBeInTheDocument();
    expect(screen.queryByTestId("participants")).toBeNull();
  });
  test("an observer gets no n / 4 even if the board carries a count", async () => {
    inIntent(null);
    await screen.findByText("Late cash");
    expect(screen.queryByText(/\/ 4/)).toBeNull();
  });
});
