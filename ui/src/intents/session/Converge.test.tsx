import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import Converge from "./Converge";
import { LateThoughts, WhatNext } from "./OutcomeCard";
import type { View } from "./convergeApi";

// Spec 37: back up to three, counts never who, the outcome card, What next, late thoughts. fetch is stubbed with synthetic data.

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const row = (ref: string, text: string, backed = 0, mine = false) => ({ ref, kind: "card" as const, text, group: null, anonymous: false, backed, i_backed: mine, replies: 0 });
const base: View = {
  id: "bra-1", title: "Investor day", intent_state: "open", tier: "content", tz: "UTC", ends: null,
  viewer: { organiser: false, seated: true, can_back: true },
  converge: { state: "round_1_open", round: 1, max_rounds: 2, max_backs: 3, used: 3 },
  have_backed: 2, seated_count: 6, rows: [row("c:1", "Idea one", 2, true), row("c:2", "Idea two", 1, true), row("c:3", "Idea three", 0, true), row("c:4", "Idea four")],
  mine: [], tie: null, north: "2 of 6 have backed.", can: {}, next_kinds: ["initiative", "problem", "decision", "backlog", "handled", "nothing"],
  outcome: { chosen: null, ideas_kept: [], dropped: [], next: null, rounds: 1 }, late: null,
};
const chosen = {
  idea: "Client events", why: "3 of 6 backed it. It had 3 backs against 1 for the next idea.",
  why_sources: [{ text: "3 of 6 backed it.", source: "3 of 6 backed" }, { text: "It had 3 backs against 1 for the next idea.", source: "Round 1" }],
  kind: "group" as const, ref: "g:1", what_it_takes: [{ text: "Name who will take this forward, and by when.", source: "north_suggestion" }],
  proposed_by: [{ name: "Person 1" }], proposed_unnamed: 1, backed: 3, backed_of: 6, overridden_reason: null, drafted_by: "north", edited_by: null,
  confirmed_by: null, confirmed_at: null, by_rounds: { round1: 3 },
};
const closed: View = {
  ...base, viewer: { organiser: true, seated: true, can_back: false }, converge: { state: "round_1_closed", round: 1, max_rounds: 2, max_backs: 3, used: 0 },
  mine: [], north: "\"Idea one\" leads with 3 backed.", can: { round2: "Only two ideas, so no second round." },
  candidates: [{ ref: "g:1", text: "Client events", backed: 3, top: true }, { ref: "c:4", text: "Idea four", backed: 1, top: true }],
  outcome: { chosen, ideas_kept: [{ ref: "c:4", kind: "card", text: "Idea four", backed: { round1: 1, round2: null }, runner_up: true }], dropped: [], next: null, rounds: 1 },
  numbers: { ideas_added: 6, groups: 1, backs_cast: 4, people_backed: [4], rounds_run: 1, minutes_to_confirm: { missing: "the outcome is not confirmed yet" } },
  prefill: { questions: [
    { id: "i1", lead: "What are you trying to achieve?", answers: { goal_line: "Client events", why: "3 of 6 backed it." }, from_brainstorm: true },
    { id: "i2", lead: "Whom do you need to involve?", answers: { involve: ["Person 1"] }, from_brainstorm: true },
    { id: "i3", lead: "Do you think this needs a build?", answers: {}, from_brainstorm: false },
  ] },
  backlog_preview: { title: "Client events", why: "3 of 6 backed it.", raised_by: "Person 1", also_considered: ["Idea four"], review_date: null },
};

function mock(get: View, posts: { url: string; body: Record<string, unknown> }[] = [], onPost?: (url: string) => Response | undefined) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method && init.method !== "GET") {
      posts.push({ url, body: init.body ? JSON.parse(String(init.body)) : {} });
      return onPost?.(url) ?? json(200, get);
    }
    return json(200, get);
  }));
  return posts;
}
const mount = (ui: React.ReactElement, at = "/centre/intent/bra-1") => render(<MemoryRouter initialEntries={[at]}>{ui}</MemoryRouter>);

