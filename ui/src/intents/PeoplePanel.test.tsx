import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, test, vi } from "vitest";

import PeoplePanel, { InvitationCard, type PeopleData } from "./PeoplePanel";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const data = (o: Partial<PeopleData> = {}): PeopleData => ({
  intent: { id: "i1", type: "brainstorm", title: "Month-end", state: "open", areas: [], area_ids: [], ends: "10 Oct" }, level: "organiser", me: null,
  people: [{ person_id: "o", name: "Janet Shaw", role: "organiser", status: "joined" }, { person_id: "a", name: "Aaron Lyle", role: "participant", status: "invited" }],
  counts: { people: 2, joined: 1, contributed: 0, confirmed: 0, invited: 1, affected: 0, not_answered: 1, declined: 0, removed: 0 }, roles_allowed: ["participant", "observer"],
  can_invite: true, can_ask: false, range: null, waiting: { names: ["Aaron"], ids: ["a"], last_reminder: null }, gone: [], drafts: null, wall_session_id: null, history: [],
  invitation: null, ...o,
});
const posts: { url: string; body: unknown }[] = [];
function mock(d: PeopleData) {
  posts.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") { posts.push({ url, body: JSON.parse(String(init.body)) }); return json({}); }
    return json(d);
  }));
}
afterEach(() => vi.unstubAllGlobals());

describe("PeoplePanel", () => {
  test("the organiser sees the count, the summary, who North waits for, and Invite", async () => {
    mock(data());
    render(<MemoryRouter><PeoplePanel intentId="i1" /></MemoryRouter>);
    expect(await screen.findByText("People (2)")).toBeTruthy();
    expect(screen.getByText("1 joined, 0 contributed, 0 confirmed")).toBeTruthy();
    expect(screen.getByText(/North is waiting for Aaron\./)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Invite" })).toBeTruthy();
  });

  test("another person gets no Invite and the plain empty line", async () => {
    mock(data({ level: "member", can_invite: false, people: [{ person_id: "o", name: "Janet Shaw", role: "organiser", status: "joined" }], waiting: null }));
    render(<MemoryRouter><PeoplePanel intentId="i1" /></MemoryRouter>);
    expect(await screen.findByText("Nobody else has been added yet.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Invite" })).toBeNull();
  });
});

describe("InvitationCard", () => {
  test("renders nothing when the viewer has no invitation", async () => {
    mock(data());
    const { container } = render(<InvitationCard intentId="i1" onAnswered={() => undefined} />);
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByText("We could not find that.")).toBeNull();
    expect(container.querySelector("section")).toBeNull();
  });

  const inv = { inviter: "Janet", title: "Month-end", purpose: "Cut it", ask: "You are asked to take part.", note: null, ends: "10 Oct", minutes: 5, reason_required: true, closed: false, closed_note: null };
  test("a required reason keeps Send my reason off until one is written, then declines", async () => {
    mock(data({ level: "member", me: { person_id: "a", role: "participant", status: "invited" }, invitation: inv }));
    render(<InvitationCard intentId="i1" onAnswered={() => undefined} />);
    expect(await screen.findByText("Janet has invited you to Month-end")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Decline" }));
    const send = screen.getByRole("button", { name: "Send my reason" });
    expect((send as HTMLButtonElement).disabled).toBe(true);
    await userEvent.type(screen.getByPlaceholderText("Why not? A short line helps the organiser plan."), "On leave");
    await userEvent.click(send);
    expect(posts[0]).toEqual({ url: "/api/intents/i1/people/a/answer", body: { action: "decline", reason: "On leave" } });
  });
  test("W2F2: a closed intent shows one closed line with the date and outcome, never the invitation or its buttons", async () => {
    const closed = data({ intent: { ...data().intent, state: "closed" }, level: "member", me: { person_id: "a", role: "participant", status: "invited" }, invitation: { ...inv, closed: true } });
    vi.stubGlobal("fetch", vi.fn(async (url: string) => json(url.includes("/closure")
      ? { closed_on: "2 Oct", cancel: null, outcome: { lines: [{ label: "Chosen idea", value: "Read the mailbox" }], missing: [] } } : closed)));
    render(<MemoryRouter><InvitationCard intentId="i1" /></MemoryRouter>);
    expect(await screen.findByText("Closed on 2 Oct.")).toBeTruthy();
    expect(await screen.findByText(/Chosen idea: Read the mailbox/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Read what came out" }).getAttribute("href")).toBe("/centre/intent/i1/close");
    expect(screen.queryByText("Janet has invited you to Month-end")).toBeNull();
    expect(screen.queryByRole("button", { name: "Accept" })).toBeNull();
  });

  test("W2F2: on a closed intent the people panel offers no ask and no email draft", async () => {
    mock(data({ intent: { ...data().intent, state: "closed" }, can_ask: true }));
    render(<MemoryRouter><PeoplePanel intentId="i1" /></MemoryRouter>);
    expect(await screen.findByText("People (2)")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Ask the organiser to add someone" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Draft the email" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Invite" })).toBeNull();
  });
});
