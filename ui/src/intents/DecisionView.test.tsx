import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../theme";
import DecisionStart, { rewriteOf } from "./start/DecisionStart";
import DecisionView, { markOf, ordered, withDefaults, type Intent, type Option } from "./views/DecisionView";

// Spec 43 screens A, B and D. fetch is stubbed with synthetic Ardmore data.

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const J = { account_id: "j", name: "Janet Shaw" }, D = { account_id: "d", name: "Daniel Kerr" }, K = { account_id: "k", name: "Katie Menon" };
const src = { kind: "intent", ref: "prb-1", label: "Problem: NAV report late", at: "2026-10-05T09:00:00Z" };
const opt = (id: string, extra: Partial<Option> = {}): Option => ({ id, name: `Option ${id}`, means: "m", for: [], against: [], needs: "Not known. Needs: a quote or an estimate.",
  origin: "north", by: "North", at: "2026-10-07T09:00:00Z", confirmed_by: null, sources: [src], notes: [], ...extra });
function rec(extra: Partial<Intent> = {}, outcome: Record<string, unknown> = {}): Intent {
  return { id: "dec-1", type: "decision", title: "Which valuation date?", purpose: "", state: "open", tier: "content", created_at: "2026-10-07T09:00:00Z",
    areas: ["Finance operations"], people: { organiser: J, decider: D, advisers: [K] }, time_box: { ends: "2099-10-09T09:00:00Z" }, links: { from: null, to: [] },
    outcome: { question: "Which valuation date?", options: [opt("a"), opt("b", { origin: "anonymous", by: "Anonymous", sources: [] })],
      recommendation: { option_id: "a", line: "North leans to Option a, because it has the most records behind it.", sources: [src], missing: [], drafted_at: "2026-10-07T09:00:00Z" },
      chosen: null, why: "", why_drafted: false, decided_by: null, decided_at: null, no_decision_reason: null, deferral: null, writes: [], considered_snapshot: [],
      affects: [], north: { drafted_at: "2026-10-07T09:00:00Z", records: 1, notes: 0, drafted: 1 }, ...outcome } as Intent["outcome"], ...extra };
}
function mock(who: string, record: Intent) {
  const posts: { url: string; body: Record<string, unknown> }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      const body = init.body ? JSON.parse(String(init.body)) : {};
      posts.push({ url, body });
      if (body.kind === "start") return json(200, { marks: { d: ["sponsor"] }, sponsor: D });
      return json(200, record);
    }
    if (url === "/api/auth/me") return json(200, { display_name: who, company_id: "ardmore", roles: [] });
    if (url === "/api/intents/people") return json(200, { people: [{ person_id: "d", name: "Daniel Kerr", role: "Chief Investment Officer", area: "Investments" }], areas: [] });
    if (url === "/api/intents/areas") return json(200, { areas: [{ id: "a1", name: "Finance operations" }] });
    if (url.startsWith("/api/intents/")) return json(200, record);
    return json(200, { nodes: [] });
  }));
  return posts;
}
const show = (el: ReactElement, path = "/centre/intent/dec-1") => render(
  <ThemeProvider><MemoryRouter initialEntries={[path]}><Routes><Route path="/centre/intent/:intentId" element={el} /><Route path="/centre/intent/new" element={el} /></Routes></MemoryRouter></ThemeProvider>);

afterEach(() => vi.unstubAllGlobals());

test("marks and order: guessed cards show their record count; a card with no record is shown last", () => {
  expect(markOf(opt("a"))).toBe("Guessed by North, from 1 record");
  expect(markOf(opt("x", { sources: [] }))).toBe("Guessed by North, nothing recorded behind it");
  expect(markOf(opt("y", { origin: "anonymous", by: "Anonymous" }))).toBe("Added by an adviser");
  expect(markOf(opt("f", { fallback: true }))).toContain("Drafted from simple word rules");
  expect(ordered([opt("bare", { sources: [] }), opt("z")]).map((o) => o.id)).toEqual(["z", "bare"]);
  expect(rewriteOf("Which custodian")).toBe("Which custodian?");
  expect(rewriteOf("Whether to move")).toBeNull();
});

