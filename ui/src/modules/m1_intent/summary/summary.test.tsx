import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import type { SummaryPage } from "../api";
import { m1Summary as T } from "../copy";
import SummaryScreen from "./SummaryScreen";

// The five states of the summary page, the empty sections, anonymous notes and the three names rules.

const SID = "d".repeat(32);
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const BOARD = {
  stage: "closed", paused_from: null, organiser: true, status: "done", can_edit: false, can_restore: false, edited: false,
  counts: { notes: 2, clusters: 1, on_its_own: 0 }, on_its_own: [],
  clusters: [{ id: "c1", name: "Calls arrive too late", source: "north", reasoning: "", note_ids: ["n1", "n2"], notes: [
    { id: "n1", text: "Capital calls reach us late", anonymous: false, mine: false, author_name: "Ada Guest" },
    { id: "n2", text: "We hear by email", anonymous: true, mine: false }] }],
};
const base = (): SummaryPage => ({
  session: { title: "Agree what we want to know", date: "2026-10-04", stage: "closed", names: "choice", people: [{ name: "Ada Guest", role: "Planner" }, { name: "Ben Guest", role: "Treasurer" }], people_count: 2 },
  intent: [{ id: "must", label: "Must", items: [{ id: "c1", name: "Calls arrive too late", note_count: 2, vote_total: 2 }] },
    { id: "should", label: "Should", items: [] }, { id: "could", label: "Could", items: [] }, { id: "not_this_time", label: "Not this time", items: [] },
    { id: "open", label: "Not decided yet", items: [] }],
  pain_points: [], future_signals: [], levers: [],
  board: BOARD as unknown as SummaryPage["board"], charter: null, can_download: false,
  contributions: { mode: "choice", totals: { notes: 2, comments: 1, votes: 2 },
    people: [{ name: "Ada Guest", role: "Planner", notes: 1, comments: 1, votes: 1 }, { name: "Ben Guest", role: "Treasurer", notes: 0, comments: 0, votes: 1 }],
    anonymous: { notes: 1, comments: 0, total: 1 } },
});

function show(respond: () => Response) {
  vi.stubGlobal("fetch", vi.fn(async () => respond()));
  render(
    <MemoryRouter initialEntries={[`/modules/m1_intent/sessions/${SID}/summary`]}>
      <Routes>
        <Route path="/modules/m1_intent/sessions/:sessionId/summary" element={<SummaryScreen />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => vi.unstubAllGlobals());

it("shows loading, then the sections in order, with empty ones saying so", async () => {
  show(() => json(200, base()));
  expect(screen.getByRole("status")).toBeInTheDocument();
  await screen.findByText(T.intent);
  const heads = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
  expect(heads).toEqual(["Agree what we want to know", T.intent, T.painPoints, T.future, T.levers, T.board, T.charter, T.contributed]);
  expect(screen.getAllByText(T.none).length).toBeGreaterThanOrEqual(3); // pain points, signals, levers (and the empty priorities)
  expect(screen.getByRole("button", { name: T.print })).toBeInTheDocument();
});

it("names an anonymous note as an anonymous note and keeps its author out", async () => {
  show(() => json(200, base()));
  await screen.findByText(T.board);
  expect(screen.getByText(`(${T.anonymousNote})`)).toBeInTheDocument();
  expect(screen.getByText(T.anonymousTotal(1))).toBeInTheDocument();
});

it("shows only totals when the session keeps names private", async () => {
  const d = base();
  d.contributions = { mode: "anonymous", totals: d.contributions.totals, people: null, anonymous: null };
  show(() => json(200, d));
  await screen.findByText(T.anonymousHidden);
  expect(screen.queryByRole("table")).toBeNull();
  expect(screen.queryByText(/Anonymous:/)).toBeNull();
});

it("lists no names in a small group where some notes are anonymous, and still shows the anonymous total", async () => {
  const d = base();
  d.contributions = { ...d.contributions, people: null, small_group: true };
  show(() => json(200, d));
  await screen.findByText(T.smallGroup);
  expect(screen.queryByRole("table")).toBeNull();
  expect(screen.getByText(T.anonymousTotal(1))).toBeInTheDocument();
});

it("shows every person openly, with no anonymous line, when the session is named", async () => {
  const d = base();
  d.contributions = { ...d.contributions, mode: "named", anonymous: null };
  show(() => json(200, d));
  await screen.findByRole("table");
  expect(screen.getByRole("rowheader", { name: /Ada Guest/ })).toBeInTheDocument();
  expect(screen.queryByText(/Anonymous:/)).toBeNull();
});

it("shows the pain points with their own fields", async () => {
  const d = base();
  d.pain_points = [{ text: "Cash is found late", anonymous: false, author_name: "Ada Guest", details: [{ label: T.who, values: ["Treasury"] }, { label: T.kpi, values: ["Cash headroom"] }] }];
  show(() => json(200, d));
  await screen.findByText(/Cash is found late/);
  expect(screen.getByText(`${T.who}: Treasury`)).toBeInTheDocument();
  expect(screen.getByText(`${T.kpi}: Cash headroom`)).toBeInTheDocument();
});

it("shows no empty brackets for a named note with no name", async () => {
  const d = base();
  d.levers = [{ text: "Commit in smaller steps", anonymous: false, details: [] }];
  show(() => json(200, d));
  await screen.findByText(/Commit in smaller steps/);
  expect(screen.queryByText("()")).toBeNull();
});

it("says plainly when the rooms have not closed (refused) and offers to retry on an error", async () => {
  show(() => json(409, { error: "wrong_state", message: "The summary is ready once the private rooms have closed." }));
  expect(await screen.findByText(/ready once the private rooms have closed/)).toBeInTheDocument();
});

it("shows an error with a way to try again", async () => {
  show(() => json(500, { error: "x" }));
  expect(await screen.findByRole("alert")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /try again/i }));
});
