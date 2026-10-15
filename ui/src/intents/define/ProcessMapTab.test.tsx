import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import ProcessMapTab from "./ProcessMapTab";

// Spec 27 Screens A and B. fetch is stubbed with a synthetic map.

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const cell = (value: unknown, mark = "guessed") => ({ value: mark === "unknown" ? null : value, mark, by: "Lens", at: "2026-10-07T01:00:00Z", from: "Card: Fund pricing", agent: "lens" });
const proc = (id: string, name: string, over: Record<string, unknown> = {}) => ({
  id, cluster: "ops", name: cell(name), owner: cell(null, "unknown"), trigger: cell(null, "unknown"), frequency: cell(null, "unknown"),
  inputs: cell(null, "unknown"), outputs: cell(null, "unknown"), systems: cell(["pas"]), steps: [], breaks: [], status: "guessed", confirmed: null, history: [], ...over,
});
const MAP = (over: Record<string, unknown> = {}, me: Record<string, unknown> = {}) => ({
  version: 3, state: "Drafted", tier: "write", drafted_at: "2026-10-07T01:00:00Z", drafted_from: { cards: 14, interviews: 2, documents: 3 },
  processes: [proc("p1", "Month-end fund pricing", { owner: { ...cell("harvey", "stated"), agent: undefined } }), proc("p2", "Capital calls")],
  questions: [{ id: "q1", process_id: "p2", topic: "steps", to_person: "harvey", text: "What are the steps of 'Capital calls'?", state: "open" }],
  clusters: [{ id: "ops", name: "Operations", cards: 2 }], people: { harvey: { name: "Harvey Rowley", role: "Fund Operations Manager" } }, systems: { pas: "Portfolio accounting system" },
  counters: { processes: 2, confirmed: 0, guessed: 1, edited: 1, steps: 0, steps_unknown: 1, questions_open: 1, questions_queued: 0, without_owner: 1, breaks_on_cards: 0, breaks_own_words: 0, measures_linked: 0, sources_linked: 0, state: "Drafted" },
  me: { person: "janet", name: "Janet Shaw", can_edit: true, can_draft: true, cards: {}, owns: [], ...me }, draft_blocked: null, ...over,
});

function mock(body: unknown) {
  vi.stubGlobal("fetch", vi.fn(async () => json(200, body)));
}
const view = (path = "/centre/intent/i1/define?tab=process-map") =>
  render(<MemoryRouter initialEntries={[path]}><ProcessMapTab intentId="i1" /></MemoryRouter>);

afterEach(() => vi.unstubAllGlobals());

test("list: the header line from the record, cards, owner chip, step strip empty state and the question badge", async () => {
  mock(MAP()); view();
  expect(await screen.findByText(/Mapped today by Lens from 14 cards, 2 interviews and 3 documents/)).toBeInTheDocument();
  expect(screen.getByText("Month-end fund pricing")).toBeInTheDocument();
  expect(screen.getByText("Harvey Rowley")).toBeInTheDocument();
  expect(screen.getByText("No owner yet")).toBeInTheDocument();
  expect(screen.getAllByText("No steps yet. Lens does not guess steps. The owner is asked.").length).toBe(2);
  expect(screen.getByText("1 question to Harvey")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Ask Lens to draft" })).toBeEnabled();
});

test("nothing drafted: the empty line, and the draft button says why it is disabled", async () => {
  mock(MAP({ processes: [], questions: [], drafted_at: null, clusters: [], draft_blocked: "Form clusters first. Lens drafts processes from them." })); view();
  expect(await screen.findByText("Lens has not drafted a map yet. Ask Lens to draft it, or add a process yourself.", { selector: "p.pmt-note" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Ask Lens to draft" })).toBeDisabled();
  expect(screen.getByText("Form clusters first. Lens drafts processes from them.")).toBeInTheDocument();
});

test("process card: only the named owner can confirm; others read why", async () => {
  mock(MAP()); view("/centre/intent/i1/define?tab=process-map&process=p1");
  expect(await screen.findByText("Only Harvey can confirm this.")).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "Confirm this process" })[0]).toBeDisabled();
});

test("process card as the owner: confirm is enabled and posts the version", async () => {
  mock(MAP({}, { person: "harvey", name: "Harvey Rowley", can_edit: false, can_draft: false, owns: ["p1"] }));
  view("/centre/intent/i1/define?tab=process-map&process=p1");
  const btn = await screen.findByRole("button", { name: "Confirm this process" });
  expect(btn).toBeEnabled();
  fireEvent.click(btn);
  await waitFor(() => expect((fetch as unknown as { mock: { calls: unknown[][] } }).mock.calls.some((c) => String(c[0]).endsWith("/p1/confirm"))).toBe(true));
});

test("a viewer who sees counts only gets the summary line", async () => {
  mock({ version: 1, state: "Drafted", tier: "counts", summary: "Process map: 7 processes, 4 confirmed", counters: { processes: 7, confirmed: 4 } }); view();
  expect(await screen.findByText("Process map: 7 processes, 4 confirmed")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Ask Lens to draft" })).toBeNull();
});

test("F29: an unknown step shows a dashed ? chip; Ask Harvey sends an ask change; source and system chips open popovers", async () => {
  const p1 = proc("p1", "Month-end fund pricing", {
    owner: { ...cell("harvey", "stated"), agent: undefined },
    trigger: { ...cell(null, "unknown") },
    systems: { ...cell(["pas"]), from: "Interview with Harvey Rowley", quote: "The pricing file arrives from the portfolio accounting system." },
  });
  mock(MAP({ processes: [p1], questions: [] }));
  view("/centre/intent/i1/define?tab=process-map&process=p1");
  expect(await screen.findAllByLabelText("Steps not known yet")).not.toHaveLength(0);
  fireEvent.click(await screen.findByRole("button", { name: "Ask Harvey" }));
  await waitFor(() => {
    const call = (fetch as unknown as { mock: { calls: [string, { body: string }][] } }).mock.calls.find((c) => String(c[1]?.body ?? "").includes('"op":"ask"'));
    expect(call).toBeTruthy();
  });
  fireEvent.click(screen.getByRole("button", { name: "Guessed by Lens from Interview with Harvey Rowley" }));
  expect(screen.getByText(/The pricing file arrives from the portfolio accounting system/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Portfolio accounting system" }));
  expect(screen.getByText(/from the company profile/)).toBeInTheDocument();
});
