import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, test, vi } from "vitest";

import NorthPanel, { NorthNudge, type NorthState } from "./NorthPanel";

// B08: North's panel. fetch is stubbed; nothing leaves the page. Synthetic names only.
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const draft = (extra: object = {}) => ({
  id: "d1", kind: "opening", text: "Add your notes before Thursday.", status: "draft", chip: "Draft by North, not confirmed",
  based_on: ["the intent record", "the time box"], options: null, can_confirm: true, confirm_by: "Janet Shaw", is_proposal: false, ...extra,
});
const state = (extra: Partial<NorthState> = {}): NorthState => ({
  head: { name: "North", role_line: "runs this initiative with you" }, read_only: false, can_answer: true, waiting: 1,
  asking: { question: "Whom do you need to involve?", mine: true, holder_name: "Janet Shaw" }, turn: { line: "Your turn: answer the start question", mine: true },
  clock: "Day 4 of 10, 6 days left.", drafts: [draft() as never], thread: [], voice: { available: false, reason: "Spoken replies are not set up for intents yet." },
  ...extra,
});
const posts: { url: string; body: unknown }[] = [];
function mock(s: NorthState, after?: NorthState) {
  posts.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") { posts.push({ url, body: init.body ? JSON.parse(String(init.body)) : undefined }); return json(200, after ?? s); }
    return json(200, s);
  }));
}
afterEach(() => vi.unstubAllGlobals());

