import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import type { StartProps } from "../IntentNew";
import CheckinStart from "../start/CheckinStart";
import WeekView from "../views/WeekView";

// F16: the setup's question 3 reads once, the still-to-answer line is plain words, and a refused record is quiet. Synthetic data.

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const setup = {
  areas: [{ id: "fund-operations", name: "Fund Operations", kind: "operations_area" }],
  people: [{ id: "acc-a", name: "Aaron Lyle", role: null, tagged: true, has_account: true }, { id: "acc-h", name: "Harvey Rowley", role: null, tagged: true, has_account: true }],
  minimum: 2, extra_max: 240, area: null, reporters: [], close_day: "fri", reviewer: "acc-a",
  preview: { opens: "2026-10-12", answers_close: "2026-10-14", review_day: "2026-10-15", closes: "2026-10-16", next_opens: "2026-10-19", weekday: "Monday" },
};
afterEach(() => vi.unstubAllGlobals());

test("question 3 shows its heading once and the still-to-answer line names what is open in plain words", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(200, { organiser: true, setup })));
  render(<ThemeProvider><MemoryRouter><CheckinStart {...({ type: "pulse", draftId: "d1" } as StartProps)} /></MemoryRouter></ThemeProvider>);
  expect(await screen.findByText("Still to answer: the ops area and at least 2 people who report.")).toBeTruthy();
  fireEvent.click(screen.getByText("Fund Operations"));
  expect(await screen.findByText("Still to answer: at least 2 people who report.")).toBeTruthy();
  fireEvent.click(screen.getAllByRole("button", { name: "Change" })[1]!); // open question 3
  expect(screen.getAllByText("Which day does the week close?")).toHaveLength(1);
});

test("a 403 on the record is a quiet line with no Try again", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(403, { message: "The record opens when answers close.", error: "not_allowed" })));
  render(<ThemeProvider><MemoryRouter initialEntries={["/centre/intent/i1/week?view=record"]}><Routes><Route path="/centre/intent/:intentId/:view" element={<WeekView />} /></Routes></MemoryRouter></ThemeProvider>);
  expect(await screen.findByText("The record opens when answers close.")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  expect(screen.queryByRole("alert")).toBeNull();
});

test("answers closed before the week closes reads as answers closed, not closed", async () => {
  const week = { week_key: "2026-W41", opens: "2026-10-05", answers_close: "2026-10-06", review_day: "2026-10-07", closes: "2026-10-08", state: "review" };
  vi.stubGlobal("fetch", vi.fn(async (u: string) => json(200, String(u).includes("/pulse/entry") ? { week, title: "T", area: "Technology", prompts: [], participant: true, can_edit: false, status: "closed",
    submitted_at: "2026-10-06T08:00:00Z", skipped: [], active_seconds: 0, items: [], withdrawn: 0, guessed: 0, next_week_opens: null, has_newer: false, series_status: "active" } : { weeks: [] })));
  render(<ThemeProvider><MemoryRouter initialEntries={["/centre/intent/i1/week"]}><Routes><Route path="/centre/intent/:intentId/:view" element={<WeekView />} /></Routes></MemoryRouter></ThemeProvider>);
  expect(await screen.findByText("Answers are closed")).toBeTruthy();
  expect(screen.queryByText("This week is closed")).toBeNull();
});
