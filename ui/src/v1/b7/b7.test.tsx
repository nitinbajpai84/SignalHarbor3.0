import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import type { LayoutItem } from "../cxui/api";
import DashboardView from "../cxui/DashboardView";
import Canvas, { fits, freeRuns } from "./Canvas";
import RefreshLine from "./RefreshLine";
import StudioPage from "./StudioPage";
import type { Refresh, Studio } from "./api";

vi.mock("vega-embed", () => ({ default: vi.fn(async () => ({ view: { finalize: () => undefined } })) }));
vi.setConfig({ testTimeout: 20000 });

// DS1, OP1 against b7_routes (synthetic data): the canvas (slots, keyboard move and resize), the studio page and Lumen's conversation in it, the approver's view, the refresh line.
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const item = (id: string, row: number, col: number, size: LayoutItem["size"], kind = "line"): LayoutItem =>
  ({ id, kind, tile: kind === "note" ? null : `t-${id}`, title: `Widget ${id}`, text: kind === "note" ? "A note" : "", row, col, size, reads: kind === "note" ? [] : ["monthly report holdings"] });
const FRESH: Refresh = { schedule: "daily", words: "Updated daily at 06:00 after the pipeline run", last_refreshed: "2026-10-10T06:02:00", next: "2026-10-11T06:00:00", warning: null, link: null, late_sources: [], last_run_failed: false };
const board = (over: Partial<Studio> = {}): Studio => ({
  id: "dash-1", project_id: "EV-1", title: "Board pack", rev: 4, status: "draft", version: 1, published_version: null, sent_back: null, submitted_by: null, submitted_at: null,
  approved_by: null, approved_at: null, company_wide: false, layout: { rows: 2, items: [item("a", 0, 0, "medium")] }, tiles: [],
  can: { edit: true, submit: true, approve: false },
  library: { kinds: ["figure", "line", "bar", "area", "table", "status", "note"], tables: [{ name: "gold_x", label: "monthly report holdings", columns: [] }],
    lumen: [{ dashboard_id: "dash-9", tile_id: "t-9", title: "Cash by entity", state: "proposed", reads: ["monthly report holdings"] }] },
  refresh: FRESH, ...over,
});

