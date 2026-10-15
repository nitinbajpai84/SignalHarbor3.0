import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import EventsView, { EventsLink, tidy, openPath } from "./views/EventsView";
import SearchFilters from "./SearchFilters";

// What happened (spec 16) in its five states, the stubs and drafts, the closed-only download; and the search region (spec 15).

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const line = (seq: number, over: object = {}) => ({
  seq, at: `2026-10-06T09:${String(10 + seq).padStart(2, "0")}:00Z`, kind: "card_added", group: "talk", status: "act", stage: "wall", who: "Aaron", person: "Aaron", anonymous: false,
  agent: null, sentence: "Aaron added a card to Processes", stub: null, confirms: null, corrects: null, superseded: false, ...over,
});
const PAGE = {
  items: [line(4, { kind: "closed", group: "opened_closed", who: "Janet", person: "Janet", sentence: "Janet closed the intent", confirms: 3 }),
    line(3, { kind: "north_drafted", group: "agent", status: "draft", agent: "north", who: "North (draft)", person: null, sentence: "North drafted the closure", confirmed_by: { seq: 4, name: "Janet", at: "2026-10-06T09:14:00Z" } }),
    line(2, { stub: "A sealed card was added", who: null, person: null, sentence: "A sealed card was added" }),
    line(1, { anonymous: true, who: "Anonymous", person: null, sentence: "Anonymous added a card to Processes" })],
  total: 4, visible: 4, next: null, last_seq: 4, mode: "full", zone: "UTC", download: false,
  groups: [{ key: "opened_closed", name: "Opened and closed", count: 1 }, { key: "talk", name: "Talk", count: 3 }, { key: "agent", name: "Agent drafts", count: 1 }],
  stages: [{ key: "before_first_stage", name: "Before the first stage", count: 0 }, { key: "wall", name: "Wall", count: 4 }],
  summary: { by_group: {}, people: [{ name: "Aaron", count: null, few: true }], anonymous: 1, drafts: 1, acts: 2 }, intent: { title: "Agree what we want to know", state: "open", type: "brainstorm" },
};

function show(respond: (url: string) => Response) {
  const f = vi.fn(async (url: string) => respond(String(url)));
  vi.stubGlobal("fetch", f);
  render(<MemoryRouter initialEntries={["/centre/intent/i1/events"]}><Routes><Route path="/centre/intent/:intentId/events" element={<EventsView />} /></Routes></MemoryRouter>);
  return f;
}

