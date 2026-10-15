import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../theme";
import WeekView from "./views/WeekView";

// Weekly check-in entry (spec 39). fetch is stubbed with synthetic data.

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const entry = (over = {}) => ({
  week: { week_key: "2026-W41", opens: "2026-10-05", answers_close: "2026-10-07", review_day: "2026-10-08", closes: "2026-10-09", state: "collect" }, title: "Check-in: Operations", area: "Operations",
  prompts: [{ kind: "ran", lead: "What ran well this week?" }, { kind: "broke", lead: "What broke or nearly broke?" }, { kind: "thought", lead: "What is on your mind?" }],
  participant: true, can_edit: true, status: "none", submitted_at: null, skipped: [], active_seconds: 0, items: [], withdrawn: 0, guessed: 0, next_week_opens: null, has_newer: false, series_status: "running", measures: [], ...over,
});
function mock(e = entry(), drafts: unknown[] = []) {
  const puts: Record<string, unknown>[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "PUT") { puts.push(JSON.parse(String(init.body))); return json(200, e); }
    if (url.includes("/pulse/prefill")) return json(200, { drafts, count: drafts.length });
    if (url.includes("/pulse/mine")) return json(200, { weeks: [], trend: null, minutes: [] });
    if (url.includes("/pulse/entry")) return json(200, e);
    return json(200, {});
  }));
  return puts;
}
const view = () => render(<ThemeProvider><MemoryRouter initialEntries={["/centre/intent/i1/week"]}><Routes><Route path="/centre/intent/:intentId/:view" element={<WeekView />} /></Routes></MemoryRouter></ThemeProvider>);
afterEach(() => vi.unstubAllGlobals());

test("three questions, nothing chosen for the person, send is off until one is answered", async () => {
  mock(); view();
  expect(await screen.findByText("What ran well this week?")).toBeTruthy();
  expect(screen.getByText("What broke or nearly broke?")).toBeTruthy();
  expect(screen.getByText("What is on your mind?")).toBeTruthy();
  expect((screen.getByRole("button", { name: "Send my week" }) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getByText("Answer one of the three, or say nothing to add.")).toBeTruthy();
});

test("North's drafts are marked guessed and a line is added in the person's own words", async () => {
  const puts = mock(entry(), [{ id: "run:x", kind: "ran", text: "Mailbox: 5 of 5 loads on time", evidence: "From 5 runs, 2 to 6 Oct", label: "Guessed by North, from this week's run log", from: [] }]);
  view();
  expect(await screen.findByText("Mailbox: 5 of 5 loads on time")).toBeTruthy();
  expect(screen.getByText("Guessed by North, from this week's run log")).toBeTruthy();
  fireEvent.change(screen.getAllByPlaceholderText("One line, in your words")[0]!, { target: { value: "Capital calls on time" } });
  fireEvent.click(screen.getAllByRole("button", { name: "Add" })[0]!);
  await screen.findAllByText("North drafted 1 line from this week's runs and alerts. Keep, change, or drop each.");
  expect(puts.some((p) => p.op === "add" && p.kind === "ran" && p.text === "Capital calls on time")).toBe(true);
});

test("after answers close the late line shows and nothing can be added", async () => {
  mock(entry({ can_edit: false, week: { ...entry().week, state: "review" } })); view();
  expect(await screen.findByText("This week's answers have closed. Your answer can no longer be added.")).toBeTruthy();
  expect(screen.queryByPlaceholderText("One line, in your words")).toBeNull();
});