test("the recommendation is always labelled as the agent's draft, with its sources, and only the decider sees Choose", async () => {
  mock("Katie Menon", rec());
  show(<DecisionView />);
  expect(await screen.findByText(/North leans to Option a/)).toBeInTheDocument();
  expect(screen.getAllByText("Agent's draft. Not a decision.").length).toBeGreaterThan(0);
  expect(screen.getByText(/Problem: NAV report late/)).toBeInTheDocument();
  expect(screen.queryByText(/^Choose Option/)).toBeNull();
  expect(screen.getByText("Waiting for Daniel")).toBeInTheDocument();
});

test("the decider records a decision with a reason through the sign modal", async () => {
  const posts = mock("Daniel Kerr", rec());
  show(<DecisionView />);
  fireEvent.click(await screen.findByText("Choose Option a"));
  const record = screen.getByText("Record my decision");
  expect(record).toBeDisabled();
  fireEvent.change(screen.getByPlaceholderText("Why this option?"), { target: { value: "Matches the audit cycle" } });
  fireEvent.click(record);
  await waitFor(() => expect(posts.some((p) => p.body.kind === "choose" && p.body.option_id === "a" && p.body.why === "Matches the audit cycle")).toBe(true));
});

test("the record view shows the decision strip and no write buttons", async () => {
  mock("Katie Menon", rec({ state: "closed" }, { chosen: "a", why: "Simplest", decided_by: "Daniel Kerr", decided_at: "2026-10-08T09:00:00Z", considered_snapshot: [opt("a"), opt("b")] }));
  show(<DecisionView />);
  expect(await screen.findByText(/Decided: Option a. By Daniel Kerr/)).toBeInTheDocument();
  expect(screen.queryByText("Add an option")).toBeNull();
  expect(screen.queryByText("Add a note")).toBeNull();
  expect(screen.getByText(/North's draft recommendation was Option a/)).toBeInTheDocument();
});

test("start questions: the sponsor is the default decider and Open this decision sends the five answers", async () => {
  const posts = mock("Janet Shaw", { ...rec({ state: "draft" }), title: "" } as Intent);
  show(<DecisionStart type="decision" draftId="dec-1" catalogue={{ title: "Decision", chooser_line: "", open_button: "Open this decision", start_questions: [] }} catalogueVersion={1} />,
    "/centre/intent/new");
  expect(await screen.findByText("Say what must be decided")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("What must be decided?"), { target: { value: "Which valuation date do we use?" } });
  expect(screen.getByText("Choose at least one area")).toBeInTheDocument();
  fireEvent.click(screen.getByText("Add area"));
  fireEvent.click(await screen.findByText("Finance operations"));
  fireEvent.click(screen.getByText("Open this decision"));
  await waitFor(() => expect(posts.some((p) => p.body.kind === "open")).toBe(true));
  const sent = posts.find((p) => p.body.kind === "open")!.body.answers as Record<string, unknown>;
  expect(sent.decider).toEqual(D);
  expect(sent.areas).toEqual(["Finance operations"]);
  expect(sent.question).toBe("Which valuation date do we use?");
});

test("start questions from a brainstorm: the chosen idea, its sponsor and its participants are pre-filled as a draft", async () => {
  const draft = { ...rec({ state: "draft", links: { from: "bra-9", to: [] } }), title: "" } as Intent;
  const posts = mock("Janet Shaw", draft);
  const base = vi.mocked(fetch).getMockImplementation()!;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => url === "/api/intents/bra-9"
    ? json(200, { type: "brainstorm", title: "Fund report", outcome: { chosen: { text: "Move the monthly report to one agreed set of measures" } },
      people: { sponsor: D, participants: [K, D] } })
    : base(url, init)));
  show(<DecisionStart type="decision" draftId="dec-1" catalogue={{ title: "Decision", chooser_line: "", open_button: "Open this decision", start_questions: [] }} catalogueVersion={1} />,
    "/centre/intent/new");
  expect(await screen.findByText("Pre-filled from the brainstorm. Change anything.")).toBeInTheDocument();
  expect(screen.getByLabelText("What must be decided?")).toHaveValue("Move the monthly report to one agreed set of measures");
  fireEvent.click(screen.getByText("Add area"));
  fireEvent.click(await screen.findByText("Finance operations"));
  fireEvent.click(screen.getByText("Open this decision"));
  await waitFor(() => expect(posts.some((p) => p.body.kind === "open")).toBe(true));
  const sent = posts.find((p) => p.body.kind === "open")!.body.answers as Record<string, unknown>;
  expect(sent.decider).toEqual(D);
  expect(sent.advisers).toEqual([K]);
});