afterEach(() => vi.unstubAllGlobals());

test("three backs used shows 3 of 3, counts only, no names", async () => {
  mock(base);
  mount(<Converge intentId="bra-1" />);
  expect(await screen.findByText("Idea one")).toBeInTheDocument();
  expect(screen.getAllByText("3 of 3 used").length).toBeGreaterThan(0);
  expect(screen.getByText("2 backed")).toBeInTheDocument();
  expect(screen.getAllByText("You backed this")).toHaveLength(3);
  expect(screen.queryByText(/you and/i)).toBeNull();
  expect(screen.getByText("2 of 6 have backed.")).toBeInTheDocument();
});

test("a fourth back shows the server's refusal, and take back sends on:false", async () => {
  const posts = mock(base, [], (url) => (url.endsWith("/back") ? json(409, { message: "You have used all three. Take one back first." }) : undefined));
  mount(<Converge intentId="bra-1" />);
  fireEvent.click((await screen.findAllByRole("button", { name: "Back this" }))[0]!);
  expect(await screen.findByRole("alert")).toHaveTextContent("You have used all three. Take one back first.");
  expect(posts[0]).toEqual({ url: "/api/intents/bra-1/converge/back", body: { candidate: "c:4", on: true } });
});

test("the close dialog names n of m, and an organiser sees the tie dialog with exactly the free places", async () => {
  const org: View = { ...base, viewer: { organiser: true, seated: true, can_back: true }, can: {} };
  mock(org);
  const a = mount(<Converge intentId="bra-1" />);
  fireEvent.click(await screen.findByRole("button", { name: "Close the count" }));
  expect(screen.getByText("2 of 6 have backed. Close the count? People can no longer change their backs.")).toBeInTheDocument();
  a.unmount();
  const tied: View = { ...closed, converge: { ...closed.converge, state: "round_1_closed" }, tie: { among: ["c:1", "c:2", "c:3"], free: 2, count: 1, resolved: false, picks: [] }, can: { round2: "Pick which ideas go forward first." } };
  const posts = mock(tied);
  mount(<Converge intentId="bra-1" />);
  expect(await screen.findByText(/tied for the last places: Idea one, Idea two, Idea three/)).toBeInTheDocument();
  const use = screen.getByRole("button", { name: "Use these" });
  expect(use).toBeDisabled();
  const boxes = screen.getAllByRole("checkbox");
  fireEvent.click(boxes[0]!);
  fireEvent.click(boxes[2]!);
  fireEvent.click(use);
  await waitFor(() => expect(posts[0]?.body).toEqual({ tie_picks: ["c:1", "c:3"] }));
});

test("observers and the sponsor read but cannot back", async () => {
  mock({ ...base, viewer: { organiser: false, seated: false, can_back: false }, converge: { ...base.converge, used: 0 } });
  mount(<Converge intentId="bra-1" />);
  await screen.findByText("Idea one");
  expect(screen.queryByRole("button", { name: "Back this" })).toBeNull();
  expect(screen.queryByText("Your backs")).toBeNull();
});

