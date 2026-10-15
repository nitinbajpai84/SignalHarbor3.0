import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, test, vi } from "vitest";

import TimeCard from "./TimeCard";

const card = { line: "Time is up. Overdue by 1 working day.", organiser: "Janet", who_picks: "Janet picks. If Janet does not pick by Mon 20 Oct, Daniel is asked." };
const show = (o = {}) => render(<MemoryRouter><TimeCard intentId="i1" card={card} canExtend isOrganiser onExtend={vi.fn()} {...o} /></MemoryRouter>);

describe("TimeCard", () => {
  beforeEach(() => localStorage.clear());
  test("one sentence, three buttons and who picks", () => {
    show();
    expect(screen.getAllByText(/Overdue by 1 working day/)).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Extend the time box" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Close with what we have" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Cancel this intent" })).toBeTruthy();
    expect(screen.getByText(/Janet picks\. If Janet does not pick by Mon 20 Oct, Daniel is asked\./)).toBeTruthy();
  });
  test("Remind me tomorrow hides the card, for the organiser only", async () => {
    const { unmount } = show({ isOrganiser: false });
    expect(screen.queryByText("Remind me tomorrow")).toBeNull();
    unmount();
    show();
    await userEvent.click(screen.getByText("Remind me tomorrow"));
    expect(screen.queryByTestId("time-card")).toBeNull();
  });
});
