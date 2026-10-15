import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { copy } from "../../../copy";
import type { BoardCluster, BoardNote, BoardView } from "../api";
import { m1Board as t } from "../copy";
import BoardScreen from "./BoardScreen";

// M1-17 to M1-19 screens: the counts while the rooms are open, the board after, North's grouping, the organiser's edits.
// Family-office example wording only.

const SID = "b".repeat(32);
const BASE = `/api/modules/m1_intent/sessions/${SID}`;
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const note = (id: string, text: string, over: Partial<BoardNote> = {}): BoardNote => ({ id, text, anonymous: false, mine: false, ...over });
const cluster = (id: string, name: string, notes: BoardNote[], colour: number = 0): BoardCluster => ({
  id, name, source: "north", reasoning: "The notes are about the same problem", note_ids: notes.map((n) => n.id), notes, colour,
});
const LATE = cluster("c1", "Calls arrive too late", [
  note("n1", "Capital calls reach us too late", { author_name: "Ada" }),
  note("n2", "We learn of calls by email", { anonymous: true }),
], 0);
const EXPO = cluster("c2", "No single exposure view", [note("n3", "Exposure by name takes a week", { author_name: "Ben" }), note("n4", "Private funds are not in it", { anonymous: true })], 1);
const FEES = note("n5", "Fee reports differ by manager", { author_name: "Ada" });
const board = (over: Partial<BoardView> = {}): BoardView => ({
  stage: "board", paused_from: null, organiser: true, status: "done", can_edit: true, can_restore: true, edited: false,
  counts: { notes: 5, clusters: 2, on_its_own: 1 }, clusters: [LATE, EXPO], on_its_own: [FEES], ...over,
});
const calls: { method: string; url: string; body: unknown }[] = [];

interface World {
  board?: () => Response | Promise<Response>;
  counts?: () => Response;
  after?: (url: string) => Response | undefined;
}
function serve(w: World) {
  calls.length = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
      if (url === `${BASE}/board` && method === "GET") return (w.board ?? (() => json(200, board())))();
      if (url === `${BASE}/board/counts`) return (w.counts ?? (() => json(404, { error: "not_found", message: "no" })))();
      if (url === `${BASE}/timer`) return json(200, { stage: "private_rooms", timed: false, now: "z" });
      return w.after?.(url) ?? json(404, {});
    }),
  );
}
const open = () =>
  render(
    <MemoryRouter initialEntries={[`/s/${SID}`]}>
      <Routes>
        <Route path="/s/:sessionId" element={<BoardScreen />} />
      </Routes>
    </MemoryRouter>,
  );
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

// ---- five states
test("loading, then the board", async () => {
  serve({ board: () => new Promise<Response>(() => undefined) });
  open();
  expect(screen.getByRole("status")).toHaveTextContent("Loading");
});

test("an error says what happened and offers to try again", async () => {
  serve({ board: () => json(500, { error: "x" }) });
  open();
  expect(await screen.findByRole("alert")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
});

test("a refusal is shown in plain words", async () => {
  serve({ board: () => json(403, { error: "forbidden", message: "no" }) });
  open();
  expect(await screen.findByRole("alert")).toHaveTextContent(copy.states.refused);
});

test("an empty board says nobody submitted a note", async () => {
  serve({ board: () => json(200, board({ counts: { notes: 0, clusters: 0, on_its_own: 0 }, clusters: [], on_its_own: [] })) });
  open();
  expect(await screen.findByText(t.empty)).toBeInTheDocument();
  expect(screen.queryByRole("group", { name: t.viewSwitch })).not.toBeInTheDocument();
});

// ---- while the rooms are open
test("while the rooms are open the organiser sees counts, never the notes, and can close the rooms after confirming", async () => {
  const user = userEvent.setup();
  serve({
    board: () => json(409, { error: "wrong_state", message: "The board appears when the private rooms close." }),
    counts: () => json(200, { stage: "private_rooms", submitted: 14, drafts: 3, people_with_drafts: 2 }),
    after: (u) => (u === `${BASE}/rooms/close` ? json(200, { state: "board" }) : undefined),
  });
  open();
  expect(await screen.findByText(t.counts(14, 3, 2))).toBeInTheDocument();
  expect(screen.queryByText(/Capital calls/)).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: t.close }));
  expect(calls.some((c) => c.url.endsWith("/rooms/close"))).toBe(false); // asked first
  await user.click(screen.getByRole("button", { name: t.closeYes }));
  await waitFor(() => expect(calls.find((c) => c.url.endsWith("/rooms/close"))).toMatchObject({ method: "POST" }));
});

