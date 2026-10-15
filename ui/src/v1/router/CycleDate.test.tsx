import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import CycleDateSetting, { CycleBadge, dayWords } from "./CycleDate";

const state = (over = {}) => ({ cycle_date: "2026-07-31", today: "2026-07-31", real_today: "2026-10-12", pinned: true, can_set: true, ...over });
const reply = (body: unknown, init = 200) => Promise.resolve(new Response(JSON.stringify(body), { status: init, headers: { "Content-Type": "application/json" } }));

afterEach(() => vi.unstubAllGlobals());

describe("cycle date", () => {
  it("words a day", () => expect(dayWords("2026-07-31")).toBe("31 Jul 2026"));

  it("the header shows the cycle date only when it is not the real day", async () => {
    vi.stubGlobal("fetch", vi.fn(() => reply(state())));
    const { unmount } = render(<CycleBadge />);
    expect(await screen.findByText("Cycle: 31 Jul 2026")).toBeTruthy();
    unmount();
    vi.stubGlobal("fetch", vi.fn(() => reply(state({ cycle_date: null, today: "2026-10-12", pinned: false }))));
    const { container } = render(<CycleBadge />);
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(container.textContent).toBe("");
  });

  it("the administrator saves a new day and can return to the real day", async () => {
    const f = vi.fn((url: string, init?: RequestInit) => reply(init?.method === "PUT" ? state({ cycle_date: "2026-08-31", today: "2026-08-31" }) : state()));
    vi.stubGlobal("fetch", f);
    render(<CycleDateSetting />);
    const input = await screen.findByLabelText("Cycle date");
    fireEvent.change(input, { target: { value: "2026-08-31" } });
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(f.mock.calls.some(([, i]) => i?.method === "PUT" && String(i.body).includes("2026-08-31"))).toBe(true));
    await userEvent.click(await screen.findByRole("button", { name: "Use the real day" }));
    await waitFor(() => expect(f.mock.calls.some(([, i]) => i?.method === "PUT" && String(i.body).includes("null"))).toBe(true));
  });

  it("someone who may not set it sees the day and no controls", async () => {
    vi.stubGlobal("fetch", vi.fn(() => reply(state({ can_set: false }))));
    render(<CycleDateSetting />);
    expect(await screen.findByText(/Only the administrator or the head of data/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Save" })).toBeNull();
  });
});
