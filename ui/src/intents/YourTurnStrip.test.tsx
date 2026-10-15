import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";

import WhoHasNotActed from "./WhoHasNotActed";
import YourTurnStrip from "./YourTurnStrip";

// Nira's strip and the organiser's panel (spec 45). fetch is stubbed with synthetic data.

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const line = (id: string, group: string, extra: object = {}) => ({ id, kind: "decision", title: `Title ${id}`, detail: "Detail.", href: `/centre/intent/${id}`, action: "Decide", due: null, group, ...extra });

function mount(ui: ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

test("the strip counts the lines, filters from four lines, and shows each action", async () => {
  const lines = [line("a", "Signature"), line("b", "Decision"), line("c", "Question"), line("d", "Rating", { due: "2000-01-03" })];
  vi.stubGlobal("fetch", vi.fn(async () => json(200, { lines, count: 4 })));
  mount(<YourTurnStrip />);
  expect(await screen.findByText("4 things wait for you")).toBeInTheDocument();
  expect(screen.queryByText("Title d")).toBeNull(); // three show at every width, the rest wait behind "Show all"
  fireEvent.click(screen.getByRole("button", { name: "Show all 4" }));
  expect(screen.getByText("Overdue since Mon 3 Jan")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Ratings" }));
  expect(screen.getByText("Title d")).toBeInTheDocument();
  expect(screen.queryByText("Title a")).toBeNull();
});

test("an empty list and a failed read say so in words", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(200, { lines: [], count: 0 })));
  const first = mount(<YourTurnStrip />);
  expect(await screen.findByText("Nothing waits for you in the Intent Centre.")).toBeInTheDocument();
  first.unmount();
  vi.stubGlobal("fetch", vi.fn(async () => json(500, {})));
  mount(<YourTurnStrip />);
  expect(await screen.findByText("Nira could not read your list. Reload to try again.")).toBeInTheDocument();
});

const WHO = { active: true, count_stage: "2 of 3 in this stage", anonymous: true, nudged_at: null, cooling: false,
  people: [{ person_id: "k", name: "Katie", owes: "Add your ideas", since: "2026-10-06T09:00:00+00:00" }, { person_id: "a", name: "Aaron", owes: "Add your ideas", since: null }] };

test("the panel nudges the ticked people, drafts one message and never sends on its own", async () => {
  const posts: { url: string; body: unknown }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      posts.push({ url, body: init.body ? JSON.parse(String(init.body)) : null });
      return url.endsWith("/send") ? json(503, { message: "No email path is set up yet; the message stays a draft." }) : json(200, { message: { id: "m1", subject: "A reminder", body: "Hello", chat: "Short line" } });
    }
    return json(200, WHO);
  }));
  mount(<WhoHasNotActed intentId="i1" />);
  expect(await screen.findByText("Anonymous ideas are counted, not named.")).toBeInTheDocument();
  expect(screen.getByText("Not available yet: the stage has no opening date on record.")).toBeInTheDocument();
  fireEvent.click(screen.getByLabelText("Nudge Aaron"));
  fireEvent.click(screen.getByRole("button", { name: "Nudge 1" }));
  expect(await screen.findByText("Draft message")).toBeInTheDocument();
  expect(posts).toEqual([{ url: "/api/intents/i1/nudge/all", body: { to: ["k"] } }]);
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  await waitFor(() => expect(screen.getByText("No email path is set up yet; the message stays a draft.")).toBeInTheDocument());
});

test("the panel is hidden for a person who may not see it and when no one is quiet it says so", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(403, {})));
  const first = mount(<WhoHasNotActed intentId="i1" />);
  await waitFor(() => expect(first.container).toBeEmptyDOMElement());
  first.unmount();
  vi.stubGlobal("fetch", vi.fn(async () => json(200, { ...WHO, people: [], anonymous: false })));
  mount(<WhoHasNotActed intentId="i1" />);
  expect(await screen.findByText("Everyone has acted in this stage.")).toBeInTheDocument();
});