describe("What happened", () => {
  it("shows the timeline, a draft chip, a stub, an anonymous line, and no download while open", async () => {
    show(() => json(200, PAGE));
    expect(await screen.findByText("Janet closed the intent")).toBeTruthy();
    expect(screen.getByText("Draft by North")).toBeTruthy();
    expect(screen.getByText("A sealed card was added")).toBeTruthy();
    expect(screen.getByText("Anonymous added a card to Processes")).toBeTruthy();
    expect(screen.getByText("This is a record. It cannot be changed.")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Download transcript" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getAllByText("Tuesday 6 October").length).toBeGreaterThan(0);
  });

  it("asks the server again when a kind chip is turned off", async () => {
    const f = show(() => json(200, PAGE));
    await screen.findByText("Janet closed the intent");
    await userEvent.click(screen.getAllByRole("button", { name: /^Talk/ })[0]!);
    await waitFor(() => expect(f.mock.calls.some(([u]) => String(u).includes("kind=opened_closed%2Cagent"))).toBe(true));
    expect(screen.getAllByRole("button", { name: "Clear filters" }).length).toBeGreaterThan(0);
  });

  it("says so when nothing happened yet", async () => {
    show((u) => u.includes("/events") ? json(200, { ...PAGE, items: [], total: 0, visible: 0, groups: PAGE.groups.map((g) => ({ ...g, count: 0 })), summary: { ...PAGE.summary, people: [], anonymous: 0 } }) : json(200, { created_at: "2026-09-01T02:00:00Z" }));
    expect(await screen.findByText("History starts on 1 September 2026; earlier steps were not recorded.")).toBeTruthy();
  });

  it("tidies raw keys and legacy kinds, and each line opens its screen", () => {
    expect(tidy({ kind: "signed", who: "Marcus", sentence: "Marcus signed the root_cause" })).toBe("Marcus signed the root cause");
    expect(tidy({ kind: "closure_signed", who: "Janet", sentence: "Janet: closure signed" })).toBe("Janet signed the closing summary");
    expect(openPath({ kind: "person_invited", sentence: "" }, "i1")).toBe("/centre/intent/i1/people");
    expect(openPath({ kind: "card_added", sentence: "" }, "i1")).toBe("/centre/intent/i1");
  });

  it("shows the link with the count, and nothing when the history is shut", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(200, { visible: 7 })));
    const { unmount } = render(<MemoryRouter><EventsLink intentId="i1" /></MemoryRouter>);
    expect(await screen.findByText("What happened (7)")).toBeTruthy();
    unmount();
    vi.stubGlobal("fetch", vi.fn(async () => json(403, { message: "no" })));
    render(<MemoryRouter><EventsLink intentId="i1" /></MemoryRouter>);
    await waitFor(() => expect(screen.queryByText(/What happened/)).toBeNull());
  });

  it("offers the transcript once the intent is closed", async () => {
    show(() => json(200, { ...PAGE, download: true }));
    await userEvent.click(await screen.findByRole("button", { name: "Download transcript" }));
    expect(screen.getByRole("button", { name: "Download Markdown" })).toBeTruthy();
    expect(screen.getByText(/Transcript of: Agree what we want to know/)).toBeTruthy();
  });

  it("shows milestones and counts only to the company admin, with no download", async () => {
    show(() => json(200, { ...PAGE, mode: "milestones", download: false, summary: { ...PAGE.summary, people: [], anonymous: 0 } }));
    expect((await screen.findAllByText("Milestones and counts only.")).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Download transcript" })).toBeNull();
  });

  it("handles a refusal and a failure in plain words", async () => {
    show(() => json(403, { detail: "no" }));
    expect(await screen.findByText("The history is open to the people in this intent.")).toBeTruthy();
  });
  it("offers another try when the history does not load", async () => {
    show(() => json(500, {}));
    expect(await screen.findByRole("button", { name: "Try again" })).toBeTruthy();
  });
});

describe("Search region", () => {
  const FACETS = { type: { brainstorm: 1 }, state: { open: 1 }, area: { Operations: 1 }, role: { participant: 1 }, timebox: { running: 1 }, outcome: {}, rated: { not_rated: 1 } };
  const CARD = { id: "i1", type: "brainstorm", title: "Onboarding review", title_private: false, state: "open", stage_name: "Wall", areas: ["Operations"], people_count: 3, can_open: false,
    purpose: "Find the slow steps", organiser: "Janet", outcome_text: null, rating: { n: 0, avg: null }, match: { field: "purpose", snippet: "Find the slow steps" },
    timebox: { status: "running", ends: "2026-10-09", closed_at: null, cancelled_at: null, days_left: 2, extended: false } };
  const result = (items: unknown[], visible = items.length) => ({ items, total: items.length, total_visible: visible, next_cursor: null, facets: FACETS, index: { built_at: "2026-10-07T09:14:00Z", rows: visible } });
  const mount = (body: unknown) => {
    const f = vi.fn(async () => json(200, body));
    vi.stubGlobal("fetch", f);
    render(<MemoryRouter initialEntries={["/centre/intent"]}><SearchFilters view="home" /></MemoryRouter>);
    return f;
  };

  it("shows a card with its access line and the exact empty copy", async () => {
    mount(result([CARD]));
    expect(await screen.findByText("Onboarding review")).toBeTruthy();
    expect(screen.getByText("You can see that this exists. Ask the organiser to add you to open it.")).toBeTruthy();
    expect(screen.getByText("View summary")).toBeTruthy();
  });
  it("says nothing is running when the viewer has no intents", async () => {
    mount(result([], 0));
    expect(await screen.findByText("Nothing is running that you can see.")).toBeTruthy();
  });
  it("sends a chip as a filter and shows the no-match copy", async () => {
    const f = mount(result([CARD]));
    await screen.findByText("Onboarding review");
    f.mockImplementation(async () => json(200, result([], 1)));
    await userEvent.click(screen.getAllByRole("button", { name: /^Initiative|^Brainstorm/ })[0]!);
    expect(await screen.findByText("No intent matches these filters.")).toBeTruthy();
    expect(String((f.mock.calls.at(-1) as unknown[])[0])).toContain("type=");
  });
});
