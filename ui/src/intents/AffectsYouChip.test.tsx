import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";

import AffectsYouChip from "./AffectsYouChip";
import FeelThis from "./FeelThis";
import NoteToOrganiser from "./NoteToOrganiser";

// Affected person and observer (spec 47). fetch is stubbed with synthetic data.

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const MINE = { role: "affected", follow: false, request: null, replies: [], tapped: [] };

function mock(mine: object = MINE) {
  const sent: { method: string; url: string; body: Record<string, unknown> }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    if (method !== "GET") { sent.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : {} }); return json(200, {}); }
    return json(200, { mine });
  }));
  return sent;
}
const wrap = (node: ReactElement) => render(<MemoryRouter>{node}</MemoryRouter>);

afterEach(() => vi.unstubAllGlobals());

test("the chip shows for an affected person with no stronger role and nobody else", () => {
  const { container, rerender } = wrap(<AffectsYouChip affected area="Operations" />);
  expect(screen.getByText("Affects you")).toBeTruthy();
  rerender(<MemoryRouter><AffectsYouChip affected stronger /></MemoryRouter>);
  expect(container.textContent).toBe("");
  rerender(<MemoryRouter><AffectsYouChip affected={false} /></MemoryRouter>);
  expect(container.textContent).toBe("");
});

test("I feel this counts without a name by default, and can be taken back", async () => {
  const sent = mock();
  wrap(<FeelThis intentId="prb-1" item="intent" />);
  await waitFor(() => expect((screen.getByText("I feel this") as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByText("I feel this"));
  expect((screen.getByLabelText("Count me without my name") as HTMLInputElement).checked).toBe(true);
  fireEvent.click(screen.getAllByText("I feel this")[1]!);
  await screen.findByText("You tapped");
  expect(sent[0]).toMatchObject({ method: "POST", body: { item: "intent", signed: false } });
  fireEvent.click(screen.getByText("Take it back"));
  await screen.findByText("I feel this");
  expect(sent[1]!.method).toBe("DELETE");
});

test("the note button waits for text, and an observer sees no note box", async () => {
  const sent = mock();
  const { unmount } = wrap(<NoteToOrganiser intentId="prb-1" organiser="Janet" />);
  const send = (await screen.findByText("Send note")) as HTMLButtonElement;
  expect(send.disabled).toBe(true);
  fireEvent.change(screen.getByPlaceholderText("Tell Janet what you know or what worries you."), { target: { value: "Sign-off is slow" } });
  fireEvent.click(screen.getByLabelText("Send without my name"));
  fireEvent.click(send);
  await screen.findByText("Sent. Janet can read it.");
  expect(sent[0]).toMatchObject({ url: "/api/intents/prb-1/notes", body: { text: "Sign-off is slow", signed: false } });
  unmount();
  mock({ ...MINE, role: "observer" });
  wrap(<NoteToOrganiser intentId="prb-1" />);
  await screen.findByText(/You are watching this intent/);
  expect(screen.queryByText("Send note")).toBeNull();
  expect(screen.queryByText("Ask to join")).toBeNull();  // an observer follows only
});

test("ask to join needs a reason; a declined request shows the reason", async () => {
  const sent = mock();
  const { unmount } = wrap(<NoteToOrganiser intentId="prb-1" />);
  fireEvent.click(await screen.findByText("Ask to join"));
  const go = screen.getByText("Send request") as HTMLButtonElement;
  expect(go.disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Why would you like to join? One line."), { target: { value: "I run the packing list" } });
  fireEvent.click(go);
  await waitFor(() => expect(sent[0]).toMatchObject({ url: "/api/intents/prb-1/join-requests", body: { asked_role: "participant", reason: "I run the packing list" } }));
  unmount();
  mock({ ...MINE, request: { id: "r1", state: "declined", asked_role: "participant", at: "2026-10-09T00:00:00Z", role_given: null, decline_reason: "Wall is full" } });
  wrap(<NoteToOrganiser intentId="prb-1" />);
  await screen.findByText("Declined: Wall is full");
});
