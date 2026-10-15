import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import type { BoardCluster, BoardNote, BoardView, CharterDoc } from "./api";
import BoardScreen from "./board/BoardScreen";
import CharterPaper from "./CharterPaper";
import { m1Board as board, m1Charter as charter, m1Notes as n } from "./copy";
import NoteForm from "./private_room/NoteForm";
import type { FormField, KindInfo, Room, RoomNote } from "./private_room/roomApi";

// The four kinds of note: the note form (kind choice, the kind's own details, North's suggestion, the pack's labelled
// suggestions, names open or anonymous), the board (one tab for each kind) and the charter (four lists). fetch is stubbed.
// Family-office example wording only.

const SID = "c".repeat(32);
const BASE = `/api/modules/m1_intent/sessions/${SID}`;
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const field = (id: string, label: string, over: Partial<FormField> = {}): FormField => ({
  id, label, kind: "text", ask: "", required: false, person_only: false, guess: false, ...over,
});
const FORM = [field("problem", "The problem", { required: true }), field("purpose", "The business purpose"), field("affected", "Who is affected", { kinds: ["intent"] })];
const KINDS: KindInfo[] = [
  { id: "intent", label: "Something we intend to do now", heading: "Problems to solve now", ask: "", fields: [] },
  { id: "pain_point", label: "Something that hurts today", heading: "Pain points", ask: "", fields: [field("who", "Who is affected"), field("how_often", "How often")] },
  { id: "future_signal", label: "Something to watch in future", heading: "What to track for the future", ask: "", fields: [field("source", "Outside or market signal")] },
  { id: "lever", label: "A lever we change", heading: "Levers for what-if", ask: "", fields: [field("moves", "KPIs it moves")] },
];
const NORTH: Room["north"] = { practice_on: false, library_on: false, available: true };
const note = (over: Partial<RoomNote> = {}): RoomNote => ({
  id: "n1", text: "Month end takes two days", state: "draft", source: { kind: "typed" }, priority: null, practice: null, practice_added: [],
  created_at: "x", updated_at: "x", fields: {}, labels_suggested: [], anonymous: false, kind: "intent", missing: [], ...over,
});
const room = (notes: RoomNote[]): Room => ({ open: true, message: null, title: "t", turns: [], notes, form: FORM, kinds: KINDS, north: NORTH });
const calls: { method: string; url: string; body: unknown }[] = [];

function stub(answer: Room | null = null) {
  calls.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ method: init?.method ?? "GET", url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    return answer ? json(200, answer) : json(404, {});
  }));
}
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});
const form = (n1: RoomNote, over: Partial<React.ComponentProps<typeof NoteForm>> = {}) =>
  render(<NoteForm sessionId={SID} note={n1} form={FORM} open northAvailable onRoom={() => undefined} kinds={KINDS} names="choice" north={NORTH} {...over} />);