describe("an older record", () => {
  it("reads missing lists as empty instead of painting blank", () => {
    const old = withDefaults({ id: "d", type: "decision", title: "t", purpose: "", state: "closed", areas: undefined as never, people: { organiser: null, decider: null } as never,
      time_box: { ends: "2026-10-01" }, outcome: { question: "", options: [], chosen: null, why: "" } as never });
    expect(old.outcome?.considered_snapshot).toEqual([]);
    expect(old.outcome?.writes).toEqual([]);
    expect(old.people.advisers).toEqual([]);
    expect(withDefaults({ ...old, outcome: { options: [{ id: "a" }] } as never }).outcome?.options[0]?.sources).toEqual([]);
  });
});

test("W2F7: older seeded options read with a name and an author, never 'undefined'; a nameless option is not a card", () => {
  const r = withDefaults(rec({}, { options: [
    { id: "o1", text: "Adopt the governed measures", drafted_by: "north", added_by: null },
    { id: "o2", text: "Use a credit line", drafted_by: null, added_by: "adviser" },
    { id: "o3", text: "", drafted_by: "north", added_by: null }] as unknown as Option[] }));
  const opts = ordered(r.outcome!.options);
  expect(opts.map((o) => o.name)).toEqual(["Use a credit line", "Adopt the governed measures"]);  // a North card with no record goes last
  expect(opts.map(markOf).join(" ")).not.toContain("undefined");
  expect(markOf(opts[0]!)).toBe("Added by an adviser");
});

test("W2F7: an adviser has a note box on the Notes view and Add an option; a saved note marks the adviser as replied", async () => {
  const after = rec({}, { options: [opt("a", { notes: [{ id: "n1", kind: "comment", text: "Fine", by: "Katie Menon", at: "2026-10-07T10:00:00Z", state: "open", decided_by: null, answer: null }] }), opt("b")] });
  const posts = mock("Katie Menon", rec());
  show(<DecisionView />, "/centre/intent/dec-1?view=notes");
  expect(await screen.findByText("Your note")).toBeInTheDocument();
  expect(screen.getAllByText("Add an option").length).toBeGreaterThan(0);
  expect(screen.getByText("Not replied yet")).toBeInTheDocument();
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") { posts.push({ url, body: JSON.parse(String(init.body)) }); return json(200, after); }
    return json(200, url === "/api/auth/me" ? { display_name: "Katie Menon", roles: [] } : after);
  }));
  const box = screen.getByLabelText("On which option?").closest(".ds-card")!;
  fireEvent.change(within(box as HTMLElement).getByPlaceholderText("Your view on this option"), { target: { value: "Fine" } });
  fireEvent.click(within(box as HTMLElement).getByText("Add a note"));
  await waitFor(() => expect(posts.some((p) => p.url === "/api/intents/dec-1/options/a/notes" && p.body.text === "Fine")).toBe(true));
  expect(await screen.findByText("Added 1 note")).toBeInTheDocument();
});

test("W2F7: with no options yet the Notes view says so and offers Add an option", async () => {
  mock("Katie Menon", rec({}, { options: [], recommendation: null }));
  show(<DecisionView />, "/centre/intent/dec-1?view=notes");
  expect(await screen.findByText("No options yet. Add an option, then a note on it.")).toBeInTheDocument();
});
