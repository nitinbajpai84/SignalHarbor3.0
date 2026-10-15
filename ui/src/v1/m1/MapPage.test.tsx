import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { setSessionExpiredHandler } from "../../api/client";
import MapPage from "./MapPage";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const MAP = {
  built_at: "2026-10-08T09:00:00+00:00",
  nodes: [
    { id: "intent:p", type: "Intent", label: "Monthly performance pack", state: "designed", intents: [], notes: [] },
    { id: "measure:p:TWR", type: "Measure", label: "Time-weighted return", what: "Return net of flows", said_by: "Arjun Mehta", at: "2026-10-08T09:00:00+00:00",
      from_record: "intents/p/sow.json", intents: ["p"], notes: [{ id: "c1", text: "Net of fees?", by: "Harvey Rowley", at: "2026-10-08T10:00:00+00:00", state: "open" }] },
    { id: "gap:p:CD", type: "Gap", label: "No source yet", what: "Nothing feeds Cash drag yet", stub: true, intents: ["p"], notes: [] },
  ],
  edges: [{ from: "intent:p", to: "measure:p:TWR", type: "uses" }],
};

afterEach(() => { vi.unstubAllGlobals(); setSessionExpiredHandler(null); });

it("opens an intent, shows a thing with its origin and note, and says something looks wrong", async () => {
  const posts: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") { posts.push(`${url} ${String(init.body)}`); return json(200, {}); }
    return json(200, MAP);
  }));
  render(<MemoryRouter initialEntries={["/centre/intent/graph"]}><MapPage /></MemoryRouter>);
  await userEvent.click(await screen.findByRole("button", { name: /Monthly performance pack/ }));
  await userEvent.click(screen.getByRole("button", { name: /Time-weighted return · 1 note/ }));
  expect(screen.getByText("Said by Arjun Mehta, 8 Oct.")).toBeInTheDocument();
  expect(screen.getByText("Came from: the intent of work")).toBeInTheDocument();
  expect(screen.getByText("1 note from Harvey Rowley, 8 Oct")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Something looks wrong" }));
  await userEvent.type(screen.getByLabelText("What looks wrong"), "Owner is wrong");
  await userEvent.click(screen.getByRole("button", { name: "Send" }));
  expect(posts[0]).toContain("/api/v1/map/node/measure%3Ap%3ATWR/comments");
});

it("tells a refused viewer the map is not open to them", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(403, { error: "forbidden" })));
  render(<MemoryRouter><MapPage /></MemoryRouter>);
  expect(await screen.findByText("The map is not open to you")).toBeInTheDocument();
});