function mock(start: Studio) {
  let cur = start;
  let steps = [{ n: 1, at: "06:30", by: "Lumen", said: "", summary: "Lumen's starter" }];
  const calls: { method: string; url: string; body?: Record<string, unknown> }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method, url, body });
    if (url === "/api/v1/projects") return json(200, { projects: [{ id: "EV-1", title: "Monthly report", stage: "live" }] });
    if (url === "/api/v1/build/p/EV-1/studio") return json(200, { dashboards: [{ id: cur.id, title: cur.title, status: cur.status, version: cur.version, tiles: cur.layout.items.length, created_by: "a", updated_at: "", waiting_for_you: cur.can.approve }], can_make: true });
    if (url.endsWith("/layout")) { cur = { ...cur, layout: { rows: body!.rows as number, items: (body!.items as { id: string; row: number; col: number; size: LayoutItem["size"] }[]).map((i) => ({ ...cur.layout.items.find((o) => o.id === i.id)!, ...i })) } }; return json(200, cur); }
    if (url.endsWith("/widgets")) { const it = item("n", body!.row as number, body!.col as number, "medium", body!.kind as string); cur = { ...cur, layout: { ...cur.layout, items: [...cur.layout.items, it] } }; return json(200, { placed: it, dashboard: cur }); }
    if (url.endsWith("/talk")) {
      const edit = Boolean(body!.widget);
      cur = { ...cur, rev: cur.rev + 1, layout: { ...cur.layout, items: edit ? cur.layout.items.map((i) => (i.id === body!.widget ? { ...i, title: "Cash by entity, dots" } : i)) : [...cur.layout.items, item("q", 1, 0, "medium")] } };
      steps = [...steps, { n: steps.length + 1, at: "06:4" + steps.length, by: "Mei", said: String(body!.text), summary: "Talk" }];
      return json(200, { reply: edit ? "Done, it is dots." : "Added Cash by entity.", changed: [edit ? String(body!.widget) : "q"], step: steps.length });
    }
    if (url.endsWith("/history")) return json(200, { steps, now: steps.length });
    if (url.endsWith("/undo")) { cur = { ...cur, rev: cur.rev + 1, layout: { ...cur.layout, items: cur.layout.items.filter((i) => i.id !== "q") } }; steps = steps.slice(0, -1); return json(200, { ok: true }); }
    if (/\/history\/\d+\/restore$/.test(url)) { steps = steps.slice(0, 1); return json(200, { ok: true }); }
    if (/\/history\/\d+\/compare$/.test(url)) return json(200, { added: ["Cash by entity"], removed: [], changed: ["Widget a"] });
    if (url.endsWith("/withdraw")) { cur = { ...cur, status: "draft", can: { ...cur.can, edit: true, submit: true } }; return json(200, { ok: true }); }
    if (url.endsWith("/ask") && body!.new_talk) { cur = { ...cur, talk: [] }; return json(200, { reply: "A fresh talk.", proposals: [], dashboard: cur }); }
    if (url.endsWith("/ask")) {
      if (/^(why|what)/i.test(String(body!.text))) { cur = { ...cur, talk: [...(cur.talk ?? []), { by: "person", text: String(body!.text) }, { by: "lumen", text: "It is 54,968,000." }] }; return json(200, { reply: "It is 54,968,000.", proposals: [], dashboard: cur }); }
      const edit = Boolean(body!.widget);
      const t = { id: edit ? "t-p2" : "t-p1", title: edit ? "Cash by entity, dots" : "Cash by entity", state: "proposed", spec: { mark: "line" }, kpi: "", note: "", replaces: edit ? "t-a" : null };
      cur = { ...cur, tiles: [...cur.tiles.filter((x) => x.id !== t.id), t] };
      return json(200, { reply: edit ? "I changed it. This is a new version waiting for you." : "I have proposed one tile. It is waiting for you.", proposals: [t], worded_by: body!.text === "rules please" ? "rules" : "model", dashboard: cur });
    }
    if (url.endsWith("/tiles/t-p1/accept") || url.endsWith("/tiles/t-p2/accept")) {
      const second = url.includes("t-p2");
      const it = second ? { ...cur.layout.items.find((i) => i.id === "a")!, tile: "t-p2", title: "Cash by entity, dots" } : item("q", (body!.row as number | undefined) ?? 1, (body!.col as number | undefined) ?? 0, "medium", "lumen");
      cur = { ...cur, tiles: cur.tiles.filter((x) => !x.id.startsWith("t-p")), layout: { ...cur.layout, items: second ? cur.layout.items.map((i) => (i.id === "a" ? it : i)) : [...cur.layout.items, it] } };
      return json(200, { placed: it, dashboard: cur });
    }
    if (url.endsWith("/reject")) { cur = { ...cur, tiles: cur.tiles.filter((x) => !url.includes(x.id)) }; return json(200, cur); }
    if (url.endsWith("/starter/accept")) { cur = { ...cur, starter: { ...cur.starter!, status: "accepted" }, tiles: cur.tiles.map((t) => ({ ...t, state: "accepted" })) }; return json(200, cur); }
    if (url.endsWith("/submit")) { cur = { ...cur, status: "submitted", can: { ...cur.can, edit: false, submit: false } }; return json(200, cur); }
    if (url.endsWith("/approve")) { cur = { ...cur, status: "published", can: { ...cur.can, approve: false }, approved_by: "Head of data", approved_at: "2026-10-10T09:00:00Z" }; return json(200, cur); }
    if (url.endsWith("/send-back")) { cur = { ...cur, status: "draft", sent_back: { reason: String(body!.reason), by: "Head of data", at: "" }, can: { ...cur.can, approve: false } }; return json(200, { id: cur.id, status: "draft" }); }
    if (url.includes("/studio/dash-1/tiles/") && url.endsWith("/data")) return json(200, { spec: { mark: "line" }, columns: ["m", "v"], rows: [{ m: "Sep", v: 1 }], data_used: { tables: ["gold_x"], last_refresh: "2026-10-10T06:02:00" } });
    if (url.endsWith("/studio/dash-1")) return json(200, cur);
    return json(404, { message: "no" });
  }));
  return calls;
}
const studio = () => render(<ThemeProvider><MemoryRouter initialEntries={["/centre/build/p/EV-1/studio"]}><Routes>
  <Route path="/centre/build/p/:projectId/studio" element={<StudioPage />} /></Routes></MemoryRouter></ThemeProvider>);
