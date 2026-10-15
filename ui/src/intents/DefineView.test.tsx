import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { tabFrom } from "./define/DefineTabs";
import DefineView, { clockTone, dateOk, mmss, quarterOn, secondsLeft } from "./views/DefineView";

// Define inside an intent (file 26). The wrapped module 1 board is replaced by a small tile with the same hooks (data-cluster, the
// name button and the "Move to" menu); fetch is stubbed with synthetic data.

vi.mock("../modules/m1_intent/define/DefineScreen", () => ({
  default: () => (
    <div data-cluster="c1">
      <button type="button" className="df-cluster__name">Late capital calls</button>
      <select aria-label="Move to" value="" onChange={() => { throw new Error("the board's own move must not run"); }}>
        <option value="" disabled>Move to</option>
        <option value="must">Must</option>
        <option value="future">Future</option>
      </select>
    </div>
  ),
}));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const ITEMS = { made: 1, of: 3, shelf_counts: { must: 1, should: 1, good_to_have: 0, future: 0, not_placed: 1 }, unticked: 1, parked_late: 0, ungoverned: 1 };
const DATA = {
  intent: { id: "ini-1", type: "initiative", title: "Manager benchmarks", purpose: "One view of manager returns", state: "open", organiser_name: "Janet Shaw" },
  stage: { state: "open", opened_at: "2026-10-06T09:00:00Z", closed_at: null }, tier: "content", wall_session_id: "s1", organiser: true,
  start_blocked: null, session: null, decisions: { made: 1, of: 3 }, open_items: ITEMS, signed: false, today: "2026-10-07",
};

function mock(over: Record<string, unknown> = {}) {
  const sent: { url: string; body: Record<string, unknown> }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST" || init?.method === "PUT") {
      const body = init.body ? JSON.parse(String(init.body)) : {};
      sent.push({ url, body });
      if (url.endsWith("/define/shelf") && body.shelf === "must") return json(409, { message: "Needs who may see and who resolves it before it can sit on Must.", refused: true });
      if (url.endsWith("/define/hold")) return json(200, { ...DATA, ...over, held: true });
      if (url.endsWith("/define/session")) return json(200, { ...DATA, ...over, stage: { ...DATA.stage, state: "closed", closed_at: "2026-10-07T10:00:00Z" } });
      if (url.endsWith("/charter")) return json(200, { state: "signing", organiser: true, can_draft: false, no_result: false, charter: { problems: [{}, {}] } });
      if (url.endsWith("/build-ready/check")) return json(200, { todo: [{}, {}, {}] });
      return json(200, {});
    }
    if (url.endsWith("/define/session")) return json(200, { ...DATA, ...over });
    if (url.endsWith("/clock")) return json(200, { stage: { day_of: 5, working_days_total: 6 }, box: { working_days_left: 3 } });
    if (url.includes("/charter")) return json(200, { state: "together", organiser: true, can_draft: true, no_result: false, charter: null });
    return json(404, {});
  }));
  return sent;
}
const view = (search = "") => render(
  <MemoryRouter initialEntries={[`/centre/intent/ini-1/define${search}`]}>
    <Routes><Route path="/centre/intent/:intentId/define" element={<DefineView />} /></Routes>
  </MemoryRouter>,
);

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

test("?tab= picks the tab; anything else is clusters", async () => {
  expect(tabFrom("?tab=glossary")).toBe("glossary");
  expect(tabFrom("?tab=process-map")).toBe("process-map");
  expect(tabFrom("?tab=nothing")).toBe("clusters");
  expect(tabFrom("")).toBe("clusters");
  mock(); view("?tab=process-map");
  expect(await screen.findByRole("link", { name: "Process map" })).toHaveAttribute("aria-current", "page");
  expect(screen.queryByText("Late capital calls")).not.toBeInTheDocument();
});

test("head, stage clock and the board on the clusters tab", async () => {
  mock(); view();
  expect(await screen.findByText("Manager benchmarks")).toBeInTheDocument();
  expect(await screen.findByText("Day 5 of 6. 3 days left on the intent.")).toBeInTheDocument();
  expect(screen.getByText("Late capital calls")).toBeInTheDocument();
  expect(screen.getByText("Solid: all six fields confirmed. Dashed: something is missing.")).toBeInTheDocument();
  expect(screen.getByTestId("session-clock")).toHaveTextContent("90:00");
  expect(screen.getByText("Decisions: 1 of 3")).toBeInTheDocument();
});

