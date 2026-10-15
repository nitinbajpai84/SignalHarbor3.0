import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { copy } from "../../../copy";
import type { TogetherCluster, TogetherView } from "../api";
import { m1Notes, m1Together as t } from "../copy";
import TogetherScreen from "./TogetherScreen";

// M1-20 to M1-23 screens: counts, a vote bar per option with a live tally, agree, thread, tick, hold the room. Family-office wording.

const SID = "c".repeat(32);
const BASE = `/api/modules/m1_intent/sessions/${SID}`;
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const OPTIONS = [
  { id: "must", label: "Must" }, { id: "should", label: "Should" }, { id: "could", label: "Could" }, { id: "not_this_time", label: "Not this time" },
] as const;
const cluster = (over: Partial<TogetherCluster> = {}): TogetherCluster => ({
  id: "c1", name: "Calls arrive too late", note_count: 6, agree_count: 7, comment_count: 1,
  votes: { must: 3, should: 1, could: 0, not_this_time: 0 }, vote_total: 4, priority: "must", ticked: true, my_vote: null, my_agree: false,
  comments: [{ text: "Calls reach the cash team last", anonymous: false, author_name: "Ada" }, { text: "I would put this first", anonymous: true }],
  notes: [{ id: "n1", text: "Capital calls reach us too late", anonymous: false, mine: false, author_name: "Ada" }], ...over,
});
const view = (over: Partial<TogetherView> = {}): TogetherView => ({
  stage: "together", paused_from: null, held: false, organiser: true, can_vote: true, options: [...OPTIONS],
  clusters: [cluster(), cluster({ id: "c2", name: "Nobody owns the list", note_count: 2, agree_count: 1, comment_count: 0, ticked: false, votes: { must: 0, should: 0, could: 0, not_this_time: 0 }, vote_total: 0, priority: null, comments: [] })],
  on_its_own_count: 1, ticked_count: 1, open_count: 1, i_done: false, done_count: 0, people_count: 3, ...over,
});
const calls: { method: string; url: string; body: unknown }[] = [];

function serve(get: () => Response | Promise<Response>, after?: (url: string) => Response | undefined) {
  calls.length = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
      if (url === `${BASE}/together` && method === "GET") return get();
      if (url === `${BASE}/timer`) return json(200, { stage: "together", timed: false, now: "z" });
      return after?.(url) ?? json(404, {});
    }),
  );
}
const open = () =>
  render(
    <MemoryRouter initialEntries={[`/s/${SID}`]}>
      <Routes>
        <Route path="/s/:sessionId" element={<TogetherScreen />} />
      </Routes>
    </MemoryRouter>,
  );
const card = async (name: string) => within((await screen.findByRole("heading", { name })).closest("section") as HTMLElement);
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

// ---- five states
test("loading", () => {
  serve(() => new Promise<Response>(() => undefined));
  open();
  expect(screen.getByRole("status")).toHaveTextContent("Loading");
});

