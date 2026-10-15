import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { setSessionExpiredHandler } from "../../api/client";
import OpsPage from "./OpsPage";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const OPS = {
  date: "2026-10-06", period: "2026-09", loaded: [],
  sources: [{ source_id: "administrator_A2", owner: "Harvey Rowley", state: "late", last_run: "r1", arrived: "2026-10-06T18:56:00Z", rows: 2 }],
  alerts: [{ id: "administrator_A2:late", source: "administrator_A2", kind: "late", owner: "Harvey Rowley", ask: "Hello", state: "open", by: null, note: null }],
};

afterEach(() => { vi.unstubAllGlobals(); setSessionExpiredHandler(null); });

it("shows a late source and marks it loaded for the period", async () => {
  const posts: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") { posts.push(`${url} ${String(init.body)}`); return json(200, {}); }
    return json(200, OPS);
  }));
  render(<MemoryRouter><OpsPage /></MemoryRouter>);
  expect(await screen.findAllByText("Late")).not.toHaveLength(0);
  await userEvent.click(screen.getByRole("button", { name: "Loaded" }));
  expect(posts[0]).toContain("/api/v1/ops/loaded");
  expect(posts[0]).toContain('"period":"2026-09"');
  expect(screen.getByRole("button", { name: "Not loaded" })).toBeDisabled();
});

it("refuses a viewer outside the ops seat", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(403, { error: "forbidden" })));
  render(<MemoryRouter><OpsPage /></MemoryRouter>);
  expect(await screen.findByText("Ops is for the ops manager")).toBeInTheDocument();
});
