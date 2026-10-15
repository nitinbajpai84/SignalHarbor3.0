import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { TimerView } from "../api";
import { m1Timer } from "../copy";
import StageTimer, { formatLeft } from "./StageTimer";

// M1-14 timer: countdown from the server's time, one-minute warning, organiser-only extend, five states.

const SID = "a".repeat(32);
const URL_TIMER = `/api/modules/m1_intent/sessions/${SID}/timer`;
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const timed = (over: Partial<Extract<TimerView, { timed: true }>> = {}): TimerView => ({
  stage: "briefing", timed: true, status: "running", started_at: "x", ends_at: "y", now: "z", remaining_seconds: 240,
  warning_seconds: 60, extensions: [], extension_minutes: [2, 5, 10], may_extend: false, ...over,
});
const calls: { method: string; url: string; body: unknown }[] = [];

function serve(next: () => Response | Promise<Response>) {
  calls.length = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ method: init?.method ?? "GET", url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
      return next();
    }),
  );
}

beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }));
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

test("formatLeft shows minutes and seconds and never goes below zero", () => {
  expect([formatLeft(240), formatLeft(59.9), formatLeft(0), formatLeft(-5)]).toEqual(["4:00", "0:59", "0:00", "0:00"]);
  expect([formatLeft(7197 * 60), formatLeft(5 * 3600)]).toEqual(["5 days", "5 hours"]); // a wall window is days, not 7197:29
});

test("loading, then the time left counting down from the server's figure", async () => {
  serve(() => json(200, timed()));
  render(<StageTimer sessionId={SID} />);
  expect(screen.getByRole("status")).toHaveTextContent("Loading");
  expect(await screen.findByRole("timer")).toHaveTextContent("4:00");
  act(() => {
    vi.advanceTimersByTime(3000);
  });
  expect(screen.getByRole("timer")).toHaveTextContent("3:57");
  expect(calls[0]?.url).toBe(URL_TIMER);
});

test("the one-minute warning shows at the warning time, in words", async () => {
  serve(() => json(200, timed({ status: "warning", remaining_seconds: 60 })));
  render(<StageTimer sessionId={SID} />);
  expect(await screen.findByRole("alert")).toHaveTextContent("One minute left");
  expect(m1Timer.warning(30)).toBe("30 seconds left");
});

test("no warning while there is plenty of time", async () => {
  serve(() => json(200, timed()));
  render(<StageTimer sessionId={SID} />);
  await screen.findByRole("timer");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

test("a participant has no extend control; the organiser has the contract's amounts and an extend posts it", async () => {
  serve(() => json(200, timed()));
  const first = render(<StageTimer sessionId={SID} />);
  await screen.findByRole("timer");
  expect(screen.queryByRole("group", { name: m1Timer.extendTitle })).not.toBeInTheDocument();
  first.unmount();

  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  serve(() => json(200, timed({ may_extend: true })));
  render(<StageTimer sessionId={SID} />);
  const group = await screen.findByRole("group", { name: m1Timer.extendTitle });
  expect(group.querySelectorAll("button")).toHaveLength(3);
  serve(() => json(200, timed({ may_extend: true, remaining_seconds: 360 })));
  await user.click(screen.getByRole("button", { name: m1Timer.extend(2) }));
  await waitFor(() => expect(screen.getByRole("timer")).toHaveTextContent("6:00"));
  expect(calls[0]).toMatchObject({ method: "POST", url: `${URL_TIMER}/extend`, body: { minutes: 2 } });
  expect(screen.getByText(m1Timer.extended)).toBeInTheDocument();
});

test("time is up: the organiser is told to add time; a participant is told time is up", async () => {
  serve(() => json(200, timed({ status: "over", remaining_seconds: 0, may_extend: true })));
  const a = render(<StageTimer sessionId={SID} />);
  expect(await screen.findByText(m1Timer.overOrganiser)).toBeInTheDocument();
  a.unmount();
  serve(() => json(200, timed({ status: "over", remaining_seconds: 0 })));
  render(<StageTimer sessionId={SID} />);
  expect(await screen.findByText(m1Timer.over)).toBeInTheDocument();
  expect(calls).toHaveLength(1); // an ended stage is not asked about again and again
});

test("a stage with no timer shows nothing", async () => {
  serve(() => json(200, { stage: "board", timed: false, now: "z" }));
  const { container } = render(<StageTimer sessionId={SID} />);
  await waitFor(() => expect(calls).toHaveLength(1));
  await waitFor(() => expect(container).toBeEmptyDOMElement());
});

test("when the server moves the stage on, the screen is told", async () => {
  const onStageChange = vi.fn();
  serve(() => json(200, timed({ remaining_seconds: 20 })));
  render(<StageTimer sessionId={SID} onStageChange={onStageChange} />);
  await screen.findByRole("timer");
  serve(() => json(200, { stage: "board", timed: false, now: "z" }));
  act(() => {
    vi.advanceTimersByTime(21000);
  });
  await waitFor(() => expect(onStageChange).toHaveBeenCalledWith("board"));
});

test("error: one sentence and a way to try again", async () => {
  serve(() => json(500, { detail: "boom" }));
  render(<StageTimer sessionId={SID} />);
  expect(await screen.findByRole("alert")).toHaveTextContent(m1Timer.unavailable);
  expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  expect(document.body).not.toHaveTextContent("boom");
});

test("refused: plain words, no technical detail", async () => {
  serve(() => json(403, { error: "forbidden", message: "x" }));
  render(<StageTimer sessionId={SID} />);
  expect(await screen.findByRole("alert")).toHaveTextContent("You do not have access");
});

test("onWarning is called once when the warning time is reached, not before", async () => {
  serve(() => json(200, timed({ remaining_seconds: 62 })));
  const onWarning = vi.fn();
  render(<StageTimer sessionId={SID} onWarning={onWarning} />);
  expect(await screen.findByRole("timer")).toHaveTextContent("1:02");
  expect(onWarning).not.toHaveBeenCalled();
  act(() => {
    vi.advanceTimersByTime(3000);
  });
  await waitFor(() => expect(onWarning).toHaveBeenCalledTimes(1));
  act(() => {
    vi.advanceTimersByTime(5000);
  });
  expect(onWarning).toHaveBeenCalledTimes(1);
});