afterEach(() => vi.unstubAllGlobals());

test("the grid maths: free stretches and what fits", () => {
  const items = [item("a", 0, 0, "medium"), item("b", 0, 9, "small")];
  expect(freeRuns(items, 0)).toEqual([{ col: 6, width: 3 }]);
  expect(freeRuns(items, 1)).toEqual([{ col: 0, width: 12 }]);
  expect(fits(items, "a", 0, 3, "medium", 2)).toBe(true);
  expect(fits(items, "a", 0, 4, "medium", 2)).toBe(false);   // runs into the widget at column 10
  expect(fits(items, "a", 1, 6, "wide", 2)).toBe(false);     // past column 12
  expect(fits(items, "a", 2, 0, "small", 2)).toBe(false);    // no such row
});

test("the canvas: an empty slot is clicked, a widget moves and resizes by keys and buttons", async () => {
  const changes: LayoutItem[][] = []; const problems: string[] = []; const slots: unknown[] = [];
  const layout = { rows: 2, items: [item("a", 0, 0, "medium"), item("b", 0, 9, "small")] };
  render(<MemoryRouter><Canvas pid="EV-1" did="dash-1" layout={layout} editable load={async () => ({ spec: { mark: "line" }, rows: [], data_used: { tables: [], last_refresh: null } })}
    onSlot={(s) => slots.push(s)} onChange={(i) => changes.push(i)} onProblem={(w) => problems.push(w)} /></MemoryRouter>);
  const empty = screen.getAllByRole("button", { name: /Add a widget here/ });
  expect(empty).toHaveLength(2);                              // row 1 between the widgets, and the empty second row
  fireEvent.click(empty[0]!);
  expect(slots[0]).toEqual({ row: 0, col: 6 });
  const a = screen.getByLabelText(/^Widget a\. Drag to move/);
  fireEvent.keyDown(a, { key: "ArrowRight", altKey: true });
  expect(changes.at(-1)!.find((i) => i.id === "a")).toMatchObject({ row: 0, col: 1 });
  fireEvent.keyDown(a, { key: "ArrowDown", altKey: true });
  expect(changes.at(-1)!.find((i) => i.id === "a")).toMatchObject({ row: 1, col: 0 });
  fireEvent.keyDown(a, { key: "ArrowLeft", altKey: true });   // already at the edge: nothing moves, the person is told
  expect(problems.at(-1)).toMatch(/taken or off the grid/);
  fireEvent.keyDown(a, { key: "+" });
  expect(changes.at(-1)!.find((i) => i.id === "a")).toMatchObject({ size: "wide" });
  fireEvent.keyDown(a, { key: "-" });
  expect(changes.at(-1)!.find((i) => i.id === "a")).toMatchObject({ size: "small" });
  fireEvent.click(screen.getAllByRole("button", { name: "More" })[0]!);
  const group = within(screen.getByRole("group", { name: "Position and size of Widget a" }));
  fireEvent.click(group.getByRole("button", { name: "Full" }));   // would run into widget b: refused
  expect(problems.at(-1)).toMatch(/taken or off the grid/);
  fireEvent.click(group.getByRole("button", { name: "Move down" }));
  expect(changes.at(-1)!.find((i) => i.id === "a")).toMatchObject({ row: 1 });
});

test("the canvas is read-only without editing: no slots, no buttons", () => {
  render(<MemoryRouter><Canvas pid="EV-1" did="dash-1" layout={{ rows: 2, items: [item("n", 0, 0, "full", "note")] }} /></MemoryRouter>);
  expect(screen.getByText("A note")).toBeInTheDocument();
  expect(screen.queryByRole("button")).toBeNull();
});

