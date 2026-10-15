import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";

import LensStrip, { DraftingLine, SendBackDialog } from "./LensStrip";

// The Lens strip, the drafting line and the send-back dialog (spec 44). fetch is stubbed with synthetic data.

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const order = ["mapping", "business_definition", "technical_definition", "catalogue_entry", "owners", "governed_state", "process_steps", "data_sources", "ambiguities"];
const cell = (kind: string, state: string, code = "M1", name = "Fund returns") => ({ cell_key: `${code}:${kind}`, kind, measure_code: code, name, state });
const base = (over: Record<string, unknown> = {}) => ({
  run: { state: "done", model_set_up: true, order }, reads: { documents: 14, interviews: 6, profile: true, pack: true },
  counts: {}, total: 0, drafted: 0, failed: [], questions: { mine_open: 0, waiting: 0, open_total: 0 }, my_questions: [], cells: {}, ...over,
});
function mock(lens: unknown, roles = ["company_admin"]) {
  const posts: { url: string; body: unknown }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") { posts.push({ url, body: init.body ? JSON.parse(String(init.body)) : {} }); return json(200, { outcome: "redrafted" }); }
    if (url === "/api/auth/me") return json(200, { display_name: "Janet Shaw", company_id: "co-a", roles });
    if (url === "/api/intents/i1/define/lens") return json(200, lens);
    return json(404, {});
  }));
  return posts;
}
afterEach(() => vi.unstubAllGlobals());

test("counts, source line and the questions chip come from the record", async () => {
  const cells = Object.fromEntries(order.map((k, i) => [`M1:${k}`, { ...cell(k, i < 5 ? "guessed" : "not_drafted"), value: "A draft" }]));
  mock(base({ total: 9, drafted: 5, cells, questions: { mine_open: 2, waiting: 4, open_total: 3 } }));
  render(<LensStrip intentId="i1" />);
  expect(await screen.findByText(/Lens has drafted 5 of 9 items for 1 measure\./)).toBeInTheDocument();
  expect(screen.getByText("Read: 14 documents, 6 interviews, the profile, the industry pack as suggestions")).toBeInTheDocument();
  expect(screen.getByText("Questions: 2 open for you, 4 waiting")).toBeInTheDocument();
  fireEvent.click(screen.getByText("Show each measure"));
  expect(screen.getByText("Business definition: Guessed")).toBeInTheDocument();
  expect(screen.getByText("Data sources: Not drafted")).toBeInTheDocument();
});

test("not started, no measures and no questions read as the spec says", async () => {
  mock(base({ run: { state: "idle", model_set_up: false, order } }));
  const { unmount } = render(<LensStrip intentId="i1" />);
  expect(await screen.findByText(/Not available yet: Lens has not started\. North starts it when Define opens\./)).toBeInTheDocument();
  expect(screen.queryByText(/Questions:/)).toBeNull();
  unmount();
  mock(base());
  render(<LensStrip intentId="i1" />);
  expect(await screen.findByText(/Not available yet: no measures to draft\./)).toBeInTheDocument();
});

test("no model line shows once a run has happened", async () => {
  mock(base({ run: { state: "done", model_set_up: false, order } }));
  render(<LensStrip intentId="i1" />);
  expect(await screen.findByText(/document reading is not set up for your company/)).toBeInTheDocument();
});

test("try again for failed items is for organiser and analyst, and starts a retry run", async () => {
  const lens = base({ total: 1, drafted: 0, failed: ["M1:owners"], cells: { "M1:owners": cell("owners", "failed") } });
  const posts = mock(lens);
  const { unmount } = render(<LensStrip intentId="i1" />);
  fireEvent.click(await screen.findByText("Try again for 1 item that failed"));
  await waitFor(() => expect(posts).toEqual([{ url: "/api/intents/i1/define/lens/run", body: { retry: true } }]));
  unmount();
  vi.unstubAllGlobals();
  mock(lens, ["participant"]);
  render(<LensStrip intentId="i1" />);
  await screen.findByText(/Lens has drafted/);
  expect(screen.queryByText("Try again for 1 item that failed")).toBeNull();
});

test("progress shows while a run is on", async () => {
  const cells = { "M1:mapping": cell("mapping", "guessed"), "M1:business_definition": cell("business_definition", "guessed"), "M1:technical_definition": cell("technical_definition", "drafting") };
  mock(base({ run: { state: "running", model_set_up: true, order }, total: 3, drafted: 2, cells }));
  render(<LensStrip intentId="i1" />);
  expect(await screen.findByText("Drafting 3 of 9 for Fund returns")).toBeInTheDocument();
});