test("an error offers to try again", async () => {
  serve(() => json(500, { error: "x" }));
  open();
  expect(await screen.findByRole("alert")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
});

test("a refusal is shown in plain words", async () => {
  serve(() => json(403, { error: "forbidden", message: "no" }));
  open();
  expect(await screen.findByRole("alert")).toHaveTextContent(copy.states.refused);
});

test("before the room is back together the person is told so", async () => {
  serve(() => json(409, { error: "wrong_state", message: "The room is not back together yet." }));
  open();
  expect(await screen.findByText(t.notYet)).toBeInTheDocument();
});

test("with no groups the screen says so", async () => {
  serve(() => json(200, view({ clusters: [], ticked_count: 0, open_count: 0 })));
  open();
  expect(await screen.findByText(t.empty)).toBeInTheDocument();
});

// ---- the populated room
test("each group shows its counts, a bar and a tally per option, and the room's priority so far", async () => {
  serve(() => json(200, view()));
  open();
  const c = await card("Calls arrive too late");
  expect(c.getByText(t.counts(6, 7, 1))).toBeInTheDocument();
  expect(c.getByText(t.votes(3))).toBeInTheDocument();
  expect(c.getAllByText(t.votes(0))).toHaveLength(2);
  expect(c.getByText(t.priority("Must"))).toBeInTheDocument();
  expect(c.getByRole("button", { name: t.voteOn("Not this time", "Calls arrive too late") })).toBeInTheDocument();
  const second = await card("Nobody owns the list");
  expect(second.getByText(t.voteNone)).toBeInTheDocument();
  expect(screen.getByText(t.summary(2, 1))).toBeInTheDocument();
  expect(screen.getByText(t.alone(1))).toBeInTheDocument();
});

test("a thread shows who wrote a comment, or anonymous, and never a name beside an anonymous one", async () => {
  serve(() => json(200, view()));
  open();
  const c = await card("Calls arrive too late");
  expect(c.getByText("Ada")).toBeInTheDocument();
  expect(c.getByText("Calls reach the cash team last")).toBeInTheDocument();
  expect(c.getByText(t.anonymous).closest("li")).toHaveTextContent("I would put this first");
  expect(c.getByText(t.anonymous).closest("li")).not.toHaveTextContent("Ada");
});

test("voting posts the option, shows it pressed, and pressing it again takes the vote back", async () => {
  const user = userEvent.setup();
  serve(() => json(200, view()), (u) => (u.endsWith("/vote") ? json(200, view({ clusters: [cluster({ my_vote: "should" })] })) : undefined));
  open();
  const c = await card("Calls arrive too late");
  await user.click(c.getByRole("button", { name: t.voteOn("Should", "Calls arrive too late") }));
  await waitFor(() => expect(calls.find((x) => x.url === `${BASE}/together/clusters/c1/vote`)?.body).toEqual({ option: "should" }));
  await waitFor(() => expect(screen.getByRole("button", { name: t.voteOn("Should", "Calls arrive too late") })).toHaveAttribute("aria-pressed", "true"));
  await user.click(screen.getByRole("button", { name: t.voteOn("Should", "Calls arrive too late") }));
  await waitFor(() => expect(calls.filter((x) => x.url.endsWith("/vote")).at(-1)?.body).toEqual({ option: null }));
});

test("agree posts a mark and a comment posts its text and whether it is anonymous", async () => {
  const user = userEvent.setup();
  serve(() => json(200, view()), (u) => (u.endsWith("/agree") || u.endsWith("/comments") ? json(200, view()) : undefined));
  open();
  const c = await card("Calls arrive too late");
  await user.click(c.getByRole("button", { name: t.agreeLabel("Calls arrive too late") }));
  await waitFor(() => expect(calls.find((x) => x.url.endsWith("/agree"))?.body).toEqual({ agree: true }));
  await user.type(c.getByRole("textbox", { name: t.commentField }), "Put this first");
  await user.click(c.getByRole("checkbox", { name: t.commentAnon }));
  await user.click(c.getByRole("button", { name: t.commentSend }));
  await waitFor(() => expect(calls.find((x) => x.url.endsWith("/comments"))?.body).toEqual({ text: "Put this first", anonymous: true }));
});

test("the comment's anonymous box shows only when each person chooses; otherwise the rule is said and sent", async () => {
  const user = userEvent.setup();
  serve(() => json(200, view({ names: "anonymous" })), (u) => (u.endsWith("/comments") ? json(200, view({ names: "anonymous" })) : undefined));
  open();
  const c = await card("Calls arrive too late");
  expect(c.queryByRole("checkbox", { name: t.commentAnon })).not.toBeInTheDocument();
  expect(c.getByText(m1Notes.namesAnonymous)).toBeInTheDocument();
  await user.type(c.getByRole("textbox", { name: t.commentField }), "Put this first");
  await user.click(c.getByRole("button", { name: t.commentSend }));
  await waitFor(() => expect(calls.find((x) => x.url.endsWith("/comments"))?.body).toEqual({ text: "Put this first", anonymous: true }));
});

test("in an open session the comment box says names are shown and never offers anonymous", async () => {
  serve(() => json(200, view({ names: "named" })));
  open();
  const c = await card("Calls arrive too late");
  expect(c.queryByRole("checkbox", { name: t.commentAnon })).not.toBeInTheDocument();
  expect(c.getByText(m1Notes.namesNamed)).toBeInTheDocument();
});

test("a failed vote says what happened in one sentence", async () => {
  const user = userEvent.setup();
  serve(() => json(200, view()), (u) => (u.endsWith("/vote") ? json(409, { error: "wrong_state", message: "The room is held." }) : undefined));
  open();
  await user.click((await card("Calls arrive too late")).getByRole("button", { name: t.voteOn("Must", "Calls arrive too late") }));
  expect(await screen.findByRole("alert")).toHaveTextContent("The room is held.");
});

// ---- the organiser
test("the organiser ticks a group into the charter and a participant only sees where it stands", async () => {
  const user = userEvent.setup();
  serve(() => json(200, view()), (u) => (u.endsWith("/tick") ? json(200, view()) : undefined));
  const first = open();
  const box = (await card("Nobody owns the list")).getByRole("checkbox", { name: t.tickLabel("Nobody owns the list") });
  expect(box).not.toBeChecked();
  await user.click(box);
  await waitFor(() => expect(calls.find((x) => x.url === `${BASE}/together/clusters/c2/tick`)?.body).toEqual({ ticked: true }));
  first.unmount();

  serve(() => json(200, view({ organiser: false })));
  open();
  const c = await card("Nobody owns the list");
  expect(c.queryByRole("checkbox", { name: t.tickLabel("Nobody owns the list") })).not.toBeInTheDocument();
  expect(c.getByText(t.carried)).toBeInTheDocument();
  expect((await card("Calls arrive too late")).getByText(t.inCharter)).toBeInTheDocument();
});

test("ticking a group shows at once, before any reload", async () => {
  const user = userEvent.setup();
  const ticked = view({ clusters: view().clusters.map((c) => ({ ...c, ticked: true })), ticked_count: 2, open_count: 0 });
  serve(() => json(200, view()), (u) => (u.endsWith("/tick") ? json(200, ticked) : undefined));
  open();
  const box = (await card("Nobody owns the list")).getByRole("checkbox", { name: t.tickLabel("Nobody owns the list") });
  await user.click(box);
  await waitFor(() => expect(box).toBeChecked());
  expect(screen.getByRole("button", { name: t.finishNow })).toBeInTheDocument();
});

test("both finish buttons carry the same words, and the done count says people", () => {
  expect(t.finishNow).toBe("We're done, go to the charter");
  expect(t.finishButton).toBe(t.finishNow);
  expect(t.doneCount(0, 3)).toBe("0 of 3 people said they are done");
});

test("Nira asks whether to hold the room; holding posts the pause, and a held room can be resumed", async () => {
  const user = userEvent.setup();
  serve(() => json(200, view()), (u) => (u.endsWith("/pause") ? json(200, { state: "paused", paused_from: "together" }) : undefined));
  const first = open();
  expect(await screen.findByText(t.niraAsk(1, 1))).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: t.hold }));
  await waitFor(() => expect(calls.find((x) => x.url === `${BASE}/pause`)).toMatchObject({ method: "POST" }));
  first.unmount();

  serve(() => json(200, view({ held: true, stage: "paused", paused_from: "together", can_vote: false })), (u) => (u.endsWith("/resume") ? json(200, { state: "together" }) : undefined));
  open();
  expect(await screen.findByText(t.niraHeld)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: t.voteOn("Must", "Calls arrive too late") })).toBeDisabled();
  await user.click(screen.getByRole("button", { name: t.resume }));
  await waitFor(() => expect(calls.find((x) => x.url === `${BASE}/resume`)).toMatchObject({ method: "POST" }));
});