test("while the rooms are open a participant is only told when the board appears", async () => {
  serve({ board: () => json(409, { error: "wrong_state", message: "The board appears when the private rooms close." }) });
  open();
  expect(await screen.findByText(t.notYet)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: t.close })).not.toBeInTheDocument();
});

// ---- the board
test("the board shows North's groups with counts, the anonymous notes without an author and the lone note on its own", async () => {
  serve({});
  open();
  expect(await screen.findByRole("heading", { name: "Calls arrive too late" })).toBeInTheDocument();
  expect(screen.getByText(t.summary(5, 2, 1))).toBeInTheDocument();
  expect(screen.getByText(t.groupedLine(4, 2, 1), { exact: false })).toBeInTheDocument();
  expect(screen.getByText("Suggestion")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: t.onItsOwn })).toBeInTheDocument();
  expect(screen.getByText("Fee reports differ by manager")).toBeInTheDocument();
  expect(screen.getAllByText(t.anonymous)).toHaveLength(2);
  expect(screen.getAllByText(t.by("Ada"), { exact: false })).toHaveLength(2);
  expect(screen.queryByText(t.by("Pat"), { exact: false })).not.toBeInTheDocument();
});

test("the notes can be shown as written", async () => {
  const user = userEvent.setup();
  serve({});
  open();
  await user.click(await screen.findByRole("button", { name: t.viewRaw }));
  expect(screen.getByRole("button", { name: t.viewRaw })).toHaveAttribute("aria-pressed", "true");
  expect(screen.queryByRole("heading", { name: "Calls arrive too late" })).not.toBeInTheDocument();
  expect(screen.getByText("Exposure by name takes a week")).toBeInTheDocument();
});

test("a participant can read the board and has no edit controls", async () => {
  serve({ board: () => json(200, board({ organiser: false, can_edit: false, can_restore: false })) });
  open();
  await screen.findByRole("heading", { name: "Calls arrive too late" });
  expect(screen.queryByRole("button", { name: t.rename })).not.toBeInTheDocument();
  expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: t.toTogether })).not.toBeInTheDocument();
  expect(screen.getByText(t.readOnly)).toBeInTheDocument();
});

// ---- the organiser's edits
test("the organiser moves a note to another group", async () => {
  const user = userEvent.setup();
  serve({ after: (u) => (u.includes("/move") ? json(200, board()) : undefined) });
  open();
  const pick = await screen.findByRole("combobox", { name: t.moveLabel("Fee reports differ by manager") });
  await user.selectOptions(pick, "c2");
  await waitFor(() => expect(calls.find((c) => c.url === `${BASE}/board/notes/n5/move`)?.body).toEqual({ cluster_id: "c2" }));
});

test("a note taken out of a group goes on its own", async () => {
  const user = userEvent.setup();
  serve({ after: (u) => (u.includes("/move") ? json(200, board()) : undefined) });
  open();
  await user.selectOptions(await screen.findByRole("combobox", { name: t.moveLabel("Capital calls reach us too late") }), "own");
  await waitFor(() => expect(calls.find((c) => c.url === `${BASE}/board/notes/n1/move`)?.body).toEqual({ cluster_id: null }));
});

test("the organiser renames a group", async () => {
  const user = userEvent.setup();
  serve({ after: (u) => (u.includes("/rename") ? json(200, board()) : undefined) });
  open();
  await user.click(await screen.findByRole("button", { name: t.renameLabel("Calls arrive too late") }));
  const field = screen.getByRole("textbox", { name: t.renameField });
  await user.clear(field);
  await user.type(field, "Late capital calls");
  await user.click(screen.getByRole("button", { name: t.save }));
  await waitFor(() => expect(calls.find((c) => c.url === `${BASE}/board/clusters/c1/rename`)?.body).toEqual({ name: "Late capital calls" }));
});

test("the organiser splits a group: at least one note must stay", async () => {
  const user = userEvent.setup();
  serve({ after: (u) => (u.includes("/split") ? json(200, board()) : undefined) });
  open();
  await user.click(await screen.findByRole("button", { name: t.splitLabel("Calls arrive too late") }));
  const go = screen.getByRole("button", { name: t.splitDo });
  expect(go).toBeDisabled();
  await user.click(screen.getByRole("checkbox", { name: t.splitPick("We learn of calls by email") }));
  await user.click(go);
  await waitFor(() => expect(calls.find((c) => c.url === `${BASE}/board/clusters/c1/split`)?.body).toEqual({ note_ids: ["n2"] }));
});

