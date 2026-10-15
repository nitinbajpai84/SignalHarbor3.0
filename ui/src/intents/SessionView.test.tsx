import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import SessionView from "./views/SessionView";
import { dateOk, earliest, firstMissing, windowOf } from "./start/BrainstormStart";

// The Brainstorm session (spec 36), pre-thinking (spec 35 Screen D) and the start rules. fetch is stubbed with synthetic data.

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const idea = (id: string, text: string, more: Record<string, unknown> = {}) => ({ id, text, why: "", anonymous: false, author: "Aaron Lyle", mine: false, at: "2026-10-08T10:01:00Z", edited: false, replies: [], group_id: null, group_name: null, ...more });
const BASE = {
  id: "bra-1", title: "Slow reviews", purpose: "To find: one idea to test", state: "in_session", role: "participant", mode: "live", statement: "Performance reviews take two weeks",
  context: null, good_outcome: "One idea to test", session_at: "2026-10-08T10:00:00+00:00", session_minutes: 60, anonymous_allowed: false,
  window: { before: "2026-10-07", session: "2026-10-08", after: "2026-10-09" }, starts: "2026-10-07T00:00:00+00:00", ends: "2026-10-09T23:59:59+00:00",
  my_status: "Accepted", counts: null, invited: null, message: null, phase: "diverge", paused: false, remaining_seconds: 840,
  prompts: { diverge: { text: "Add as many ideas as you can for: Performance reviews take two weeks.", drafted_by: "north", edited_by: null, edited_at: null } },
  north_lines: [], ideas_count: 2, groups: [], here: { n: 3, total: 6 }, ideas_open: true, can_add: true,
  ideas: [idea("i1", "Pay custodians by a morning cash sweep"), idea("i2", "Hidden words", { anonymous: true, author: null })],
};
type Sess = Record<string, unknown>;

function mock(sess: Sess) {
  const posts: { url: string; body: Record<string, unknown> }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") { posts.push({ url, body: JSON.parse(String(init.body ?? "{}")) }); return json(200, { ok: true }); }
    if (url.includes("/session")) return json(200, url.includes("display=projector") ? { ...sess, ideas: [] } : sess);
    return json(200, {});
  }));
  return posts;
}
function view(path = "/centre/intent/bra-1/session") {
  return render(<MemoryRouter initialEntries={[path]}><Routes><Route path="/centre/intent/:intentId/:view" element={<SessionView />} /></Routes></MemoryRouter>);
}
afterEach(() => vi.unstubAllGlobals());

