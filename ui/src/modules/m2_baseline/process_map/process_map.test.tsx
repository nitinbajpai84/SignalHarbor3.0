// slow under a full parallel run; the 5 s default timed out a different test each time
vi.setConfig({ testTimeout: 30000 });
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import type { KpiMap, MapStep, ProcessMap } from "../api";
import { mapCopy as t } from "../copy";
import ProcessMapScreen from "./ProcessMapScreen";

// M2-P03 screen: the swimlane in the old look, in its five states. fetch is stubbed.

const BASE = "/api/modules/m2_baseline/baselines/b1/process-map";
const prov = (value: string | null, mark: "stated" | "guessed" | "unknown" = "stated") => ({ value, mark, by: "Arjun Rao", at: "now", from: "meeting" });
const step = (id: string, lane: string, text: string, over: Partial<MapStep> = {}): MapStep => ({
  id, lane, text, order: 1, manual: false, confirmed: true, from: "a1", state: "proposal", by: "Lens", owner: "Arjun Rao", mark: "stated", tracking: null, ...over,
});
const KPI: KpiMap = {
  id: "k1", name: "Funding capacity", definition: prov("Cash available to meet capital calls"), drawn: true, removed: 0,
  lanes: ["Bank", "Finance", "Investments", "Committee"],
  steps: [
    step("s1", "Bank", "Sends statement, daily"),
    step("s2", "Finance", "Downloads file"),
    step("s3", "Finance", "Adjusts in workbook", { manual: true }),
    step("s4", "Investments", "Checks the figure", { confirmed: false, mark: "to_confirm" }),
    step("s5", "Committee", "Reads the monthly pack"),
  ],
  counts: { answers: 1, to_confirm: 1, manual: 1 },
  tracking: { status: prov(null, "unknown"), tentative_date: prov(null, "unknown"), next_step: prov(null, "unknown") },
};
const MAPS: ProcessMap = {
  baseline_id: "b1", signed: false, kpis: [KPI],
  statuses: [{ id: "tracked_now", label: "Tracked now" }, { id: "partly", label: "Partly tracked" }, { id: "not_tracked", label: "Not tracked" }],
};

function show(handler: (url: string, init?: RequestInit) => Response | Promise<Response>) {
  const calls: { url: string; method: string; body: unknown }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, method: init?.method ?? "GET", body: init?.body ? JSON.parse(String(init.body)) : undefined });
    return handler(url, init);
  }));
  render(
    <MemoryRouter initialEntries={["/process-map/b1"]}>
      <Routes>
        <Route path="/process-map/:baselineId" element={<ProcessMapScreen />} />
      </Routes>
    </MemoryRouter>,
  );
  return calls;
}
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