test("questions panel lists mine and saves an answer", async () => {
  const posts = mock(base({ total: 1, cells: { "M1:owners": cell("owners", "guessed") }, questions: { mine_open: 1, waiting: 2, open_total: 1 },
    my_questions: [{ id: "q1", to: "harvey", about_cell: "M1:owners", text: "Who owns Fund returns?", term: "Fund returns", state: "open", kind: "owners" }] }));
  render(<LensStrip intentId="i1" />);
  fireEvent.click(await screen.findByText("Questions: 1 open for you, 2 waiting"));
  expect(screen.getByText("Who owns Fund returns?")).toBeInTheDocument();
  expect(screen.getByText("2 more questions are waiting")).toBeInTheDocument();
  const save = screen.getByText("Save my answer");
  expect(save).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Say it in your words"), { target: { value: "Harvey Rowley" } });
  fireEvent.click(save);
  await waitFor(() => expect(posts[0]).toEqual({ url: "/api/intents/i1/define/lens/questions/q1/answer", body: { answer: "Harvey Rowley" } }));
});

test("drafting line changes after five seconds and failure offers try again", () => {
  vi.useFakeTimers();
  const { rerender } = render(<DraftingLine state="drafting" />);
  expect(screen.getByText("Lens is drafting this.")).toBeInTheDocument();
  act(() => { vi.advanceTimersByTime(5100); });
  expect(screen.getByText("Taking longer than usual. You can carry on, the page is not blocked.")).toBeInTheDocument();
  const retry = vi.fn();
  rerender(<DraftingLine state="failed" canRetry suggestion="Net of fees" onTryAgain={retry} />);
  expect(screen.getByText("Lens could not draft this just now.")).toBeInTheDocument();
  expect(screen.getByText(/Suggestion from the industry pack, not a draft of yours/)).toBeInTheDocument();
  fireEvent.click(screen.getByText("Try again"));
  expect(retry).toHaveBeenCalled();
  vi.useRealTimers();
});

test("send back needs a note, warns the second time, and posts once", async () => {
  const posts = mock(base());
  const done = vi.fn();
  render(<SendBackDialog intentId="i1" cellKey="M1:owners" kind="the three owners" measure="Fund returns" second lead="Grace" onClose={() => {}} onDone={done} />);
  expect(screen.getByText("Send back the three owners for Fund returns to Lens")).toBeInTheDocument();
  expect(screen.getByText("This was already sent back once. Sending it back again passes it to Grace to decide.")).toBeInTheDocument();
  const send = screen.getByText("Send back");
  expect(send).toBeDisabled();
  fireEvent.blur(screen.getByLabelText("Tell Lens what to change"));
  expect(screen.getByText("Please say what to change.")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Tell Lens what to change"), { target: { value: "Name the data owner" } });
  fireEvent.click(send);
  await waitFor(() => expect(done).toHaveBeenCalledWith("redrafted", undefined));
  expect(posts).toEqual([{ url: "/api/intents/i1/define/lens/cells/M1%3Aowners/send-back", body: { note: "Name the data owner" } }]);
});

// F13: the cell opens from a run-detail row, owner-only actions, the question card, the queue, the total and "Not found yet".

const withCell = (over: Record<string, unknown> = {}, extra: Record<string, unknown> = {}) => base({
  total: 9, drafted: 1, measures: 1, cells: { "M1:business_definition": { ...cell("business_definition", "guessed"), value: "The monthly return.", source: "Lens, from policy.pdf", ...over } }, ...extra,
});
async function openCell(name: string) {
  fireEvent.click(await screen.findByText("Show each measure"));
  fireEvent.click(screen.getByText(name));
}

test("a run-detail row opens the cell, and the named owner gets Confirm, Not mine and Send back", async () => {
  const posts = mock(withCell({}, { may_act: ["M1:business_definition"], people: ["Aaron Lyle", "Harvey Rowley"] }), ["owner"]);
  render(<LensStrip intentId="i1" />);
  await openCell("Business definition: Guessed");
  expect(screen.getByText("The monthly return.")).toBeInTheDocument();
  expect(screen.getByText("Send back with a note")).toBeInTheDocument();
  fireEvent.click(screen.getByText("Not mine"));
  fireEvent.change(screen.getByLabelText("Who is it?"), { target: { value: "Aaron Lyle" } });
  fireEvent.click(screen.getByText("Not mine, it is Aaron Lyle"));
  await waitFor(() => expect(posts[0]).toEqual({ url: "/api/intents/i1/define/lens/cells/M1%3Abusiness_definition/not-mine", body: { person: "Aaron Lyle" } }));
  fireEvent.click(screen.getByText("Confirm"));
  await waitFor(() => expect(posts[1]?.url).toBe("/api/intents/i1/define/lens/cells/M1%3Abusiness_definition/confirm"));
  fireEvent.click(screen.getByText("Send back with a note"));
  expect(screen.getByRole("dialog")).toBeInTheDocument();
});

test("someone who is not the owner sees the cell but none of the three actions", async () => {
  mock(withCell({}, { may_act: [] }), ["participant"]);
  render(<LensStrip intentId="i1" />);
  await openCell("Business definition: Guessed");
  expect(screen.getByText("The monthly return.")).toBeInTheDocument();
  for (const w of ["Confirm", "Not mine", "Send back with a note"]) expect(screen.queryByText(w)).toBeNull();
});

test("a refusal from the server is shown in plain words", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") return json(403, { error: "not_allowed", message: "Only the person named as owner of this item can do that." });
    if (url === "/api/auth/me") return json(200, { display_name: "Harvey", company_id: "co-a", roles: ["owner"] });
    return json(200, withCell({}, { may_act: ["M1:business_definition"] }));
  }));
  render(<LensStrip intentId="i1" />);
  await openCell("Business definition: Guessed");
  fireEvent.click(screen.getByText("Confirm"));
  expect(await screen.findByText("Only the person named as owner of this item can do that.")).toBeInTheDocument();
});

