import { render, screen, within, configure } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import App from "../../../App";
import { setSessionExpiredHandler } from "../../../api/client";
import { m1Board, m1PrivateRoom as t } from "../copy";
import type { Room, RoomNote } from "./roomApi";

// These tests render the whole App; on a loaded machine the 1s default for findBy*/waitFor is too short.
configure({ asyncUtilTimeout: 5000 });

// M1-UI2: the studio transcript keeps every turn with its time; "I'm done" and "Close the rooms now" end the private room early.

const SID = "a".repeat(32);
const BASE = `/api/modules/m1_intent/sessions/${SID}`;
const note = (id: string, text: string, state = "draft"): RoomNote => ({
  id, text, state, source: { kind: "typed" }, priority: null, practice: null, practice_added: [],
  created_at: "2026-10-03T10:00:00+00:00", updated_at: "2026-10-03T10:00:00+00:00", fields: {}, labels_suggested: [],
  anonymous: false, missing: [],
});
const room: Room = {
  open: true, message: null, title: "", form: [], north: { practice_on: false, library_on: false, available: true },
  turns: [
    { id: "t1", role: "person", text: "Our family office tracks fees by hand", at: "2026-10-03T09:05:00+00:00" },
    { id: "t2", role: "north", text: "Which fees take the most time?", at: "2026-10-03T09:06:00+00:00", answered: true },
    { id: "t3", role: "person", text: "Custody fees, every quarter", at: "2026-10-03T09:07:00+00:00" },
  ],
  notes: [note("n1", "Fees are tracked by hand"), note("n2", "Custody fees are late"), note("n3", "Already in", "submitted")],
};
const calls: { method: string; url: string }[] = [];
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function mock(organiser: boolean) {
  calls.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ method, url });
    if (url === "/api/auth/me") return json(200, { display_name: "Ann", company_id: "co-a", roles: ["company_admin"] });
    if (url === "/api/company") return json(200, { company_id: "co-a", name: "Harbor Test Co", industry: "none" });
    if (url === "/api/modules") return json(200, [{ id: "m1_intent", number: 1, name: "Intent", description: "d", agent: "North" }]);
    if (url === `${BASE}/room`) return json(200, room);
    if (url === `${BASE}/room/library`) return json(200, { on: false, available: false, label: "", problems: [], message: "x" });
    if (url === `${BASE}/lobby`) return json(200, { session_id: SID, state: "private_rooms", organiser, seats: [], arrived: 1, seat_count: 1, length_minutes: 20, is_solo: false, me: null });
    if (url === `${BASE}/timer`) return json(200, { timed: false, stage: "private_rooms" });
    if (url.startsWith(`${BASE}/room/notes/`) && url.endsWith("/submit")) return json(200, room);
    if (url === `${BASE}/rooms/close`) return json(200, { state: "board" });
    if (url === `${BASE}/room/done`) return json(200, { state: "private_rooms", i_done: true });
    return json(404, {});
  }));
}
const open = () => render(<MemoryRouter initialEntries={[`/modules/m1_intent/sessions/${SID}/room`]}><App /></MemoryRouter>);
const submits = () => calls.filter((c) => c.method === "POST" && c.url.endsWith("/submit")).map((c) => c.url.split("/").at(-2));

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  sessionStorage.clear();
  localStorage.clear();
  setSessionExpiredHandler(null);
});

describe("the interview transcript", () => {
  test("is headed as North's, keeps every turn and gives each its speaker and time", async () => {
    mock(false);
    open();
    const panel = await screen.findByRole("region", { name: t.chatHeading });
    expect(within(panel).getByText(t.chatEyebrow)).toBeInTheDocument();
    const turns = within(panel).getAllByRole("listitem");
    expect(turns).toHaveLength(3);
    expect(turns[0]).toHaveTextContent(`${t.you}`);
    expect(turns[0]).toHaveTextContent("Our family office tracks fees by hand");
    expect(turns[1]).toHaveTextContent(t.north);
    expect(turns[2]).toHaveTextContent("Custody fees, every quarter");
    expect(turns[0]?.querySelector(".when")?.textContent).toMatch(/^\d\d:\d\d$/);
  });
});

describe("ending the private room early", () => {
  test("I'm done asks once, then submits only this person's drafts and shows the waiting state", async () => {
    mock(false);
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: t.done }));
    expect(screen.getByRole("alertdialog", { name: t.doneSure })).toBeInTheDocument();
    expect(submits()).toEqual([]); // nothing is sent before the person says yes
    await user.click(screen.getByRole("button", { name: t.doneYes }));
    expect(await screen.findByText(t.waiting)).toBeInTheDocument();
    expect(submits()).toEqual(["n1", "n2"]); // the note that was already submitted is left alone
    expect(calls.filter((c) => c.method === "POST" && c.url === `${BASE}/room/done`)).toHaveLength(1); // the server learns this person is done
  });

  test("the organiser's I'm done does not call the participants' done route", async () => {
    mock(true);
    const user = userEvent.setup();
    open();
    await vi.waitFor(() => expect(calls.some((c) => c.url === `${BASE}/lobby`)).toBe(true));
    await user.click(await screen.findByRole("button", { name: t.done }));
    await user.click(screen.getByRole("button", { name: t.doneYes }));
    expect(await screen.findByText(t.waiting)).toBeInTheDocument();
    expect(calls.some((c) => c.url === `${BASE}/room/done`)).toBe(false);
  });

  test("keep writing leaves everything as it was", async () => {
    mock(false);
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: t.done }));
    await user.click(screen.getByRole("button", { name: t.doneNo }));
    expect(submits()).toEqual([]);
    expect(screen.getByRole("button", { name: t.done })).toBeInTheDocument();
  });

  test("Close the rooms now is the organiser's only, asks first, then calls rooms/close", async () => {
    mock(true);
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: m1Board.close }));
    expect(screen.getByRole("alertdialog", { name: m1Board.closeSure })).toBeInTheDocument();
    expect(calls.some((c) => c.url.endsWith("/rooms/close"))).toBe(false);
    await user.click(screen.getByRole("button", { name: m1Board.closeYes }));
    await vi.waitFor(() => expect(calls.some((c) => c.method === "POST" && c.url === `${BASE}/rooms/close`)).toBe(true));
    expect(screen.queryByText(t.waiting)).not.toBeInTheDocument(); // the organiser goes straight on to the board
  });

  test("a participant has no Close the rooms now", async () => {
    mock(false);
    open();
    await screen.findByRole("button", { name: t.done });
    await vi.waitFor(() => expect(calls.some((c) => c.url === `${BASE}/lobby`)).toBe(true)); // it asked who this person is
    expect(screen.queryByRole("button", { name: m1Board.close })).not.toBeInTheDocument();
  });
});
