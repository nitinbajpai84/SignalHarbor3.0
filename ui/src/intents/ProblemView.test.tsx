// slow under a full parallel run; the 5 s default timed out a different test each time
vi.setConfig({ testTimeout: 30000 });
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { configure } from "@testing-library/react";
configure({ asyncUtilTimeout: 5000 });
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

import { ThemeProvider } from "../theme";
import ProblemStart from "./start/ProblemStart";
import ProblemView from "./views/ProblemView";

// The Problem's start questions (spec 41) and its stage view (specs 41 and 42). fetch is stubbed with synthetic data.

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
function Where() { const l = useLocation(); return <p data-testid="where">{l.pathname + l.search}</p>; }

const OPTIONS = {
  people: [{ id: "harvey", name: "Harvey Rowley", team: "Fund Operations", can_own: true }, { id: "aaron", name: "Aaron Lyle", team: "Risk", can_own: true }, { id: "grace", name: "Grace Ward", team: "Office", can_own: true }],
  areas: ["Fund Operations", "Risk"], catalogue: [{ id: "measure:K02", name: "Evidence coverage", group: "Measures" }], currency: "SGD",
  chips: [{ source: "source_owner", name: "Harvey Rowley", label: "Source owner, from the pipeline contract" }],
  prefill: { what: "Custodian daily file: the file has not arrived", about: "measure:K02", owner_source: "source_owner", alert: "custodian_daily_file:missing", origin: "Started from: Custodian daily file, the file has not arrived" },
};
const CAT = { title: "Problem", chooser_line: "x", open_button: "Open this problem", time_box_days: 5, start_questions: [] };

function startView(url = "/centre/intent/new?type=problem&draft=prb-1&alert=custodian_daily_file:missing") {
  const posts: { url: string; body: Record<string, unknown> }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (u: string, init?: RequestInit) => {
    if (init?.method === "POST") { posts.push({ url: u, body: JSON.parse(String(init.body)) }); return json(200, { id: "prb-1" }); }
    if (u.startsWith("/api/intents/problem/start")) return json(200, OPTIONS);
    if (u === "/api/intents/prb-1/problem") return json(200, { id: "prb-1", state: "draft", start_answers: {} });
    return json(200, {});
  }));
  render(<ThemeProvider><MemoryRouter initialEntries={[url]}><Routes>
    <Route path="/centre/intent/new" element={<><ProblemStart type="problem" draftId="prb-1" catalogue={CAT} catalogueVersion={1} /><Where /></>} />
    <Route path="/centre/intent/:id" element={<Where />} /><Route path="/centre/intent" element={<Where />} />
  </Routes></MemoryRouter></ThemeProvider>);
  return posts;
}

const base = {
  id: "prb-1", state: "open", short_ref: "P-1", title: "Monthly fee file arrives late", purpose: "x", stage: "Describe", stage_key: "describe", triage: "waiting", tz: "UTC",
  clock: { starts: "2026-10-07T09:00:00Z", ends: "2026-10-14T09:00:00Z", working_days_total: 5, working_days_left: 5, day_of: 1, state: "on_time" },
  created_at: "2026-10-07T09:00:00Z", reporter: "Katie Menon", owner: null, organiser: "Katie Menon", tier: "content", people_count: 4, waiting_for: "Harvey Rowley",
  affected_may_read: false, areas: ["Fund Operations"], extended: null, links: {},
  me: { reporter: false, owner: false, proposed: true, organiser: false, admin: false, affected: false },
  as_reported: { what: "Monthly fee file arrives late", saw: "It came on the 5th.", bites: { kind: "slowed", count: 3, amount: null, unit: null }, about: { kind: "measure", id: "measure:K02", name: "Evidence coverage" },
                 areas: ["Fund Operations"], affected: ["Aaron Lyle"], reported_at: "2026-10-07T09:00:00Z" },
  passes: [], escalated: false,
  triage_note: { drafted_at: "2026-10-07T09:00:00Z", drafted_plainly: true, similar: [], related: [], terms: [], ops_unreadable: false, can_redraw: false, alerts: [], range_breaks: [] },
  proposed_owner: { name: "Harvey Rowley", source: "source_owner", label: "Source owner, from the pipeline contract", picked_by_reporter: false },
  can: { accept: true, pass: true, assign: false, redraw: true, extend: false, change_owner: false },
};