test("North's grouping can be restored after a confirmation", async () => {
  const user = userEvent.setup();
  serve({ after: (u) => (u.endsWith("/board/restore") ? json(200, board()) : undefined) });
  open();
  await user.click(await screen.findByRole("button", { name: t.restore }));
  expect(calls.some((c) => c.url.endsWith("/restore"))).toBe(false);
  await user.click(screen.getByRole("button", { name: t.restoreYes }));
  await waitFor(() => expect(calls.some((c) => c.url.endsWith("/restore"))).toBe(true));
});

// ---- North's grouping
test("the organiser's screen asks North to group the notes once, the first time it opens", async () => {
  serve({
    board: () => json(200, board({ status: "none", can_restore: false, clusters: [], on_its_own: [LATE.notes[0]!, FEES], counts: { notes: 2, clusters: 0, on_its_own: 2 } })),
    after: (u) => (u.endsWith("/board/group") ? json(200, board()) : undefined),
  });
  open();
  await waitFor(() => expect(calls.filter((c) => c.url.endsWith("/board/group"))).toHaveLength(1));
  expect(await screen.findByRole("heading", { name: "Calls arrive too late" })).toBeInTheDocument();
});

test("when North could not group, the notes stay on their own with a plain message and a retry", async () => {
  const user = userEvent.setup();
  serve({
    board: () => json(200, board({ status: "failed", can_restore: false, clusters: [], on_its_own: [LATE.notes[0]!, FEES], counts: { notes: 2, clusters: 0, on_its_own: 2 } })),
    after: (u) => (u.endsWith("/board/group") ? json(200, board()) : undefined),
  });
  open();
  expect(await screen.findByText(t.failed)).toBeInTheDocument();
  expect(screen.getByText("Fee reports differ by manager")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: t.retry }));
  await waitFor(() => expect(calls.some((c) => c.url.endsWith("/board/group"))).toBe(true));
});

test("the organiser brings the room back together", async () => {
  const user = userEvent.setup();
  serve({ after: (u) => (u.endsWith("/together") ? json(200, { state: "together" }) : undefined) });
  open();
  await user.click(await screen.findByRole("button", { name: t.toTogether }));
  await waitFor(() => expect(calls.find((c) => c.url.endsWith("/together"))).toMatchObject({ method: "POST" }));
});

test("after the organiser has changed the groups by hand North's line describes the groups as they are now", async () => {
  serve({ board: () => json(200, board({ edited: true, counts: { notes: 5, clusters: 2, on_its_own: 0 }, on_its_own: [] })) });
  open();
  expect(await screen.findByText(t.editedLine(2, 0), { exact: false })).toBeInTheDocument();
  expect(screen.queryByText(t.groupedLine(5, 2, 0), { exact: false })).not.toBeInTheDocument();
  expect(screen.getByText(t.nothingAlone)).toBeInTheDocument();
});

test("grouped without North: the organiser sees the check-it note and can group again", async () => {
  const user = userEvent.setup();
  serve({
    board: () => json(200, board({ grouped_without_north: true })),
    after: (u) => (u.endsWith("/board/group") ? json(200, board()) : undefined),
  });
  open();
  expect(await screen.findByText(t.withoutNorth)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: t.regroup }));
  await waitFor(() => expect(calls.some((c) => c.url.endsWith("/board/group"))).toBe(true));
});

test("the organiser makes a cluster by hand", async () => {
  const user = userEvent.setup();
  serve({ after: (u) => (u.endsWith("/board/clusters") ? json(200, board()) : undefined) });
  open();
  await user.type(await screen.findByRole("textbox", { name: t.clusterName }), "Our own group");
  await user.click(screen.getByRole("button", { name: t.makeCluster }));
  await waitFor(() => expect(calls.find((c) => c.url.endsWith("/board/clusters"))).toMatchObject({ method: "POST", body: { name: "Our own group" } }));
});

test("a guest cannot make a cluster, and the together refusal is shown in plain words", async () => {
  const user = userEvent.setup();
  serve({
    board: () => json(200, board({ organiser: false, can_edit: false })),
  });
  const guest = open();
  expect(await screen.findByText(t.readOnly)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: t.makeCluster })).not.toBeInTheDocument();
  guest.unmount();
  serve({ after: (u) => (u.endsWith("/together") ? json(409, { error: "wrong_state", message: "Group the notes first, or make a cluster by hand." }) : undefined) });
  open();
  await user.click(await screen.findByRole("button", { name: t.toTogether }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Group the notes first, or make a cluster by hand.");
});