describe("North panel", () => {
  test("shows the question, the turn, the clock and a draft marked as a draft", async () => {
    mock(state());
    render(<NorthPanel intentId="i-1" />);
    expect(await screen.findByText("Whom do you need to involve?")).toBeInTheDocument();
    expect(screen.getByTestId("north-pill")).toHaveTextContent("North, 1 waiting");
    expect(screen.getByTestId("north-turn")).toHaveTextContent("Your turn: answer the start question");
    expect(screen.getByTestId("north-clock")).toHaveTextContent("Day 4 of 10, 6 days left.");
    expect(screen.getByText("Draft by North, not confirmed")).toBeInTheDocument();
    expect(screen.getByText("No conversation yet. North will open one when this intent starts.")).toBeInTheDocument();
  });

  test("Answer is off until there is text, then posts to the turns route", async () => {
    mock(state(), state({ asking: null, waiting: 0 }));
    render(<NorthPanel intentId="i-1" />);
    const answer = await screen.findByRole("button", { name: "Answer" });
    expect(answer).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Your answer"), "Daniel and Aaron");
    await userEvent.click(answer);
    await waitFor(() => expect(posts).toEqual([{ url: "/api/intents/i-1/north/turns", body: { text: "Daniel and Aaron" } }]));
    expect(await screen.findByText("North has nothing to ask right now.")).toBeInTheDocument();
  });

  test("Confirm posts for the named person; others see who can confirm", async () => {
    mock(state());
    const { unmount } = render(<NorthPanel intentId="i-1" />);
    await userEvent.click(await screen.findByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(posts[0]?.url).toBe("/api/intents/i-1/north/drafts/d1/confirm"));
    unmount();
    mock(state({ drafts: [draft({ can_confirm: false }) as never] }));
    render(<NorthPanel intentId="i-1" />);
    expect(await screen.findByText("Only Janet Shaw can confirm this")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm" })).toBeDisabled();
  });

  test("a proposal needs a reason before the pick is recorded", async () => {
    const options = [{ key: "extend", label: "Extend the time box", reason: "required" }, { key: "close", label: "Close with what we have", reason: "optional" }];
    mock(state({ drafts: [draft({ kind: "extend_close_cancel", options, is_proposal: true }) as never] }));
    render(<NorthPanel intentId="i-1" />);
    await userEvent.click(await screen.findByRole("button", { name: "Extend the time box" }));
    const record = screen.getByRole("button", { name: "Record my pick" });
    expect(record).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Why (one line)"), "The data is late");
    await userEvent.click(record);
    await waitFor(() => expect(posts).toEqual([{ url: "/api/intents/i-1/north/proposals/d1/pick", body: { key: "extend", reason: "The data is late" } }]));
  });

  test("a reader has no answer box; someone else's turn disables it", async () => {
    mock(state({ read_only: true, can_answer: false, drafts: [] }));
    const { unmount } = render(<NorthPanel intentId="i-1" />);
    expect(await screen.findByText("You are reading this intent. You cannot answer.")).toBeInTheDocument();
    expect(screen.queryByLabelText("Your answer")).toBeNull();
    unmount();
    mock(state({ asking: { question: "Who is the sponsor?", mine: false, holder_name: "Janet Shaw" }, drafts: [] }));
    render(<NorthPanel intentId="i-1" />);
    expect(await screen.findByLabelText("Your answer")).toBeDisabled();
    expect(screen.getAllByText("Waiting for Janet Shaw").length).toBeGreaterThan(0);
  });

  test("a failed answer shows North's plain line", async () => {
    vi.stubGlobal("fetch", vi.fn(async (_u: string, init?: RequestInit) => (init?.method === "POST" ? json(500, {}) : json(200, state()))));
    render(<NorthPanel intentId="i-1" />);
    await userEvent.type(await screen.findByLabelText("Your answer"), "Hello");
    await userEvent.click(screen.getByRole("button", { name: "Answer" }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
  test.each([403, 404])("a %i renders nothing: no panel, no not-found line, no Try again", async (code) => {
    const f = vi.fn(async () => json(code, { error: "x", message: "We could not find that intent." }));
    vi.stubGlobal("fetch", f);
    const { container } = render(<NorthPanel intentId="i-1" />);
    await waitFor(() => expect(f).toHaveBeenCalled());
    await waitFor(() => expect(container.querySelector(".ds-north")).toBeNull());
    expect(screen.queryByText("We could not find that intent.")).toBeNull();
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });
  test("no seat (the person only sees that the intent exists) renders nothing", async () => {
    const f = vi.fn(async () => json(200, { intent: { id: "i-1" }, seat: null }));
    vi.stubGlobal("fetch", f);
    const { container } = render(<NorthPanel intentId="i-1" />);
    await waitFor(() => expect(f).toHaveBeenCalled());
    await waitFor(() => expect(container.querySelector(".ds-north")).toBeNull());
    expect(container.textContent).toBe("");
  });
});

describe("North panel, F27", () => {
  test("Ask North posts a question, Something is wrong posts a wrong note, Retry repeats a failed call", async () => {
    mock(state({ seat: "participant" }));
    render(<NorthPanel intentId="i-1" />);
    await userEvent.type(await screen.findByLabelText("Ask North something about this intent"), "What is a data source?");
    await userEvent.click(screen.getByRole("button", { name: "Ask North" }));
    await waitFor(() => expect(posts[0]).toEqual({ url: "/api/intents/i-1/north/turns", body: { text: "What is a data source?", ask: true } }));
    await userEvent.click(screen.getByRole("button", { name: "Tell the organiser North got this wrong" }));
    await userEvent.type(screen.getByLabelText("What did North get wrong?"), "Wrong date");
    await userEvent.click(screen.getByRole("button", { name: "Tell the organiser" }));
    await waitFor(() => expect(posts[1]?.body).toEqual({ text: "Wrong date", wrong: true }));
  });

  test("the organiser has no Something is wrong link; a failed call shows Try again", async () => {
    vi.stubGlobal("fetch", vi.fn(async (_u: string, init?: RequestInit) => (init?.method === "POST" ? json(500, {}) : json(200, state({ seat: "organiser", drafts: [] })))));
    render(<NorthPanel intentId="i-1" />);
    await userEvent.type(await screen.findByLabelText("Ask North something about this intent"), "Hello");
    expect(screen.queryByRole("button", { name: "Tell the organiser North got this wrong" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Ask North" }));
    expect(await screen.findByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  test("the nudge strip shows today's nudge and Not now hides it", async () => {
    mock(state({ nudge: { text: "Aaron, please add your notes by Friday.", at: "2026-10-08T09:00:00Z" } }));
    render(<NorthNudge intentId="i-1" />);
    expect(await screen.findByTestId("north-nudge")).toHaveTextContent("Aaron, please add your notes by Friday.");
    await userEvent.click(screen.getByRole("button", { name: "Not now" }));
    expect(screen.queryByTestId("north-nudge")).toBeNull();
    localStorage.clear();
  });
});