describe("process map screen", () => {
  afterEach(() => vi.unstubAllGlobals());

  test("a missing step an owner mentioned is dashed and names the person to ask", async () => {
    const wei = step("s6", "Risk", "Works out exposure by issuer", { confirmed: false, mark: "to_confirm", ask: "Wei Chen" });
    show(() => json({ ...MAPS, kpis: [{ ...KPI, lanes: [...KPI.lanes, "Risk"], steps: [...KPI.steps, wei] }] }));
    const card = await screen.findByRole("button", { name: /Works out exposure by issuer/ });
    expect(within(card).getByText(t.askToConfirm("Wei Chen"))).toBeInTheDocument();
    expect(card).toHaveStyle({ borderStyle: "dashed" });
  });

  test("populated: lanes down the left, steps across, manual tag, dashed unconfirmed step, legend, definitions", async () => {
    show(() => json(MAPS));
    await screen.findByRole("group", { name: t.panelTitle });
    expect(screen.getAllByText(/^Step \d$/).map((e) => e.textContent)).toEqual(["Step 1", "Step 2", "Step 3", "Step 4", "Step 5"]);
    expect([...document.querySelectorAll(".n2-lane-label")].map((e) => e.textContent)).toEqual(KPI.lanes);
    const manual = screen.getByRole("button", { name: /Adjusts in workbook/ });
    expect(manual).toHaveClass("n2-step", "manual");
    expect(within(manual).getByText(t.manualTag)).toHaveClass("n2-step-flag");
    expect(screen.getByRole("button", { name: /Sends statement/ })).not.toHaveClass("manual");
    expect(screen.getByRole("button", { name: /Checks the figure/ })).toHaveStyle({ borderStyle: "dashed" });
    expect(screen.getByRole("button", { name: /Sends statement/ })).not.toHaveStyle({ borderStyle: "dashed" });
    expect(screen.getByText(t.legendManual)).toBeInTheDocument();
    expect(screen.getByText(t.legendSystem)).toBeInTheDocument();
    expect(screen.getByText(t.lens(1, 1, 1))).toBeInTheDocument();
    expect(within(manual).getByText(new RegExp(t.trackingUnknown))).toHaveClass("n2-step-kpi");
    expect(screen.getByRole("heading", { name: t.defsTitle })).toBeInTheDocument();
    expect(screen.getByText("Cash available to meet capital calls")).toBeInTheDocument();
  });

  test("loading", async () => {
    show(() => new Promise<Response>(() => undefined));
    expect(await screen.findByRole("status")).toBeInTheDocument();
  });

  test("empty: no measures", async () => {
    show(() => json({ ...MAPS, kpis: [] }));
    expect(await screen.findByText(t.empty)).toBeInTheDocument();
  });

  test("error", async () => {
    show(() => json({ error: "x" }, 500));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  test("refused: a role without access", async () => {
    show(() => json({ error: "forbidden", message: "no" }, 403));
    expect(await screen.findByRole("alert")).toHaveTextContent(/access/i);
  });

  test("a map that was never drawn says so, and a drawn one with no steps says what to do", async () => {
    show(() => json({ ...MAPS, kpis: [{ ...KPI, drawn: false, steps: [], lanes: [] }] }));
    expect(await screen.findByText(t.notDrawn)).toBeInTheDocument();
  });

  test("a person confirms, edits, removes and adds a step; each goes to the server and the map follows", async () => {
    const user = userEvent.setup();
    const calls = show((url, init) => {
      if (init?.method === "POST" && url.endsWith("/validate")) {
        return json({ ...KPI, steps: KPI.steps.map((s) => (s.id === "s4" ? { ...s, confirmed: true, mark: "stated", state: "validated", by: "Pat" } : s)), counts: { ...KPI.counts, to_confirm: 0 } });
      }
      if (init?.method === "PUT" && url.includes("/steps/")) return json({ ...KPI, steps: KPI.steps.map((s) => (s.id === "s2" ? { ...s, text: "Downloads by hand", manual: true, state: "edited" } : s)) });
      if (init?.method === "DELETE") return json({ ...KPI, steps: KPI.steps.filter((s) => s.id !== "s5"), removed: 1 });
      if (init?.method === "POST") return json({ ...KPI, steps: [...KPI.steps, step("added-1", "Tax adviser", "Reviews it", { state: "validated", from: "added by Pat", by: "Pat" })] });
      return json(MAPS);
    });
    await user.click(await screen.findByRole("button", { name: /Checks the figure/ }));
    await user.click(screen.getByRole("button", { name: t.confirm }));
    await waitFor(() => expect(screen.getByRole("button", { name: /Checks the figure/ })).not.toHaveStyle({ borderStyle: "dashed" }));
    expect(screen.getByText(t.lens(1, 0, 1))).toBeInTheDocument();
    expect(calls.at(-1)).toMatchObject({ method: "POST", url: `${BASE}/k1/steps/s4/validate` });

    await user.click(screen.getByRole("button", { name: /Downloads file/ }));
    await user.click(screen.getByRole("button", { name: t.edit }));
    const editor = within(screen.getByRole("group", { name: t.selected }));
    await user.clear(editor.getByLabelText(t.what));
    await user.type(editor.getByLabelText(t.what), "Downloads by hand");
    await user.click(editor.getByLabelText(t.isManual));
    await user.click(editor.getByRole("button", { name: t.save }));
    await screen.findByRole("button", { name: /Downloads by hand/ });
    expect(calls.at(-1)).toMatchObject({ method: "PUT", url: `${BASE}/k1/steps/s2`, body: { lane: "Finance", text: "Downloads by hand", manual: true } });

    await user.click(screen.getByRole("button", { name: /Reads the monthly pack/ }));
    await user.click(screen.getByRole("button", { name: t.remove }));
    await waitFor(() => expect(screen.queryByRole("button", { name: /Reads the monthly pack/ })).toBeNull());
    expect(screen.getByText(t.removedNote(1))).toBeInTheDocument();

    const addForm = screen.getByRole("heading", { name: t.addTitle }).closest("section") as HTMLElement;
    await user.type(within(addForm).getByLabelText(t.lane), "Tax adviser");
    await user.type(within(addForm).getByLabelText(t.what), "Reviews it");
    await user.click(within(addForm).getByRole("button", { name: t.add }));
    await screen.findByRole("button", { name: /Reviews it/ });
    expect(calls.at(-1)).toMatchObject({ method: "POST", url: `${BASE}/k1/steps`, body: { lane: "Tax adviser", text: "Reviews it", manual: false } });
  });

  test("tracking status, tentative date and next step are saved", async () => {
    const user = userEvent.setup();
    const calls = show((_url, init) =>
      init?.method === "PUT"
        ? json({ ...KPI, tracking: { status: prov("not_tracked"), tentative_date: prov("2027-03-31"), next_step: prov("Ask the bank for a feed") } })
        : json(MAPS),
    );
    await screen.findByRole("group", { name: t.panelTitle });
    await user.selectOptions(screen.getByLabelText(t.status), "not_tracked");
    await user.type(screen.getByLabelText(t.tentativeDate), "2027-03-31");
    await user.type(screen.getByLabelText(t.nextStep), "Ask the bank for a feed");
    await user.click(screen.getByRole("button", { name: t.save }));
    await waitFor(() => expect(calls.at(-1)?.method).toBe("PUT"));
    expect(calls.at(-1)).toMatchObject({ url: `${BASE}/k1/tracking`, body: { status: "not_tracked", tentative_date: "2027-03-31", next_step: "Ask the bank for a feed" } });
  });

  test("a signed baseline is read-only: no draw, no edit, no add", async () => {
    const user = userEvent.setup();
    show(() => json({ ...MAPS, signed: true }));
    await screen.findByRole("group", { name: t.panelTitle });
    expect(screen.getByText("Signed: read-only")).toBeInTheDocument(); // the one banner every screen shares
    expect(screen.queryByRole("button", { name: t.draw })).toBeNull();
    expect(screen.queryByRole("heading", { name: t.addTitle })).toBeNull();
    await user.click(screen.getByRole("button", { name: /Sends statement/ }));
    expect(screen.queryByRole("button", { name: t.edit })).toBeNull();
  });

  test("drawing from the answers replaces the map with the server's", async () => {
    const user = userEvent.setup();
    show((_url, init) => (init?.method === "POST" ? json({ ...MAPS, kpis: [{ ...KPI, steps: KPI.steps.slice(0, 2), counts: { answers: 1, to_confirm: 0, manual: 0 } }] }) : json({ ...MAPS, kpis: [{ ...KPI, drawn: false, steps: [] }] })));
    await user.click(await screen.findByRole("button", { name: t.draw }));
    await screen.findByText(t.lens(1, 0, 0));
    expect(screen.getByRole("button", { name: t.redraw })).toBeInTheDocument();
  });
});