test("the refresh line says when the figures were refreshed, and warns in amber with a link to the Map", () => {
  render(<MemoryRouter><RefreshLine refresh={{ ...FRESH, warning: "Not refreshed since 9 Oct: the Administrator file is late", link: "/centre/operations" }} /></MemoryRouter>);
  expect(screen.getByText(/Updated daily at 06:00 after the pipeline run · last refreshed 10 Oct 2026, 06:02 · next 11 Oct 2026, 06:00/)).toBeInTheDocument();
  expect(screen.getByText(/Not refreshed since 9 Oct: the Administrator file is late/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /source health in Operations/ })).toHaveAttribute("href", "/centre/operations");
});

test("the studio: move a widget, add one to a slot, ask Lumen for another, then submit", async () => {
  const calls = mock(board());
  studio();
  expect(await screen.findByText("Widget a")).toBeInTheDocument();
  expect(screen.getByText(/Updated daily at 06:00/)).toBeInTheDocument();
  expect(screen.getByText(/Reads: monthly report holdings/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Add widget to the slot" })).toBeDisabled();
  await userEvent.click(screen.getAllByRole("button", { name: "More" })[0]!);
  const group = within(screen.getByRole("group", { name: "Position and size of Widget a" }));
  await userEvent.click(group.getByRole("button", { name: "Move down" }));
  await waitFor(() => expect(calls.filter((c) => c.url.endsWith("/layout")).at(-1)?.body).toEqual({ rows: 2, items: [{ id: "a", row: 1, col: 0, size: "medium" }], rev: 4 }));  // rev: a stale copy is refused (409)
  await waitFor(() => expect(screen.getAllByRole("button", { name: /Add a widget here/ })).toHaveLength(2));
  fireEvent.click(screen.getAllByRole("button", { name: /Add a widget here/ })[0]!);   // row 1, the whole width
  await userEvent.click(screen.getByRole("button", { name: "Bar chart" }));
  await userEvent.click(screen.getByRole("button", { name: "Add widget to the slot" }));
  await waitFor(() => expect(calls.find((c) => c.url.endsWith("/widgets"))?.body).toEqual({ kind: "bar", table: "gold_x", row: 0, col: 0 }));
  await waitFor(() => expect(screen.getAllByRole("button", { name: /Add a widget here/ })[0]).toHaveAccessibleName("Add a widget here, row 1, column 7"));
  fireEvent.click(screen.getAllByRole("button", { name: /Add a widget here/ })[0]!);
  await userEvent.type(screen.getByLabelText("Your message"), "add cash by entity as bars{Enter}");   // ST2: Enter sends, as in every composer
  await waitFor(() => expect(calls.find((c) => c.url.endsWith("/talk"))?.body).toEqual({ text: "add cash by entity as bars" }));
  expect(await screen.findByText(/Added Cash by entity/)).toBeInTheDocument();
  expect(await screen.findByText("Widget q")).toBeInTheDocument();   // placed at once, no Accept step
  await userEvent.click(screen.getByRole("button", { name: "Send for approval" }));
  await waitFor(() => expect(calls.some((c) => c.url.endsWith("/submit") && c.method === "POST")).toBe(true));
  expect(await screen.findByText(/waiting for the head of data or the sponsor/)).toBeInTheDocument();
});

test("the approver sees the preview with sources, approves, or sends it back with a reason", async () => {
  const calls = mock(board({ status: "submitted", submitted_by: "Anna", can: { edit: false, submit: false, approve: true },
    review: { built_by: "Mei Chen", submitted_by: "Anna", submitted_at: "2026-10-11T14:20:00", checks: [
      { title: "Every tile names where it comes from", detail: "Reads monthly report holdings.", ok: true },
      { title: "The benchmark is the signed definition", detail: "No signed benchmark version is on record for this project.", ok: null }] } }));
  studio();
  expect(await screen.findByRole("region", { name: "Waiting for your approval" })).toBeInTheDocument();
  expect(screen.getByRole("list", { name: "Widgets and where they read" })).toHaveTextContent("Widget a: reads monthly report holdings");
  expect(screen.queryByRole("button", { name: /Add a widget here/ })).toBeNull();   // the approver does not edit
  const lumen = screen.getByRole("group", { name: "What Lumen checked" });   // V6 (D3): each check from a record; no record, "not checked"
  expect(within(lumen).getByText("Every tile names where it comes from")).toBeInTheDocument();
  expect(within(lumen).getByText(/not checked/)).toBeInTheDocument();
  expect(screen.getByText(/Before this: Mei Chen built the dashboard with Lumen\. Anna sent it for approval/)).toBeInTheDocument();
  expect(screen.getByText("Approving lets Mei choose where it is delivered. It does not send anything yet.")).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText(/Note to .* \(needed only if you send it back\)/), "Add cash by entity");
  await userEvent.click(screen.getByRole("button", { name: "Send back" }));
  await waitFor(() => expect(calls.filter((c) => c.url.endsWith("/send-back")).at(-1)?.body).toEqual({ reason: "Add cash by entity" }));
});

test("the approver can approve and publish", async () => {
  const calls = mock(board({ status: "submitted", can: { edit: false, submit: false, approve: true } }));
  studio();
  await userEvent.click(await screen.findByRole("button", { name: "Approve" }));
  await waitFor(() => expect(calls.some((c) => c.url.endsWith("/approve"))).toBe(true));
  expect((await screen.findAllByText(/Published/)).length).toBeGreaterThan(0);
});

test("Consume shows the grid of the published version with the refresh line", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url.endsWith("/view")) return json(200, { id: "dash-1", title: "Board pack", project_id: "EV-1", tiles: [{ id: "t-a", title: "Widget a", kpi: "", sql: "", spec: {}, note: "", state: "accepted" }], audience: [], refresh: "same",
      layout: { rows: 1, items: [item("a", 0, 0, "full")] } });
    if (url.endsWith("/refresh")) return json(200, { ...FRESH, warning: "The last refresh failed on 10 Oct, so these figures are not refreshed since 9 Oct", link: "/centre/operations" });
    if (url.endsWith("/data")) return json(200, { spec: { mark: "line" }, rows: [], data_used: { tables: [], last_refresh: null } });
    return json(404, { message: "no" });
  }));
  render(<ThemeProvider><MemoryRouter initialEntries={["/centre/consume/d/dash-1"]}><Routes><Route path="/centre/consume/d/:dashboardId" element={<DashboardView />} /></Routes></MemoryRouter></ThemeProvider>);
  expect(await screen.findByText("Widget a")).toBeInTheDocument();
  expect(await screen.findByText(/Updated daily at 06:00 after the pipeline run/)).toBeInTheDocument();
  expect(screen.getByText(/The last refresh failed on 10 Oct/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Add a widget here|Move up/ })).toBeNull();
});