describe("the note form: kinds", () => {
  test("offers the four kinds in plain words, intent first and chosen by default", () => {
    stub();
    form(note());
    const group = screen.getByRole("group", { name: n.kindLegend });
    const labels = within(group).getAllByRole("radio").map((r) => r.closest("label")?.textContent);
    expect(labels).toEqual(KINDS.map((k) => k.label));
    expect(screen.getByRole("radio", { name: KINDS[0]!.label })).toBeChecked();
  });

  test("choosing a kind saves it", async () => {
    const user = userEvent.setup();
    stub(room([note({ kind: "lever" })]));
    form(note());
    await user.click(screen.getByRole("radio", { name: "A lever we change" }));
    await waitFor(() => expect(calls[0]).toMatchObject({ method: "POST", url: `${BASE}/room/notes/n1`, body: { kind: "lever" } }));
  });

  test.each([
    ["pain_point", ["Who is affected", "How often"], ["KPIs it moves", "Outside or market signal"]],
    ["future_signal", ["Outside or market signal"], ["Who is affected", "KPIs it moves"]],
    ["lever", ["KPIs it moves"], ["Who is affected", "Outside or market signal"]],
  ] as const)("a %s note shows its own details and not another kind's", (kind, shown, hidden) => {
    stub();
    form(note({ kind }));
    for (const label of shown) expect(screen.getByLabelText(new RegExp(`^${label}`))).toBeInTheDocument();
    for (const label of hidden) expect(screen.queryByLabelText(new RegExp(`^${label}`))).toBeNull();
  });

  test("an intent note keeps the fields it always had", () => {
    stub();
    form(note());
    expect(screen.getByLabelText(/^Who is affected/)).toBeInTheDocument();
    expect(screen.getByLabelText(/^The business purpose/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/^KPIs it moves/)).toBeNull();
  });

  test("a note with no kind (an older one) reads as an intent", () => {
    stub();
    form(note({ kind: undefined }));
    expect(screen.getByRole("radio", { name: KINDS[0]!.label })).toBeChecked();
  });

  test("North's kind is a labelled suggestion; the person decides", async () => {
    const user = userEvent.setup();
    stub(room([note({ kind: "lever" })]));
    form(note({ kind_suggested: "lever" }));
    expect(screen.getByText(n.kindSuggested("A lever we change"))).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: KINDS[0]!.label })).toBeChecked(); // not changed by the suggestion
    await user.click(screen.getByRole("button", { name: n.kindUse }));
    await waitFor(() => expect(calls[0]).toMatchObject({ body: { kind: "lever" } }));
  });

  test("the pack's suggestions are labelled as suggestions; no pack gives an honest empty state", () => {
    stub();
    const { unmount } = form(note({ kind: "pain_point" }), {
      north: { ...NORTH, suggestions: { pain_point: ["Reports arrive late"] }, suggestions_label: "Industry practice (suggestion)" },
    });
    expect(screen.getByText("Industry practice (suggestion)")).toBeInTheDocument();
    expect(screen.getByText("Reports arrive late")).toBeInTheDocument();
    unmount();
    form(note({ kind: "pain_point" }), { north: { ...NORTH, suggestions: {}, suggestions_empty: "There are no industry suggestions for your industry yet. Please write in your own words." } });
    expect(screen.getByText(/no industry suggestions for your industry yet/)).toBeInTheDocument();
    expect(screen.queryByText("Reports arrive late")).toBeNull();
  });

  test("the anonymous choice is there only when each person chooses", () => {
    stub();
    const { unmount } = form(note({ kind: "lever" }), { names: "choice" });
    expect(screen.getByRole("radio", { name: new RegExp(`^${n.anonymous}`) })).toBeInTheDocument();
    unmount();
    const open = form(note({ kind: "lever" }), { names: "named" });
    expect(screen.queryByRole("radio", { name: new RegExp(`^${n.anonymous}`) })).toBeNull();
    expect(screen.getByText(n.namesNamed)).toBeInTheDocument();
    open.unmount();
    form(note({ kind: "lever" }), { names: "anonymous" });
    expect(screen.queryByRole("radio", { name: new RegExp(`^${n.byName}`) })).toBeNull();
    expect(screen.getByText(n.namesAnonymous)).toBeInTheDocument();
  });

  test("a submitted note's kind cannot be changed", () => {
    stub();
    form(note({ state: "submitted", kind: "pain_point" }));
    expect(screen.getByRole("radio", { name: "Something that hurts today" })).toBeDisabled();
  });
});

// ---- the board: one tab for each kind
const bnote = (id: string, text: string, kind: BoardNote["kind"], over: Partial<BoardNote> = {}): BoardNote => ({ id, text, kind, anonymous: false, mine: false, ...over });
const cluster = (id: string, name: string, kind: BoardCluster["kind"], notes: BoardNote[]): BoardCluster => ({
  id, name, kind, source: "north", reasoning: "", note_ids: notes.map((x) => x.id), notes,
});
const PAIN = cluster("c1", "Meeting pack effort", "pain_point", [bnote("n1", "The meeting pack takes two days", "pain_point", { author_name: "Ada" }), bnote("n2", "The pack is late", "pain_point", { anonymous: true })]);
const LEVER = cluster("c2", "Commitment pace", "lever", [bnote("n3", "We can commit in steps", "lever", { author_name: "Ben" }), bnote("n4", "We can pace commitments", "lever", { anonymous: true })]);
const ALONE = bnote("n5", "Know our headroom weekly", "intent", { author_name: "Ada" });
const view = (): BoardView => ({
  stage: "board", paused_from: null, organiser: true, status: "done", can_edit: true, can_restore: false, edited: false,
  kinds: KINDS.map((k) => ({ id: k.id, heading: k.heading })),
  counts: { notes: 5, clusters: 2, on_its_own: 1 }, by_kind: { intent: 1, pain_point: 2, future_signal: 0, lever: 2 },
  clusters: [PAIN, LEVER], on_its_own: [ALONE],
});
const openBoard = () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => (url === `${BASE}/board` ? json(200, view()) : url === `${BASE}/timer` ? json(200, { stage: "board", timed: false, now: "z" }) : json(404, {}))));
  return render(<MemoryRouter initialEntries={[`/s/${SID}`]}><Routes><Route path="/s/:sessionId" element={<BoardScreen />} /></Routes></MemoryRouter>);
};