function problemView(rec: unknown) {
  const posts: { url: string; body: Record<string, unknown> }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (u: string, init?: RequestInit) => {
    if (init?.method === "POST") { posts.push({ url: u, body: JSON.parse(String(init.body ?? "{}")) }); return json(200, rec); }
    if (u === "/api/intents/prb-1/problem") return json(200, rec);
    if (u.startsWith("/api/intents/problem/start")) return json(200, OPTIONS);
    return json(200, {});
  }));
  render(<ThemeProvider><MemoryRouter initialEntries={["/centre/intent/prb-1"]}><Routes><Route path="/centre/intent/:intentId" element={<ProblemView />} /></Routes></MemoryRouter></ThemeProvider>);
  return posts;
}

afterEach(() => vi.unstubAllGlobals());

test("an Ops alert fills the first two questions and the origin banner can be removed", async () => {
  startView();
  expect(await screen.findByDisplayValue("Custodian daily file: the file has not arrived")).toBeInTheDocument();
  expect(screen.getByText(/Started from: Custodian daily file/)).toBeInTheDocument();
  fireEvent.click(screen.getByText("Remove link"));
  expect(screen.queryByText(/Started from: Custodian daily file/)).not.toBeInTheDocument();
});

test("five questions with a read-back after each, then the review and the open press", async () => {
  const posts = startView();
  fireEvent.change(await screen.findByLabelText("What you saw"), { target: { value: "It came on the 5th." } });
  fireEvent.click(screen.getByText("Next"));
  expect(await screen.findByText(/So: Custodian daily file/)).toBeInTheDocument();
  fireEvent.click(screen.getByText("Yes"));
  expect(await screen.findByText("Which process or measure is it about?", { exact: false })).toBeInTheDocument();
  expect((await screen.findAllByText("Evidence coverage")).length).toBeGreaterThan(0); // picked from the alert's measure
  fireEvent.click(screen.getByText("Next")); fireEvent.click(await screen.findByText("Yes"));
  fireEvent.click(await screen.findByLabelText("Stopped us"));
  fireEvent.click(screen.getByText("Next")); fireEvent.click(await screen.findByText("Yes"));
  fireEvent.click(await screen.findByText(/Source owner: Harvey Rowley/));
  expect(screen.getByText("Suggested from the pipeline contract")).toBeInTheDocument();
  fireEvent.click(screen.getByText("Next")); fireEvent.click(await screen.findByText("Yes"));
  expect(await screen.findByText("Which areas are affected?", { exact: false })).toBeInTheDocument();
  fireEvent.click(screen.getAllByText("Fund Operations")[0]!);
  expect(screen.getByText("Name at least one person who feels it.")).toBeInTheDocument();
  fireEvent.click(screen.getByText("Aaron Lyle"));
  fireEvent.click(screen.getByText("Next")); fireEvent.click(await screen.findByText("Yes"));
  expect(await screen.findByText("Ends", { exact: false })).toBeInTheDocument();
  fireEvent.click(screen.getByText("Open this problem"));
  await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("/centre/intent/prb-1"));
  const open = posts.find((p) => p.body.open === true)!;
  expect(open.url).toBe("/api/intents/prb-1/problem/start");
  expect(open.body).toMatchObject({ what: "Custodian daily file: the file has not arrived", bites: { kind: "stopped" }, areas: ["Fund Operations"], affected: ["Aaron Lyle"], alert: "custodian_daily_file:missing",
                                    owner: { source: "source_owner", name: "Harvey Rowley" } });
});

test("Next stays off until a how-hard choice is made", async () => {
  startView("/centre/intent/new?type=problem&draft=prb-1");
  fireEvent.change(await screen.findByLabelText("One line"), { target: { value: "Fee file late" } });
  fireEvent.change(screen.getByLabelText("What you saw"), { target: { value: "5th" } });
  fireEvent.click(screen.getByText("Next")); fireEvent.click(await screen.findByText("Yes"));
  fireEvent.click(await screen.findByText("Remove")); // the mock still prefills the measure
  fireEvent.click(await screen.findByText("Not sure"));
  fireEvent.click(await screen.findByText("Yes"));
  expect(await screen.findByLabelText("Slowed us")).toBeInTheDocument();
  expect(screen.getByText("Next")).toBeDisabled();
  fireEvent.click(screen.getByLabelText("Cost money"));
  expect(screen.getByText("Next")).toBeEnabled();
  expect(screen.getByLabelText("Amount in SGD")).toBeInTheDocument();
});

