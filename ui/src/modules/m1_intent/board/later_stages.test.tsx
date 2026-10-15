import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { m1Board, m1Together } from "../copy";
import LaterStages from "./LaterStages";
import StageLinks from "./StageLinks";

// One page that follows the session's own stage: the board, then back in the room; and the organiser's link to it.

const SID = "d".repeat(32);
const BASE = `/api/modules/m1_intent/sessions/${SID}`;
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function stage(state: string, extra: Record<string, unknown> = {}) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url === `${BASE}/lobby`) return json(200, { session_id: SID, state, seats: [], arrived: 0, seat_count: 1 });
      if (url === `${BASE}/board`)
        return state === "private_rooms"
          ? json(409, { error: "wrong_state", message: "x" })
          : json(200, { stage: state, paused_from: null, organiser: false, status: "done", can_edit: false, can_restore: false,
              counts: { notes: 0, clusters: 0, on_its_own: 0 }, clusters: [], on_its_own: [], ...extra });
      if (url === `${BASE}/together`)
        return json(200, { stage: state, paused_from: null, held: false, organiser: false, can_vote: true, options: [], clusters: [], on_its_own_count: 0, ticked_count: 0, open_count: 0, i_done: false, done_count: 0, people_count: 0 });
      if (url === `${BASE}/timer`) return json(200, { stage: state, timed: false, now: "z" });
      if (url === `${BASE}`) return json(200, { id: SID, state, preparation: { purpose: "p" } });
      return json(404, {});
    }),
  );
}
const open = (ui = <LaterStages />) =>
  render(
    <MemoryRouter initialEntries={[`/s/${SID}`]}>
      <Routes>
        <Route path="/s/:sessionId" element={ui} />
      </Routes>
    </MemoryRouter>,
  );
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

test("while the rooms are open or just closed the page is the board", async () => {
  stage("board");
  open();
  expect(await screen.findByRole("heading", { name: m1Board.title })).toBeInTheDocument();
});

test("once the room is back together the page is the room", async () => {
  stage("together");
  open();
  expect(await screen.findByRole("heading", { name: m1Together.title })).toBeInTheDocument();
});

test("the organiser's session page links on to the board once the private rooms are open, and not before", async () => {
  stage("private_rooms");
  const a = open(<StageLinks sessionId={SID} />);
  expect(await screen.findByRole("link", { name: m1Board.links.rooms })).toHaveAttribute("href", `/modules/m1_intent/sessions/${SID}/board`);
  a.unmount();
  stage("lobby");
  open(<StageLinks sessionId={SID} />);
  await new Promise((r) => setTimeout(r, 50));
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
});
