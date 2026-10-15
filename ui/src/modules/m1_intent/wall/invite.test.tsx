import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

import InvitePanel from "./InvitePanel";

const SID = "c".repeat(32);
const S = `/api/modules/m1_intent/sessions/${SID}`;
const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
const view = (organiser: boolean, state = "lobby") => ({
  session_id: SID, state, length_minutes: 30, is_solo: false, organiser, me: null, arrived: 1, seat_count: 2,
  seats: [{ n: 1, state: "taken", mine: false, name: "Ann", role: "Lead" }, { n: 2, state: "free", mine: false }],
});
const calls: string[] = [];
function mock(organiser: boolean, state = "lobby") {
  calls.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push(`${init?.method ?? "GET"} ${url}`);
    if (url.includes("/join-link")) return json({ join_path: "/join/abc", state: "lobby" });
    if (url.includes("/revoke")) return json(view(true));
    return json(view(organiser, state));
  }));
}
afterEach(() => vi.unstubAllGlobals());

test("organiser sees the link and the seats", async () => {
  mock(true);
  render(<InvitePanel sessionId={SID} />);
  await userEvent.click(await screen.findByRole("button", { name: /2 seats · 1 taken · Invite/ }));
  expect(await screen.findByDisplayValue(/\/join\/abc$/)).toBeTruthy();
  expect(screen.getByText(/Ann/)).toBeTruthy();
  expect(screen.getByRole("button", { name: "New link" })).toBeTruthy();
});

test("a participant sees nothing", async () => {
  mock(false);
  const { container } = render(<InvitePanel sessionId={SID} />);
  await vi.waitFor(() => expect(calls.length).toBeGreaterThan(0));
  expect(container.innerHTML).toBe("");
  expect(calls.some((c) => c.includes("/join-link"))).toBe(false); // the link is the organiser's: never asked for
});

test("revoke calls the route", async () => {
  mock(true);
  render(<InvitePanel sessionId={SID} />);
  await userEvent.click(await screen.findByRole("button", { name: /Invite/ }));
  await userEvent.click(await screen.findByRole("button", { name: "Revoke seat 1" }));
  expect(calls).toContain(`POST ${S}/seats/1/revoke`);
});

test("a closed wall keeps the seat list but offers no link, no new link and no revoke", async () => {
  mock(true, "closed");
  render(<InvitePanel sessionId={SID} />);
  await userEvent.click(await screen.findByRole("button", { name: /Invite/ }));
  expect(screen.getByText(/Ann/)).toBeTruthy();
  expect(screen.queryByRole("button", { name: "New link" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Revoke seat 1" })).toBeNull();
  expect(calls.some((c) => c.includes("/join-link"))).toBe(false);
});