test("the proposed owner reads the plain note, accepts after one confirmation, and the pass needs a reason", async () => {
  const posts = problemView(base);
  expect(await screen.findByText("North could not write the note. These are the plain matches.")).toBeInTheDocument();
  expect(screen.getByText("No similar problem on record.")).toBeInTheDocument();
  expect(screen.getByText("Nothing else open on this.")).toBeInTheDocument();
  expect(screen.getByText("No alerts or range breaks on record for this.")).toBeInTheDocument();
  expect(screen.getByText("Not passed.")).toBeInTheDocument();
  fireEvent.click(screen.getByText("Pass it on"));
  expect(screen.getByText("Name who should own this and say why.")).toBeInTheDocument();
  expect(screen.getByText("Send")).toBeDisabled();
  fireEvent.click(screen.getByText("Cancel"));
  fireEvent.click(screen.getByText("Accept"));
  expect(screen.getByText("You will own this problem. It ends 14 Oct.")).toBeInTheDocument();
  fireEvent.click(screen.getByText("Yes, I own it"));
  await waitFor(() => expect(posts[0]!.url).toBe("/api/intents/prb-1/triage/accept"));
});

test("a person who may only see that it exists gets the header and a plain line", async () => {
  problemView({ ...base, tier: "card", as_reported: undefined, triage_note: undefined, proposed_owner: undefined, passes: undefined, me: { ...base.me, proposed: false, affected: true }, can: { ...base.can, accept: false, pass: false, redraw: false } });
  expect(await screen.findByText("Monthly fee file arrives late")).toBeInTheDocument();
  expect(screen.getByText(/You can see that this problem exists/)).toBeInTheDocument();
  expect(screen.queryByText("Accept")).not.toBeInTheDocument();
});

test("the owner confirms the cause, and the fix stays locked until then", async () => {
  const working = { ...base, triage: "accepted", owner: "Harvey Rowley", stage: "Find the cause", stage_key: "find_cause", waiting_for: null, me: { ...base.me, proposed: false, owner: true },
    can: { ...base.can, accept: false, pass: false, redraw: false, extend: true }, triage_note: undefined, root_cause: null, fix: null, affected: [{ name: "Aaron Lyle", mine: false, state: "waiting", at: null, comment: null }],
    tally: { fixed: 0, still: 0, affected: 1, no_answer: 1 }, notes: [], what_we_know: null, node: { id: "measure:K02", name: "Evidence coverage", found: true }, north_banner: null,
    can_resolve: { draft_cause: false, confirm_cause: true, cause_unknown: true, save_fix: false, note: true, tap: false, close: false }, close_checks: null };
  const posts = problemView(working);
  expect(await screen.findByText("No cause yet. North drafts one when the owner asks.")).toBeInTheDocument();
  expect(screen.getByText("Nothing is known yet. Add the first note.")).toBeInTheDocument();
  expect(screen.getByText("Confirm the cause first.")).toBeInTheDocument();
  expect(screen.getByText("Add a note first")).toBeInTheDocument();
  expect(screen.getByText("Draft the cause")).toBeDisabled();
  fireEvent.change(screen.getByLabelText("The cause"), { target: { value: "The custodian moved its run." } });
  fireEvent.click(screen.getByText("Confirm this cause"));
  await waitFor(() => expect(posts[0]).toMatchObject({ url: "/api/intents/prb-1/problem/cause", body: { action: "confirm", text: "The custodian moved its run." } }));
});

test("an affected person taps their own row", async () => {
  const done = { ...base, triage: "accepted", owner: "Harvey Rowley", stage: "Confirm", stage_key: "confirm", tier: "card", as_reported: undefined, triage_note: undefined, proposed_owner: undefined,
    me: { ...base.me, proposed: false, affected: true }, can: { ...base.can, accept: false, pass: false, redraw: false }, fix_line: "Harvey Rowley did: Moved the pull, on 2026-10-07",
    affected: [{ name: "Aaron Lyle", mine: true, state: "waiting", at: null, comment: null }], fix: undefined, can_resolve: { draft_cause: false, confirm_cause: false, cause_unknown: false, save_fix: false, note: false, tap: true, close: false } };
  const posts = problemView(done);
  expect(await screen.findByText("Harvey Rowley did: Moved the pull, on 2026-10-07")).toBeInTheDocument();
  fireEvent.click(screen.getByText("Still happening for me"));
  fireEvent.change(screen.getByLabelText("Say in one sentence what is still happening"), { target: { value: "Late again on the 9th." } });
  fireEvent.click(screen.getByText("Send"));
  await waitFor(() => expect(posts[0]).toMatchObject({ url: "/api/intents/prb-1/problem/confirm-tap", body: { state: "still", comment: "Late again on the 9th." } }));
});