test("a participant is told the room is held and has no hold button", async () => {
  serve(() => json(200, view({ organiser: false, held: true, stage: "paused", paused_from: "together", can_vote: false })));
  open();
  expect(await screen.findByText(t.niraGuestHeld)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: t.resume })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: t.hold })).not.toBeInTheDocument();
});

// ---- finishing early
const charterPost = (u: string) => (u === `${BASE}/charter` ? json(201, { state: "signing" }) : undefined);
const drafted = () => calls.find((x) => x.url === `${BASE}/charter`);

test("with problems still open the organiser sees the done button and must confirm before the charter is drafted", async () => {
  const user = userEvent.setup();
  serve(() => json(200, view()), charterPost);
  open();
  await user.click(await screen.findByRole("button", { name: t.finishButton }));
  expect(screen.getByRole("alertdialog", { name: t.finishSure(1) })).toBeInTheDocument();
  expect(drafted()).toBeUndefined();
  await user.click(screen.getByRole("button", { name: t.finishNo }));
  expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: t.finishButton }));
  await user.click(screen.getByRole("button", { name: t.finishYes }));
  await waitFor(() => expect(drafted()).toMatchObject({ method: "POST" }));
});

test("when every problem is decided Nira offers to finish, with hold as the second choice and no question asked", async () => {
  const user = userEvent.setup();
  serve(() => json(200, view({ clusters: [cluster()], open_count: 0 })), charterPost);
  open();
  expect(await screen.findByText(t.niraDecided(1))).toBeInTheDocument();
  expect(screen.getByRole("button", { name: t.hold })).not.toHaveClass("primary");
  expect(screen.getAllByRole("button", { name: t.finishNow })).toHaveLength(1); // one finish button, same words in both states
  await user.click(screen.getByRole("button", { name: t.finishNow }));
  expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  await waitFor(() => expect(drafted()).toMatchObject({ method: "POST" }));
});

test("the organiser sees how many are done; a participant has I'm done and no finish button", async () => {
  const user = userEvent.setup();
  serve(() => json(200, view({ done_count: 4, people_count: 6 })));
  const first = open();
  expect(await screen.findByText(t.doneCount(4, 6))).toBeInTheDocument();
  first.unmount();

  serve(() => json(200, view({ organiser: false })), (u) => (u === `${BASE}/together/done` ? json(200, view({ organiser: false, i_done: true })) : undefined));
  open();
  await user.click(await screen.findByRole("button", { name: t.imDone }));
  await waitFor(() => expect(calls.find((x) => x.url === `${BASE}/together/done`)?.body).toEqual({ done: true }));
  expect(await screen.findByRole("button", { name: t.notDone })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: t.finishButton })).not.toBeInTheDocument();
  expect(screen.queryByText(t.doneCount(4, 6))).not.toBeInTheDocument();
});