test("a cell with nothing found reads Not found yet, never Guessed", async () => {
  mock(withCell({ outcome: "nothing", value: null }));
  render(<LensStrip intentId="i1" />);
  fireEvent.click(await screen.findByText("Show each measure"));
  expect(screen.getByText("Business definition: Not found yet")).toBeInTheDocument();
  expect(screen.queryByText("Business definition: Guessed")).toBeNull();
});

test("the strip total counts every measure, not the cells made so far", async () => {
  mock(withCell({}, { total: 108, drafted: 73, measures: 12 }));
  render(<LensStrip intentId="i1" />);
  expect(await screen.findByText("Lens has drafted 73 of 108 items for 12 measures.")).toBeInTheDocument();
});

test("the question card names the item, the role and the meanings, and a meaning answers it", async () => {
  const posts = mock(base({ total: 1, cells: {}, questions: { mine_open: 1, waiting: 0, open_total: 1 }, people: ["Aaron Lyle"],
    my_questions: [{ id: "q1", to: "harvey", about_cell: "M1:ambiguities", text: "Which meaning of Fund returns is right?", term: "Fund returns", state: "open", kind: "ambiguities",
      item: "Fund returns", why: "You are named as business owner of Fund returns.", meanings: [{ meaning: "net", where: "policy" }, { meaning: "gross", where: "interview" }] }] }));
  render(<LensStrip intentId="i1" />);
  fireEvent.click(await screen.findByText("Questions: 1 open for you, 0 waiting"));
  expect(screen.getByText("You are named as business owner of Fund returns.")).toBeInTheDocument();
  expect(screen.getByText("The documents say 2 things:")).toBeInTheDocument();
  fireEvent.click(screen.getAllByText("Use this meaning")[1]!);
  await waitFor(() => expect(posts[0]).toEqual({ url: "/api/intents/i1/define/lens/questions/q1/answer", body: { answer: "gross" } }));
  expect(screen.getByText("Not mine")).toBeInTheDocument();
});

test("the approver sees the escalation queue and can decide", async () => {
  const posts = mock(withCell({ state: "escalated", redraft: { value: "Net of fees.", note: "Say net" } },
    { may_decide: true, escalated: [{ cell_key: "M1:business_definition", with: "Grace Ward", notes: ["Say net", "Still wrong"] }] }), ["approver"]);
  render(<LensStrip intentId="i1" />);
  expect(await screen.findByText("Waiting for your decision")).toBeInTheDocument();
  expect(screen.getByText("Second note: Still wrong")).toBeInTheDocument();
  fireEvent.click(screen.getByText("Use the redraft"));
  await waitFor(() => expect(posts[0]).toEqual({ url: "/api/intents/i1/define/lens/cells/M1%3Abusiness_definition/decide", body: { choice: "redraft", wording: "" } }));
});

test("a run carried on after a restart says where it stopped", async () => {
  mock(base({ run: { state: "running", model_set_up: true, order, resumed_from: 56 }, total: 108, drafted: 56, cells: { "M1:mapping": cell("mapping", "guessed") } }));
  render(<LensStrip intentId="i1" />);
  expect(await screen.findByText("Lens stopped at 56 of 108; carrying on")).toBeInTheDocument();
});