test("bigger than a fix asks what is bigger, then turns the problem into an Initiative", async () => {
  const working = { ...base, triage: "accepted", owner: "Harvey Rowley", stage: "Find the cause", stage_key: "find_cause", waiting_for: null, me: { ...base.me, proposed: false, owner: true },
    can: { ...base.can, accept: false, pass: false, redraw: false }, triage_note: undefined, root_cause: null, fix: null, affected: [], notes: [], what_we_know: null, node: null, north_banner: null,
    can_resolve: { draft_cause: false, confirm_cause: true, cause_unknown: false, save_fix: false, note: true, tap: false, close: false }, close_checks: null };
  const posts = problemView(working);
  fireEvent.click(await screen.findByText("This is bigger than a fix"));
  expect(screen.getByText("Turn into an Initiative")).toBeDisabled();
  fireEvent.change(screen.getByLabelText("What is bigger about it?"), { target: { value: "Three feeds and two teams." } });
  fireEvent.click(screen.getByText("Turn into an Initiative"));
  await waitFor(() => expect(posts[0]).toMatchObject({ url: "/api/intents/prb-1/problem/to-initiative", body: { reason: "Three feeds and two teams." } }));
});

test("an enhancement written in the first answer is steered to an Initiative with one click that carries the words", async () => {
  const posts: { url: string; body: Record<string, unknown> }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (u: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      posts.push({ url: u, body: JSON.parse(String(init.body ?? "{}")) });
      return json(200, u === "/api/intents/classify" ? { type: "initiative", reason: "x", confidence: "Likely", title: "t" } : { id: "ini-9", version: 1 });
    }
    if (u.startsWith("/api/intents/problem/start")) return json(200, { ...OPTIONS, prefill: {} });
    if (u === "/api/intents/prb-1/problem") return json(200, { id: "prb-1", state: "draft", start_answers: {} });
    if (u === "/api/intents/prb-1") return json(200, { version: 3 });
    return json(200, {});
  }));
  render(<ThemeProvider><MemoryRouter initialEntries={["/centre/intent/new?type=problem&draft=prb-1"]}><Routes>
    <Route path="/centre/intent/new" element={<><ProblemStart type="problem" draftId="prb-1" catalogue={CAT} catalogueVersion={1} /><Where /></>} />
  </Routes></MemoryRouter></ThemeProvider>);
  fireEvent.change(await screen.findByLabelText("One line"), { target: { value: "We want a new column on the cash match report" } });
  fireEvent.change(screen.getByLabelText("What you saw"), { target: { value: "No fees column, want one added." } });
  fireEvent.click(screen.getByText("Next"));
  fireEvent.click(await screen.findByText("Switch to an Initiative"));
  await waitFor(() => expect(screen.getByTestId("where").textContent).toBe("/centre/intent/new?type=initiative&draft=ini-9"));
  const made = posts.find((p) => p.url === "/api/intents")!.body as { type: string; start_answers: { goal: { value: { line: string } } } };
  expect(made.type).toBe("initiative");
  expect(made.start_answers.goal.value.line).toBe("We want a new column on the cash match report");
  expect(posts.some((p) => p.url === "/api/intents/prb-1/cancel")).toBe(true);
});

test("a closed Problem shows when it closed, no stage chip and no headcount that disagrees with the People panel", async () => {
  problemView({ ...base, state: "closed", triage: "accepted", stage: "Confirm", closed_at: "2026-10-09T08:00:00Z", me: { ...base.me, proposed: false, reporter: true },
    can: { ...base.can, accept: false, pass: false, redraw: false }, can_resolve: {}, affected: [] });
  expect(await screen.findByText("Closed on 9 Oct")).toBeInTheDocument();
  expect(screen.queryByText("Confirm")).not.toBeInTheDocument();
  expect(screen.queryByText(/hours left|Not started|^d+ people named/)).not.toBeInTheDocument();
});