describe("live session", () => {
  it("shows the statement, the phase, the clock, North's prompt and one lane of ideas", async () => {
    mock(BASE as Sess); view();
    expect(await screen.findByText("Performance reviews take two weeks")).toBeInTheDocument();
    expect(screen.getByText("What are we thinking about:")).toBeInTheDocument();
    expect(screen.getByRole("timer")).toHaveTextContent("14:00");
    expect(screen.getByText("Everyone adds. No judging.")).toBeInTheDocument();
    expect(screen.getByText("North suggests")).toBeInTheDocument();
    expect(screen.getByText("Pay custodians by a morning cash sweep")).toBeInTheDocument();
    expect(screen.getByText("3 / 6 people")).toBeInTheDocument();
    expect(screen.queryByText("Move to group")).not.toBeInTheDocument(); // a participant has no controls
  });

  it("in Converge the clock is the time box, not a phase timer at zero", async () => {
    mock({ ...BASE, phase: "converge", remaining_seconds: null } as Sess); view();
    expect(await screen.findByTestId("count-until")).toHaveTextContent("The count stays open until Fri 9 Oct, 23:59.");
    expect(screen.queryByRole("timer")).not.toBeInTheDocument();
    expect(screen.getByText("3 / 6 people")).toBeInTheDocument();
  });

  it("an anonymous idea never shows a name, and Hide my name is offered only when the organiser allowed it", async () => {
    mock(BASE as Sess); view();
    const lane = await screen.findByTestId("lane");
    expect(within(lane).getByText("Anonymous")).toBeInTheDocument();
    expect(screen.queryByLabelText(/Hide my name/)).not.toBeInTheDocument();
  });

  it("offers Hide my name when allowed and adds an idea through the one box", async () => {
    const posts = mock({ ...BASE, anonymous_allowed: true } as Sess); view();
    fireEvent.change(await screen.findByLabelText("Add your idea"), { target: { value: "Score against worked examples" } });
    fireEvent.click(screen.getByLabelText(/Hide my name/));
    fireEvent.click(screen.getByRole("button", { name: "Add" }));
    await waitFor(() => expect(posts.some((p) => p.url.endsWith("/session/idea") && p.body.anonymous === true && p.body.text === "Score against worked examples")).toBe(true));
  });

  it("the organiser moves the phase only behind Are you sure", async () => {
    const posts = mock({ ...BASE, role: "organiser" } as Sess); view();
    fireEvent.click((await screen.findAllByRole("button", { name: "Move to group" }))[0]!);
    expect(posts).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Yes" }));
    await waitFor(() => expect(posts[0]).toMatchObject({ url: "/api/intents/bra-1/session/phase", body: { to: "group" } }));
  });

  it("a paused session is read only for everyone", async () => {
    mock({ ...BASE, paused: true } as Sess); view();
    expect(await screen.findByText("The session is paused.")).toBeInTheDocument();
    expect(screen.queryByLabelText("Add your idea")).not.toBeInTheDocument();
  });

  it("the group phase lists North's groups with counts; Group again waits for ideas", async () => {
    mock({ ...BASE, role: "organiser", phase: "group", ideas_count: 1, ideas: [idea("i1", "Sweep cash")], grouped_by_words: true, groups: [{ id: "g1", name: "Cash", by: "north", fallback: true, count: 1 }] } as Sess); view();
    expect(await screen.findByText("Groups so far")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Cash/ })).toHaveTextContent("1");
    expect(screen.getByText("Grouped by shared words, check it.")).toBeInTheDocument();
    expect(screen.getAllByText("Add ideas first").length).toBeGreaterThan(0);
  });

  it("the group phase still shows the add-idea form, and 'Led to' links the decisions", async () => {
    mock({ ...BASE, phase: "group", decided_in: [{ id: "dec-1", title: "Pick a custodian" }] } as Sess); view();
    expect(await screen.findByRole("textbox", { name: "Add your idea" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Pick a custodian" })).toHaveAttribute("href", "/centre/intent/dec-1");
    expect(screen.getByText(/Led to/)).toBeInTheDocument();
  });

  it("the projector shows the count and group names and no idea text", async () => {
    mock({ ...BASE, role: "organiser", phase: "group", groups: [{ id: "g1", name: "Cash", by: "north", fallback: true, count: 2 }] } as Sess); view();
    fireEvent.click(await screen.findByText("Projector view"));
    expect(await screen.findByTestId("idea-count")).toHaveTextContent("2");
    expect(screen.getByText("Cash")).toBeInTheDocument();
    expect(screen.getByTestId("join-box")).toHaveTextContent("/centre/intent/bra-1/session");
    expect(screen.queryByText("Pay custodians by a morning cash sweep")).not.toBeInTheDocument();
  });

  it("opening an idea shows its replies and the build on this field", async () => {
    mock({ ...BASE, ideas: [idea("i1", "Pay custodians by a morning cash sweep", { replies: [{ id: "r1", text: "Only for large balances", author: "Harvey Rowley", anonymous: false, at: "x", mine: false }] })] } as Sess);
    view("/centre/intent/bra-1/session?card=i1");
    expect(await screen.findByText("Only for large balances")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Add to this idea, do not judge it")).toBeInTheDocument();
  });
});

describe("before the session", () => {
  const before = { ...BASE, mode: "before", phase: "not_opened", state: "open", remaining_seconds: null, prompts: {}, ideas_count: null, here: null, ideas: [idea("m1", "My own idea", { mine: true })] };
  it("is private: only the person's own ideas, and the window note says so", async () => {
    mock(before as Sess); view();
    expect(await screen.findByText(/Think before Thu/)).toBeInTheDocument();
    expect(screen.getByText("My own idea")).toBeInTheDocument();
    expect(screen.getByText(/stay private until the session starts/)).toBeInTheDocument();
    expect(screen.getByText("Your ideas so far")).toBeInTheDocument();
  });
  it("an empty list reads One is enough, and the organiser sees counts only", async () => {
    mock({ ...before, ideas: [], role: "organiser", prethink: { authors: 4, ideas: 9, invited: 6 }, counts: { total: 6, invited: 3, accepted: 3, declined: 0 }, invited: [{ name: "Aaron Lyle", status: "Accepted", reason: null }], message: { subject: "Think with me", body: "Hello" } } as Sess); view();
    expect(await screen.findByText("No ideas yet. One is enough.")).toBeInTheDocument();
    expect(screen.getByText("4 of 6 invited have added ideas. 9 ideas.")).toBeInTheDocument();
    expect(screen.getByText("6 invited, 3 accepted, 0 declined")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy message" })).toBeInTheDocument();
  });
  it("an invited person sees the invitation card, and a decline needs a line", async () => {
    const posts = mock({ ...before, mode: "invitation", my_status: "Invited", ideas: [] } as Sess); view();
    expect(await screen.findByRole("button", { name: "Accept" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Decline" }));
    expect(screen.getByRole("button", { name: "Send my answer" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/One line on why/), { target: { value: "On leave" } });
    fireEvent.click(screen.getByRole("button", { name: "Send my answer" }));
    await waitFor(() => expect(posts[0]!.body).toMatchObject({ answer: "decline", reason: "On leave" }));
  });
  it("W2F2: a participant with no recorded answer is invited, never told they declined", async () => {
    mock({ ...before, mode: "declined", my_status: null, ideas: [] } as Sess); view();
    expect(await screen.findByRole("button", { name: "Accept" })).toBeInTheDocument();
    expect(screen.queryByText(/You declined this invitation/)).toBeNull();
  });

  it("W2F2: a closed brainstorm that never ran reads as closed: no invitation, no ideas box, no Open the session", async () => {
    mock({ ...before, state: "closed", role: "organiser", ideas: [] } as Sess); view();
    expect(await screen.findByText("This intent has closed. You can read the outcome.")).toBeInTheDocument();
    expect(screen.queryByText(/Your ideas so far/)).toBeNull();
    expect(screen.queryByRole("button", { name: /Open the session/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Accept" })).toBeNull();
  });
});

describe("start rules", () => {
  const today = new Date(2026, 9, 7); // a Wednesday
  it("the window skips weekends", () => {
    expect(windowOf("2026-10-15")).toEqual({ before: "2026-10-14", session: "2026-10-15", after: "2026-10-16" });
    expect(windowOf("2026-10-12").before).toBe("2026-10-09");
    expect(windowOf("2026-10-16").after).toBe("2026-10-19");
  });
  it("a session date is a working day from tomorrow", () => {
    expect(earliest(today)).toBe("2026-10-08");
    expect(dateOk("2026-10-08", today)).toBe(true);
    expect(dateOk("2026-10-07", today)).toBe(false);
    expect(dateOk("2026-10-10", today)).toBe(false);
  });
  it("names the first missing answer, and four to eight people", () => {
    const ok = { statement: "S", good_outcome: "G", people: ["a", "b", "c", "d"], areas: ["finance"], session_date: earliest(), session_time: "10:00", session_minutes: 60 };
    expect(firstMissing(ok)).toBe("");
    expect(firstMissing({ ...ok, statement: "" })).toMatch(/idea or the problem/);
    expect(firstMissing({ ...ok, people: ["a", "b", "c"] })).toBe("3 people picked. A Brainstorm needs four to eight.");
    expect(firstMissing({ ...ok, people: "abcdefghi".split("") })).toBe("9 people picked. Take one off.");
    expect(firstMissing({ ...ok, session_minutes: null })).toMatch(/45 or 60/);
  });
});