// ST2: Send is never greyed out, an empty send says what to do, one heading.
test("Lumen in the studio: always active, says what to do when empty", async () => {
  const calls = mock(board());
  studio();
  await screen.findByText("Widget a");
  expect(screen.getAllByRole("heading", { name: "Talk to Lumen" })).toHaveLength(1);
  const send = within(screen.getByRole("form", { name: "Message Lumen" })).getByRole("button", { name: "Send" });
  expect(send).toBeEnabled();
  await userEvent.click(send);
  expect(await screen.findByText("Type what you want, for example: cash by entity as bars")).toBeInTheDocument();
  expect(calls.some((c) => c.url.endsWith("/talk"))).toBe(false);
});

test("STUDIO2: a talk is applied at once: reply shown, canvas reloaded, step moves on, no Accept button", async () => {
  const calls = mock(board());
  studio();
  await screen.findByText("Widget a");
  await userEvent.type(screen.getByLabelText("Your message"), "cash by entity as bars{Enter}");
  expect(await screen.findByText("Added Cash by entity.")).toBeInTheDocument();
  expect(await screen.findByText("Widget q")).toBeInTheDocument();
  expect(calls.some((c) => c.url.endsWith("/studio/dash-1") && c.method === "GET")).toBe(true);
  expect(screen.queryByRole("button", { name: "Accept" })).toBeNull();
  await waitFor(() => expect(screen.getByText(/step 2/)).toBeInTheDocument());
});