test("a move to Must of an ungoverned group is refused with the missing fields and a way to Lens", async () => {
  const sent = mock(); view();
  fireEvent.change(await screen.findByLabelText("Move to"), { target: { value: "must" } });
  expect(await screen.findByText(/Needs who may see and who resolves it before it can sit on Must\./)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Open Lens's definition" })).toBeInTheDocument();
  expect(sent.find((s) => s.url.endsWith("/define/shelf"))?.body).toEqual({ cluster_id: "c1", shelf: "must" });
});

test("Future asks a reason and a review date later than today", async () => {
  const sent = mock(); view();
  fireEvent.change(await screen.findByLabelText("Move to"), { target: { value: "future" } });
  const dialog = await screen.findByRole("dialog", { name: "Park Late capital calls for later" });
  const park = screen.getByRole("button", { name: "Park it" });
  expect(park).toBeDisabled();
  expect(screen.getByLabelText("Review date")).toHaveValue("2027-01-07");
  fireEvent.change(screen.getByLabelText("Review date"), { target: { value: "2026-10-07" } });
  expect(screen.getByText("Choose a date after today.")).toBeInTheDocument();
  fireEvent.blur(screen.getByLabelText("Why is it parked?"));
  expect(screen.getByText("Please say why this is parked for later.")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Why is it parked?"), { target: { value: "After the audit" } });
  fireEvent.change(screen.getByLabelText("Review date"), { target: { value: "2027-02-01" } });
  fireEvent.click(park);
  await waitFor(() => expect(sent.find((s) => s.url.endsWith("/define/shelf"))?.body).toEqual(
    { cluster_id: "c1", shelf: "future", reason: "After the audit", review_date: "2027-02-01" }));
  await waitFor(() => expect(dialog).not.toBeInTheDocument()); // parked: the dialog closes
});

test("session clock counts down, turns amber and red, and runs over", () => {
  const s = { started_at: "2026-10-07T10:00:00Z", ended_at: null, planned_minutes: 90, extensions: [] };
  const at = (min: number) => Date.parse("2026-10-07T10:00:00Z") + min * 60000;
  expect(mmss(secondsLeft(s, at(0)))).toBe("90:00");
  expect(clockTone(secondsLeft(s, at(76)))).toBe("amber");
  expect(clockTone(secondsLeft(s, at(86)))).toBe("red");
  expect(secondsLeft(s, at(94))).toBe(-240);
  expect(mmss(secondsLeft(s, at(94)))).toBe("04:00");
  expect(secondsLeft({ ...s, extensions: [{ minutes: 15 }] }, at(94))).toBe(660);
  expect(secondsLeft({ ...s, started_at: null }, at(0))).toBe(5400);
  expect(quarterOn("2026-11-30")).toBe("2027-02-28");
  expect(dateOk("2026-10-08", "2026-10-07")).toBe(true);
  expect(dateOk("2026-10-07", "2026-10-07")).toBe(false);
});

test("closing writes the charter draft and closes the stage only; the intent state is not touched", async () => {
  const sent = mock(); view();
  fireEvent.click(await screen.findByRole("button", { name: "Close the session and write the charter draft" }));
  expect(screen.getByText("1 group has no shelf")).toBeInTheDocument();
  expect(screen.getByText("1 group on Must or Should not ticked")).toBeInTheDocument();
  await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Close and write the charter draft" })); });
  expect(await screen.findByText(/Charter draft written from 2 ticked groups\. 3 gaps found\./)).toBeInTheDocument();
  expect(sent.find((s) => s.url.endsWith("/define/session"))?.body).toEqual({ action: "close" });
  expect(sent.some((s) => s.url.endsWith("/state"))).toBe(false);
  expect(screen.getByRole("link", { name: "Open the charter" })).toHaveAttribute("href", "/centre/intent/ini-1/charter");
});

test("start is disabled with the reason when nobody is invited", async () => {
  mock({ start_blocked: "Name a start time and invite the committee first." }); view();
  expect(await screen.findByRole("button", { name: "Start the ninety-minute session" })).toBeDisabled();
  expect(screen.getByText("Name a start time and invite the committee first.")).toBeInTheDocument();
});

test("Hold the room goes to the intent's own hold route, not the wall's pause", async () => {
  const sent = mock({ session: { started_at: new Date().toISOString(), ended_at: null, planned_minutes: 90, extensions: [] } }); view();
  fireEvent.click(await screen.findByRole("button", { name: "Hold the room" }));
  await waitFor(() => expect(sent.some((s) => s.url.endsWith("/define/hold") && s.body.held === true)).toBe(true));
  expect(sent.some((s) => s.url.includes("/pause"))).toBe(false);
});

test("Data sources and Catalogue do not ask for a baseline when none is linked", async () => {
  const sent = mock({ has_baseline: false }); view("?tab=catalogue");
  expect(await screen.findByText("No baseline is linked to this intent yet.")).toBeInTheDocument();
  expect(sent).toEqual([]);
});

test("the close dialog names the groups still open, as the charter draft will (F50)", async () => {
  mock({ open_items: { ...ITEMS, open_groups: ["Late capital calls", "Manual pack"] } }); view();
  fireEvent.click(await screen.findByRole("button", { name: "Close the session and write the charter draft" }));
  expect(screen.getByText("2 groups are still open: Late capital calls, Manual pack. It stays out of the charter.")).toBeInTheDocument();
  expect(screen.queryByText(/Nothing is open/)).toBeNull();
});