describe("the board: kinds", () => {
  test("has one tab for each kind with its count, and shows every kind by default", async () => {
    openBoard();
    expect(await screen.findByRole("button", { name: board.kindCount(board.kindAll, 5) })).toHaveAttribute("aria-pressed", "true");
    for (const [heading, count] of [["Problems to solve now", 1], ["Pain points", 2], ["What to track for the future", 0], ["Levers for what-if", 2]] as const) {
      expect(screen.getByRole("button", { name: board.kindCount(heading, count) })).toBeInTheDocument();
    }
    expect(screen.getAllByText("Meeting pack effort").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Commitment pace").length).toBeGreaterThan(0);
  });

  test("a tab shows only the groups and notes of that kind", async () => {
    const user = userEvent.setup();
    openBoard();
    await user.click(await screen.findByRole("button", { name: board.kindCount("Levers for what-if", 2) }));
    expect(screen.getAllByText("Commitment pace").length).toBeGreaterThan(0);
    expect(screen.queryByRole("heading", { name: "Meeting pack effort" })).toBeNull();
    expect(screen.queryByText("Know our headroom weekly")).toBeNull();
    await user.click(screen.getByRole("button", { name: board.kindCount("What to track for the future", 0) }));
    expect(screen.getByText(board.kindNone)).toBeInTheDocument();
  });

  test("an anonymous note of any kind shows no name; a named one does", async () => {
    openBoard();
    await screen.findByText("The pack is late");
    expect(screen.queryByText(/Ada.*anonymous/i)).toBeNull();
    expect(screen.getAllByText(new RegExp("Ada")).length).toBeGreaterThan(0);
    const late = screen.getByText("The pack is late").closest("li")!;
    expect(within(late).queryByText(/Ada|Ben/)).toBeNull();
    const steps = screen.getByText("We can pace commitments").closest("li")!;
    expect(within(steps).queryByText(/Ada|Ben/)).toBeNull();
  });

  test("an older server with no kinds shows the board as before, with no tabs", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => (url === `${BASE}/board` ? json(200, { ...view(), kinds: undefined }) : json(404, {}))));
    render(<MemoryRouter initialEntries={[`/s/${SID}`]}><Routes><Route path="/s/:sessionId" element={<BoardScreen />} /></Routes></MemoryRouter>);
    expect((await screen.findAllByText("Meeting pack effort")).length).toBeGreaterThan(0);
    expect(screen.queryByRole("group", { name: board.kindFilter })).toBeNull();
  });
});

// ---- the charter: four lists
const doc = (over: Partial<CharterDoc> = {}): CharterDoc => ({
  version: 1, template: { id: "standard", name: "Standard charter", columns: ["problem", "purpose", "priority", "notes"] },
  problems: [
    { title: "Know our funding headroom", priority_label: "Must", so_that: null, note_count: 3, kind: "intent" },
    { title: "The pack takes two days", priority_label: "Should", so_that: null, note_count: 2, kind: "pain_point", details: [{ label: "Who is affected", values: ["The finance team"] }, { label: "How often", values: ["Every month"] }] },
    { title: "How fast we commit", priority_label: "Could", so_that: null, note_count: 1, kind: "lever", details: [{ label: "KPIs it moves", values: ["Funding headroom"] }] },
  ],
  lists: KINDS.map((k) => ({ kind: k.id, heading: k.heading })), later: [],
  alone: [{ text: "A named idea", kind: "intent", author_name: "Ada" }, { text: null, kind: "lever" }],
  footer: { date: "2026-10-04", participants: 2, notes: 6, later: 0 }, ...over,
});

describe("the charter paper: four lists", () => {
  test("shows the four headings in order, each problem under its own list with its priority and details", () => {
    render(<CharterPaper doc={doc()} status="signed" />);
    const headings = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
    expect(headings.slice(0, 4)).toEqual(["Problems to solve now", "Pain points", "What to track for the future", "Levers for what-if"]);
    expect(screen.getByText("Who is affected: The finance team")).toBeInTheDocument();
    expect(screen.getByText("KPIs it moves: Funding headroom")).toBeInTheDocument();
    expect(screen.getByText("Should")).toBeInTheDocument();
    expect(screen.getByText("Could")).toBeInTheDocument();
  });

  test("an empty list says none were raised", () => {
    render(<CharterPaper doc={doc()} status="signed" />);
    const future = screen.getByRole("heading", { name: "What to track for the future" }).parentElement!;
    expect(within(future).getByText(charter.noneRaised)).toBeInTheDocument();
  });

  test("a charter with no lists (drafted before kinds) is one list of problems", () => {
    render(<CharterPaper doc={doc({ lists: undefined, problems: [{ title: "Old problem", priority_label: "Must", so_that: null, note_count: 1 }] })} status="signed" />);
    expect(screen.getByText("Old problem")).toBeInTheDocument();
    expect(screen.queryByText(charter.noneRaised)).toBeNull();
  });

  test("a note left on its own shows its author's name only when it was posted by name", () => {
    render(<CharterPaper doc={doc()} status="signed" />);
    expect(screen.getByText(/A named idea \(by Ada\)/)).toBeInTheDocument();
    expect(screen.getByText(charter.leftAnonymous)).toBeInTheDocument();
  });

  test("no problem ticked still says so", () => {
    render(<CharterPaper doc={doc({ problems: [] })} status="draft" />);
    expect(screen.getByText(charter.nothingTicked)).toBeInTheDocument();
  });
});