test("STUDIO2: clicking a widget selects it, the chat says about this chart, and the talk carries it", async () => {
  const calls = mock(board());
  studio();
  await screen.findByText("Widget a");
  fireEvent.click(screen.getByText("Widget a"));
  expect(await screen.findByText(/About this chart: Widget a/)).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Your message"), "make it dots{Enter}");
  await waitFor(() => expect(calls.filter((c) => c.url.endsWith("/talk")).at(-1)?.body).toEqual({ text: "make it dots", widget: "a" }));
  expect(await screen.findByText("Cash by entity, dots")).toBeInTheDocument();
  expect(screen.queryByText("Widget a")).toBeNull();   // replaced where it stood
});

test("STUDIO2: Undo takes the last change back", async () => {
  const calls = mock(board());
  studio();
  await screen.findByText("Widget a");
  await userEvent.type(screen.getByLabelText("Your message"), "cash by entity{Enter}");
  await screen.findByText("Widget q");
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await waitFor(() => expect(calls.some((c) => c.url.endsWith("/undo") && c.method === "POST")).toBe(true));
  await waitFor(() => expect(screen.queryByText("Widget q")).toBeNull());
});

test("STUDIO2: the history drawer lists steps, goes back, compares, and offers to discard the draft", async () => {
  const calls = mock(board());
  studio();
  await screen.findByText("Widget a");
  await userEvent.type(screen.getByLabelText("Your message"), "cash by entity{Enter}");
  await screen.findByText("Widget q");
  await userEvent.click(screen.getByRole("button", { name: "History" }));
  const drawer = await screen.findByRole("complementary", { name: "History" });
  expect(await within(drawer).findByText(/Lumen's starter/)).toBeInTheDocument();
  await userEvent.click(within(drawer).getByRole("button", { name: "Compare with now" }));
  expect(await within(drawer).findByText("Added since: Cash by entity")).toBeInTheDocument();
  await userEvent.click(within(drawer).getByRole("button", { name: "Go back here" }));
  await waitFor(() => expect(calls.some((c) => /history\/1\/restore$/.test(c.url) && c.method === "POST")).toBe(true));
  expect(within(drawer).getByRole("button", { name: "Discard draft" })).toBeInTheDocument();
  expect(within(drawer).queryByRole("button", { name: "Withdraw from approval" })).toBeNull();
});

test("STUDIO2: a sent draft can be withdrawn from the history drawer", async () => {
  const calls = mock(board({ status: "submitted", can: { edit: false, submit: false, approve: false } }));
  studio();
  await userEvent.click(await screen.findByRole("button", { name: "History" }));
  await userEvent.click(await screen.findByRole("button", { name: "Withdraw from approval" }));
  await waitFor(() => expect(calls.some((c) => c.url.endsWith("/withdraw") && c.method === "POST")).toBe(true));
});

test("STUDIO2: every earlier control is still on the page", async () => {
  const calls = mock(board());
  const ok = vi.spyOn(window, "confirm").mockReturnValue(true);
  studio();
  await screen.findByText("Widget a");
  expect(screen.getByText(/Updated daily at 06:00/)).toBeInTheDocument();                      // refresh line
  expect(screen.getByRole("button", { name: "Add a row" })).toBeInTheDocument();                // layout
  expect(screen.getByRole("button", { name: "Add widget to the slot" })).toBeInTheDocument();   // widgets add
  expect(screen.getByRole("button", { name: "Place in the slot" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Add a picture" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Send for approval" })).toBeEnabled();
  await userEvent.click(screen.getByRole("button", { name: "Discard draft" }));
  await waitFor(() => expect(calls.some((c) => c.method === "DELETE")).toBe(true));
  ok.mockRestore();
});

test("OP1: the thread is kept per dashboard: a reload shows it, a fresh talk empties it", async () => {
  const calls = mock(board({ talk: [{ by: "person", text: "I prefer blue lines" }, { by: "lumen", text: "Noted, blue lines." }] }));
  studio();
  expect(await screen.findByText("I prefer blue lines")).toBeInTheDocument();
  expect(screen.getByText("Noted, blue lines.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Start a fresh talk" }));
  await waitFor(() => expect(screen.queryByText("I prefer blue lines")).toBeNull());
  expect(calls.find((c) => c.url.endsWith("/ask"))?.body).toEqual({ new_talk: true });
});

test("OP1: Lumen's tile list stays in the library and places in the chosen slot", async () => {
  const calls = mock(board());
  studio();
  await screen.findByText("Widget a");
  fireEvent.click(screen.getAllByRole("button", { name: /Add a widget here/ })[1]!);
  await userEvent.click(screen.getByRole("button", { name: "Place in the slot" }));
  await waitFor(() => expect(calls.find((c) => c.url.endsWith("/widgets"))?.body).toEqual({ kind: "lumen", dashboard_id: "dash-9", tile_id: "t-9", row: 1, col: 0 }));
});

test("a return figure shows as a percentage and moves in points, never a percent of a percent", async () => {
  const { Figure } = await import("../cxui/Chart");
  render(<Figure label="Portfolio return" rows={[{ value: 0.0103 }, { value: 0.0024 }]} />);
  expect(screen.getByText("1.0%")).toBeInTheDocument();
  expect(screen.getByText(/Up 0.8 points on the period before/)).toBeInTheDocument();
  expect(screen.queryByText(/334/)).toBeNull();
});

test("the studio is mounted with the other Build pages, inside the shell with the top bar", async () => {
  // App.tsx mounts every ui/src/v1/*/routes.tsx under /centre inside CentreShell; the studio registers the same way as the Build page
  const [mine, build] = await Promise.all([import("./routes"), import("../b6/routes")]);
  expect(mine.routes.map((r) => r.path)).toEqual(["build/p/:projectId/studio"]);
  expect(build.routes.map((r) => r.path)).toContain("build/p/:projectId");
});

const STARTER = { status: "proposed" as const, pack_version: 2, from_intent: true, at: "2026-10-10T15:40:00", why: ["From the signed intent KPIs: Total holdings, Portfolio return.", "Every tile reads this project's gold tables only."] };

test("H10: the starter banner offers accept, ask and send for approval; send accepts first", async () => {
  const calls = mock(board({ starter: STARTER, tiles: [{ id: "t-a", title: "Widget a", state: "proposed", spec: {}, starter: true }] }));
  studio();
  const banner = await screen.findByRole("region", { name: "Lumen's starter dashboard" });
  expect(within(banner).getByRole("list", { name: "Why Lumen chose these" })).toHaveTextContent("signed intent");
  expect(screen.queryByRole("button", { name: "Not this" })).toBeNull();            // starter tiles are not in the chat's proposals
  await userEvent.click(within(banner).getByRole("button", { name: "Add something specific" }));
  await userEvent.click(within(banner).getByRole("button", { name: "Send for approval" }));
  await waitFor(() => expect(calls.filter((c) => c.method === "POST").map((c) => c.url.split("/").slice(-2).join("/"))).toEqual(expect.arrayContaining(["starter/accept", "dash-1/submit"])));
});

test("H10: Accept as it is accepts the starter", async () => {
  const calls = mock(board({ starter: STARTER }));
  studio();
  await userEvent.click(await screen.findByRole("button", { name: "Accept as it is" }));
  await waitFor(() => expect(calls.some((c) => c.url.endsWith("/starter/accept"))).toBe(true));
  expect(await screen.findByText("Accepted")).toBeInTheDocument();
});

test("V6B: the side panel names the starter's tiles on the grid instead of saying Lumen suggested none", async () => {
  mock(board({ starter: STARTER, library: { ...board().library, lumen: [] }, tiles: [{ id: "t-a", title: "Portfolio return in the latest month", state: "proposed", spec: {}, starter: true }] }));
  studio();
  expect(await screen.findByText(/Lumen's starter tiles are on the grid: Portfolio return in the latest month/)).toBeInTheDocument();
  expect(screen.queryByText(/has not suggested any tiles/)).toBeNull();
});
