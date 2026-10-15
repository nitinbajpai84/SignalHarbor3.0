import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, test, vi } from "vitest";

import StageClock, { type ClockPart, type ClockView } from "./StageClock";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const part = (o: Partial<ClockPart>): ClockPart => ({
  starts: "2026-10-05T09:00:00+00:00", ends: "2026-10-19T09:00:00+00:00", working_days_total: 10, working_days_left: 8, hours_left: 192,
  percent_left: 80, state: "on_time", extensions: 0, day_of: 3, unit: "days", ...o,
});
const view = (o: Partial<ClockView> = {}): ClockView => ({
  id: "i1", state: "open", tz: "UTC", started: true, box: part({}), stage: part({ working_days_left: 3, ends: "2026-10-10T09:00:00+00:00" }),
  stages: [{ key: "wall", name: "Think unfiltered", status: "done", due: null }, { key: "define", name: "Define strategically", status: "current", due: "2026-10-10T09:00:00+00:00" },
    { key: "build_ready", name: "Build-ready", status: "later", due: null }],
  extensions: { count: 0, show_reason: true, list: [], latest: null }, pending: null, can_extend: true, may_act: true, can_decide: false,
  approval: { needed: false, approver: "Daniel Kerr (sponsor)" }, single_stage: false, day_choices: [1, 2, 3, 5], reason_min: 10, reason_max: 300, ...o,
});
const posts: { url: string; body: unknown }[] = [];
function mock(v: ClockView) {
  posts.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      posts.push({ url, body: JSON.parse(String(init.body)) });
      return json(200, {});
    }
    return json(200, v);
  }));
}
afterEach(() => vi.unstubAllGlobals());

describe("StageClock", () => {
  test("a Decision with one deadline shows one chip; a stage that ends earlier is labelled, not a second unlabelled limit", async () => {
    mock(view({ stage: part({ working_days_left: 8, ends: "2026-10-19T09:00:00+00:00" }) }));
    const { unmount } = render(<StageClock intentId="i1" />);
    await screen.findByText("8 days left · Day 3 of 10");
    expect(screen.queryByText("This step: ")).toBeNull();
    unmount();
    mock(view({ stage: part({ state: "overdue", hours_left: -6, words: "Overdue by 6 hours", ends: "2026-10-07T03:00:00+00:00" }) }));
    render(<StageClock intentId="i1" />);
    expect(await screen.findByText("This step:")).toBeTruthy();
    expect(screen.getByText("Whole intent:")).toBeTruthy();
  });

  test("shows days left, the day of the box and the current step", async () => {
    mock(view());
    render(<StageClock intentId="i1" />);
    expect(await screen.findByText("8 days left · Day 3 of 10")).toBeTruthy();
    expect(screen.getByText("3 days left")).toBeTruthy();
    expect(screen.getByText("Define strategically", { selector: "li" }).getAttribute("aria-current")).toBe("step");
  });

  test("colour: neutral, amber at half, red at a fifth, solid with the word Overdue; the text carries the state", async () => {
    const cases: [Partial<ClockPart>, string, string][] = [
      [{}, "8 days left · Day 3 of 10", ""],
      [{ state: "at_half", working_days_left: 5 }, "5 days left · Day 3 of 10", "sc__chip--amber"],
      [{ state: "at_risk", working_days_left: 2 }, "2 days left · Day 3 of 10", "sc__chip--red"],
      [{ state: "overdue", working_days_left: 0, hours_left: -48 }, "Overdue by 2 working days · Day 3 of 10", "sc__chip--over"],
    ];
    for (const [o, text, cls] of cases) {
      mock(view({ box: part(o) }));
      const { unmount } = render(<StageClock intentId="i1" />);
      const chip = await screen.findByText(text);
      expect(cls === "" ? chip.className === "sc__chip" : chip.classList.contains(cls)).toBe(true);
      unmount();
    }
  });

  test("an overdue intent with no current stage shows no Not started chip; a quiet one with no stage does", async () => {
    const none = [{ key: "wall", name: "Think unfiltered", status: "later" as const, due: null }];
    mock(view({ stage: null, stages: none, box: part({ state: "overdue", working_days_left: 0, hours_left: -24 }) }));
    const { unmount } = render(<StageClock intentId="i1" />);
    await screen.findByText(/Overdue by/);
    expect(screen.queryByText("Not started")).toBeNull();
    unmount();
    mock(view({ stage: null, stages: none }));
    render(<StageClock intentId="i1" />);
    expect(await screen.findByText("Not started")).toBeTruthy();
  });

  test("a recorded (closing) intent shows no Not started chip", async () => {
    mock(view({ state: "closing", stage: null, stages: [{ key: "wall", name: "Think unfiltered", status: "later" as const, due: null }] }));
    render(<StageClock intentId="i1" />);
    await screen.findByText(/days left/);
    expect(screen.queryByText("Not started")).toBeNull();
  });

  test("hours when under two working days, and a draft has no clock", async () => {
    mock(view({ box: part({ unit: "hours", hours_left: 6 }) }));
    const { unmount } = render(<StageClock intentId="i1" />);
    expect(await screen.findByText(/^6 hours left/)).toBeTruthy();
    unmount();
    mock(view({ box: null, stage: null, started: false, can_extend: false }));
    render(<StageClock intentId="i1" />);
    expect(await screen.findByText("No clock yet")).toBeTruthy();
    expect(screen.getByText("Starts when opened")).toBeTruthy();
  });

  test("extend needs a day count and a reason, then posts both", async () => {
    mock(view());
    render(<StageClock intentId="i1" />);
    await userEvent.click(await screen.findByRole("button", { name: "Extend" }));
    const dlg = within(screen.getByRole("dialog"));
    const go = dlg.getByRole("button", { name: "Extend" });
    expect((go as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText("A reason is needed.")).toBeTruthy();
    await userEvent.click(screen.getByText("2 days"));
    await userEvent.type(screen.getByPlaceholderText("Why more time is needed"), "Waiting for the glossary from Finance");
    expect(screen.getByText(/^New end /)).toBeTruthy();
    await userEvent.click(dlg.getByRole("button", { name: "Extend" }));
    expect(posts[0]).toEqual({ url: "/api/intents/i1/time-box/extend", body: { days: 2, reason: "Waiting for the glossary from Finance", scope: "intent" } });
  });

  test("a later extension asks the sponsor; the closed intent has Extend disabled", async () => {
    mock(view({ approval: { needed: true, approver: "Daniel Kerr (sponsor)" }, extensions: { count: 1, show_reason: true, list: [], latest: null } }));
    const { unmount } = render(<StageClock intentId="i1" />);
    await userEvent.click(await screen.findByRole("button", { name: "Extend" }));
    expect(screen.getByText("This extension needs Daniel Kerr (sponsor) to approve.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Ask Daniel to approve" })).toBeTruthy();
    unmount();
    mock(view({ state: "closed", can_extend: false }));
    render(<StageClock intentId="i1" />);
    expect((await screen.findByRole("button", { name: "Extend" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText("Nothing to extend. The intent is closed.")).toBeTruthy();
  });

  test("a closed intent reads Closed with its date, no days left and no Closes line", async () => {
    mock(view({ state: "closed", can_extend: false, stage: null, box: part({ state: "closed", working_days_left: 0, words: "Closed Wed 7 Oct" }) }));
    render(<StageClock intentId="i1" />);
    expect(await screen.findByText("Closed Wed 7 Oct")).toBeTruthy();
    expect(screen.queryByText(/days left/)).toBeNull();
    expect(screen.queryByText(/^Closes /)).toBeNull();
  });
});
