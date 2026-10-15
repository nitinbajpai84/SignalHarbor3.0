import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { ThemeProvider } from "../theme";
import IntentAdmin, { AdminCancelDialog } from "./IntentAdmin";

// Spec 48 screens A, B and D. fetch is stubbed with synthetic data.

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const row = (id: string, state: string, bucket: string) => ({
  id, type: "problem", title: `Intent ${id}`, purpose: "Why", state, bucket, stage: null, areas: [], organiser: "Janet", sponsor: null, people_more: 2,
  opened: "2026-10-01", ends: "2026-10-08", extensions: 0, clock: { key: bucket, text: bucket === "overdue" ? "Overdue by 2 days" : "3 days left" },
  closed_at: null, outcome: null, rating: { count: 0, mean: null, by_design: false }, could_rate: 0, cancelled_by_admin: false,
});
const LIST = {
  items: [row("a", "open", "open"), row("b", "open", "overdue")], counts: { open: 1, overdue: 1, closed: 0, cancelled: 0, total: 2 }, next: null,
  tabs: { overdue: 1, unrated: 0 }, organisers: ["Janet"], areas: [], has_no_area: true, total_all: 2, closed_in_view: 0,
};
const SETTINGS = { titles_private: false, time_boxes: { initiative: { title: "Initiative", days: 10, catalogue: 10, changed: false, stages_total: 10 } } };

function mock(opts: { adminRoutes?: boolean; list?: unknown } = {}) {
  const calls: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push(`${init?.method ?? "GET"} ${url}`);
    if (url === "/api/auth/me") return json(200, { display_name: "Janet Shaw", company_id: "co-a", roles: ["company_admin"] });
    if (url.startsWith("/api/intents/admin/")) return opts.adminRoutes ? json(200, opts.list ?? LIST) : json(403, { error: "forbidden" });
    if (url.startsWith("/api/intents/settings?view=list")) return json(200, opts.list ?? LIST);
    if (url === "/api/intents/settings") return init?.method === "PUT" ? json(200, SETTINGS) : json(200, SETTINGS);
    if (url.endsWith("/admin-cancel")) return json(200, { state: "cancelled" });
    return json(200, {});
  }));
  return calls;
}
const view = (path: string) => render(<ThemeProvider><MemoryRouter initialEntries={[path]}><IntentAdmin /></MemoryRouter></ThemeProvider>);

test("the count line is counted from the rows, read through /api/intents/admin/list", async () => {
  const calls = mock({ adminRoutes: true });
  view("/centre/intent/admin");
  expect((await screen.findByTestId("count-line")).textContent).toBe("2 intents: 1 open, 1 overdue, 0 closed, 0 cancelled");
  expect(calls.some((c) => c.startsWith("GET /api/intents/admin/list"))).toBe(true);
  expect(await screen.findByText("Overdue by 2 days")).toBeTruthy();
  expect(screen.getAllByText("+2 people").length).toBe(2);
  expect(screen.getByRole("button", { name: "Nothing closed yet" }).hasAttribute("disabled")).toBe(true);
});

test("no intents shows the spec's empty line", async () => {
  mock({ adminRoutes: true, list: { ...LIST, items: [], counts: { open: 0, overdue: 0, closed: 0, cancelled: 0, total: 0 }, total_all: 0 } });
  view("/centre/intent/admin");
  expect(await screen.findByText(/No intents yet\. They appear here when someone starts one\./)).toBeTruthy();
});

test("defaults: Save stays off until a field changes, and a changed value is marked", async () => {
  mock();
  view("/centre/intent/admin?tab=defaults");
  const save = await screen.findByRole("button", { name: "Save defaults" });
  expect(save.hasAttribute("disabled")).toBe(true);
  fireEvent.change(screen.getByLabelText("Initiative working days"), { target: { value: "6" } });
  expect(save.hasAttribute("disabled")).toBe(false);
  expect(screen.getByText("Changed")).toBeTruthy();
  expect(screen.getByText("Your Initiative time box is 6 working days. The stages add up to 10. North will propose an extension early.")).toBeTruthy();
});

test("the cancel dialog needs a reason before it can be confirmed", async () => {
  const calls = mock();
  const done = vi.fn();
  render(<ThemeProvider><AdminCancelDialog intentId="ini-1" onClose={() => {}} onDone={done} /></ThemeProvider>);
  const go = screen.getByRole("button", { name: "Cancel this intent" });
  expect(go.hasAttribute("disabled")).toBe(true);
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "  Organiser has left " } });
  fireEvent.click(go);
  await waitFor(() => expect(done).toHaveBeenCalled());
  expect(calls).toContain("POST /api/intents/ini-1/admin-cancel");
});

test("an intent with no title reads its type and opened date, never a blank cell", async () => {
  mock({ adminRoutes: true, list: { ...LIST, items: [{ ...row("c", "open", "open"), title: "" }] } });
  view("/centre/intent/admin");
  expect((await screen.findAllByText("Problem, started 2026-10-01")).length).toBeGreaterThan(0);
});
