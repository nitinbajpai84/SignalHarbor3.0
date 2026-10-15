import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, test, vi } from "vitest";

import StageBar from "./StageBar";

const SID = "c".repeat(32);
const S = `/api/modules/m1_intent/sessions/${SID}`;
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const posts: string[] = [];
function mock(organiser: boolean, state = "briefing", refuse = false) {
  posts.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      posts.push(url);
      return refuse ? json(409, { message: "Not yet: two people are still arriving." }) : json(200, { state: "private_rooms" });
    }
    if (url === `${S}/lobby`) return json(200, { state, organiser });
    return json(409, {});
  }));
  vi.stubGlobal("location", { ...window.location, reload: vi.fn() });
}
afterEach(() => vi.unstubAllGlobals());

describe("StageBar", () => {
  test("lights the current stage among all seven", async () => {
    mock(true);
    render(<StageBar sessionId={SID} />);
    expect((await screen.findByText("Briefing")).getAttribute("aria-current")).toBe("step");
    expect(screen.getAllByRole("listitem")).toHaveLength(7);
    expect(screen.getByText("Lobby").getAttribute("aria-current")).toBeNull();
  });

  test("the next-step button asks first, then calls the route", async () => {
    mock(true);
    render(<StageBar sessionId={SID} />);
    await userEvent.click(await screen.findByRole("button", { name: "Open the private rooms" }));
    expect(posts).toHaveLength(0);
    expect(screen.getByText("Are you sure?")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Yes" }));
    expect(posts).toEqual([`${S}/briefing/send`]);
  });

  test("a participant sees no stage bar at all", async () => {
    mock(false);
    const { container } = render(<StageBar sessionId={SID} />);
    await new Promise((r) => setTimeout(r, 20));
    expect(container.innerHTML).toBe("");
  });
});