test("outcome card: every sentence has its source chip, confirm names what is missing", async () => {
  mock(closed);
  mount(<Converge intentId="bra-1" />, "/centre/intent/bra-1?view=outcome");
  expect(await screen.findByText("Draft by North")).toBeInTheDocument();
  expect(screen.getByText("3 of 6 backed")).toBeInTheDocument();
  expect(screen.getByText("Round 1")).toBeInTheDocument();
  expect(screen.getByText("North's suggestion")).toBeInTheDocument();
  expect(screen.getByText("Person 1 and 1 who chose to stay unnamed")).toBeInTheDocument();
  expect(screen.getByText("3 of 6 backed this")).toBeInTheDocument();
  expect(screen.getByText("Not available yet: the outcome is not confirmed yet")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Confirm this outcome" })).toBeEnabled();
  fireEvent.change(screen.getByLabelText("The idea"), { target: { value: "" } });
  expect(screen.getByRole("button", { name: "Confirm this outcome" })).toBeDisabled();
  expect(screen.getByText("No idea is chosen yet. Pick one from the count.")).toBeInTheDocument();
});

test("outcome not drafted yet offers Draft it to the organiser only", async () => {
  const none: View = { ...closed, outcome: { ...closed.outcome, chosen: null }, candidates: [{ ref: "c:1", text: "Idea one", backed: 3, top: true }] };
  mock(none);
  const a = mount(<Converge intentId="bra-1" />, "/centre/intent/bra-1?view=outcome");
  expect(await screen.findByText("North has not drafted the outcome yet.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Draft it" })).toBeInTheDocument();
  a.unmount();
  mock({ ...none, viewer: { organiser: false, seated: true, can_back: false } });
  mount(<Converge intentId="bra-1" />, "/centre/intent/bra-1?view=outcome");
  await screen.findByText("North has not drafted the outcome yet.");
  expect(screen.queryByRole("button", { name: "Draft it" })).toBeNull();
});

test("what next lists the six kinds, pre-fills the Initiative with the chip, and reports the choice", async () => {
  mock(closed);
  const seen: { kind: string; reason: string }[] = [];
  mount(<WhatNext intentId="bra-1" onChange={(c) => seen.push({ kind: c.kind, reason: c.reason })} />);
  expect(await screen.findAllByRole("radio")).toHaveLength(6);
  expect(screen.getByText("Say what happens next.")).toBeInTheDocument();
  fireEvent.click(screen.getByLabelText("Turn into an Initiative"));
  expect(screen.getAllByText("From the brainstorm")).toHaveLength(2);
  expect(screen.getByText("Do you think this needs a build?")).toBeInTheDocument();
  expect(screen.getByText("Add the reason")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "It was the most backed." } });
  fireEvent.click(screen.getByLabelText("Put on the backlog"));
  expect(screen.getByText("Idea four", { exact: false })).toBeInTheDocument();
  expect(seen[seen.length - 1]).toEqual({ kind: "backlog", reason: "It was the most backed." });
});

test("late thoughts: window line, limit, and the frozen record", async () => {
  const late = { opens_at: "2026-10-08T09:00:00Z", closes_at: "2026-10-09T15:00:00Z", open: true, frozen_at: null, can_add: true, names: "choice" as const, limit: 300,
    about: [{ ref: "g:1", text: "Client events" }], thoughts: [{ text: "Add a dinner", about: "Client events", at: "2026-10-08T10:00:00Z", anonymous: true, name: null }] };
  const posts = mock({ ...closed, late });
  const a = mount(<LateThoughts intentId="bra-1" />);
  expect(await screen.findByText("You can add a late thought until 9 Oct, 15:00. After that the record is frozen.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Add thought" })).toBeDisabled();
  expect(screen.getByText("Anonymous · Client events · 8 Oct, 10:00")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Your late thought"), { target: { value: "More time for guests" } });
  fireEvent.click(screen.getByRole("button", { name: "Anonymous" }));
  fireEvent.click(screen.getByRole("button", { name: "Add thought" }));
  await waitFor(() => expect(posts[0]?.body).toEqual({ text: "More time for guests", about: "g:1", anonymous: true }));
  a.unmount();
  mock({ ...closed, late: { ...late, open: false, can_add: false, frozen_at: "2026-10-09T15:00:00Z", thoughts: [] } });
  mount(<LateThoughts intentId="bra-1" />);
  expect(await screen.findByText("This record is frozen.")).toBeInTheDocument();
  expect(screen.getByText("Frozen on 9 Oct")).toBeInTheDocument();
  expect(screen.getByText("No late thoughts.")).toBeInTheDocument();
});
