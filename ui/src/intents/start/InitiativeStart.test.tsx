import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { InitiativeStart, QUESTIONS, termsOf } from "./InitiativeStart";

// The Initiative start (spec 22). fetch is stubbed with synthetic Ardmore data.

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const cell = (value: unknown, mark = "stated", extra = {}) => ({ value, mark, by: "Janet Shaw", from: "", at: "2026-10-07T09:00:00Z", ...extra });
const later = (() => { const d = new Date(); d.setUTCDate(d.getUTCDate() + 7); return d.toISOString().slice(0, 10); })();
const ALL = {
  goal: cell({ line: "Cut the days to produce the quarterly client report", why: "The family council waits two weeks for it." }, "guessed"),
  people: cell({ sponsor: { account_id: "a1", name: "Daniel Kerr" }, participants: [{ account_id: "a2", name: "Aaron Lyle" }], affected: [], just_me: false, not_listed: [], affected_may_read: false }),
  build: cell("not_sure", "guessed"), definitions: cell("some", "stated", { terms: ["report"], found: [], counts: null }),
  areas: cell(["investments"]), deadline: cell(later),
};
type Call = { method: string; url: string; body: Record<string, unknown> };

function mock(answers: Record<string, unknown> = {}, more: Record<string, unknown> = {}) {
  const calls: Call[] = [];
  let rec = { id: "ini-1", version: 3, state: "draft", type: "initiative", title: "", start_answers: answers, stages: [], links: { from: null }, north_proposal: null };
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) : {};
    calls.push({ method, url, body });
    if (method === "PUT" && url === "/api/intents/ini-1/start") {
      rec = { ...rec, version: rec.version + 1, start_answers: { ...rec.start_answers, [body.key]: body.cell } };
      return json(200, rec);
    }
    if (method === "POST" && url === "/api/intents/ini-1/start/open") return json(200, { ...rec, state: "open" });
    if (method === "GET" && url in more) return json(200, more[url]);
    if (url === "/api/intents/ini-1") return json(200, rec);
    if (url === "/api/intents/people") return json(200, { people: [{ person_id: "a1", name: "Daniel Kerr", role: "Chief Investment Officer", area: "Investments" }] });
    if (url === "/api/intents/areas") return json(200, { areas: [{ id: "investments", name: "Investments" }], can_set_up: false });
    if (url === "/api/intents/ini-1/glossary-start") return json(200, { terms: [] });
    return json(200, {});
  }));
  return calls;
}
function Where() { const l = useLocation(); return <p data-testid="where">{l.pathname + l.search}</p>; }
const props = { type: "initiative", draftId: "ini-1", catalogue: { title: "Initiative", chooser_line: "", open_button: "", start_questions: [] }, catalogueVersion: 1 };
function view(step: string) {
  return render(
    <ThemeProvider><MemoryRouter initialEntries={[`/centre/intent/new?type=initiative&draft=ini-1&step=${step}`]}>
      <Routes>
        <Route path="/centre/intent/new" element={<><InitiativeStart {...props} /><Where /></>} />
        <Route path="/centre/intent/*" element={<Where />} />
      </Routes>
    </MemoryRouter></ThemeProvider>,
  );
}
afterEach(() => vi.unstubAllGlobals());

test("six questions in the canonical order, all required, with the stepper", async () => {
  expect(QUESTIONS.map((q) => q.key)).toEqual(["goal", "people", "build", "definitions", "areas", "deadline"]);
  expect(QUESTIONS.every((q) => q.required)).toBe(true);
  expect(QUESTIONS[3]!.lead).toBe("Do we already have a business glossary and technical definitions for this, or will we discover them along the way?");
  mock(); view("goal");
  expect(await screen.findByText("What are you trying to achieve?")).toBeInTheDocument();
  for (const l of ["1 Goal", "2 People", "6 Deadline", "Review"]) expect(screen.getByRole("button", { name: l })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "2 People" })).toBeDisabled(); // later steps are not clickable
  expect(screen.getByText("Nothing answered yet.")).toBeInTheDocument();
});

test("a required answer gates Next; the read-back saves the answer stated", async () => {
  const calls = mock(); view("goal");
  const next = await screen.findByRole("button", { name: "Next" });
  expect(next).toBeDisabled();
  expect(screen.getByText("Say the goal in one line.")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("In one line"), { target: { value: "Cut the days to produce the client report" } });
  expect(screen.getByText("A few words on why will help the people you invite.")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText(/Why does it matter/), { target: { value: "The family council waits two weeks for it." } });
  fireEvent.click(await screen.findByRole("button", { name: "That is right" }));
  await waitFor(() => expect(next).toBeEnabled());
  const put = calls.find((c) => c.method === "PUT")!;
  expect(put.url).toBe("/api/intents/ini-1/start");
  expect(put.body).toMatchObject({ version: 3, key: "goal", cell: { mark: "stated", value: { line: "Cut the days to produce the client report" } } });
});

test("arriving from the tile without a step, the answer saves and Next stays on question 1", async () => {
  mock(); view("");
  await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("step=goal"));
  fireEvent.change(screen.getByLabelText("In one line"), { target: { value: "Cut the days to produce the client report" } });
  fireEvent.change(screen.getByLabelText(/Why does it matter/), { target: { value: "The family council waits two weeks for it." } });
  fireEvent.click(await screen.findByRole("button", { name: "That is right" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Next" })).toBeEnabled());
  expect(screen.getByText("What are you trying to achieve?")).toBeInTheDocument();
});

test("the review card shows each answer with its mark", async () => {
  mock(ALL); view("review");
  expect(await screen.findByText("Here is what I understood. Check it, change anything that is wrong, then open it.")).toBeInTheDocument();
  expect(screen.getAllByText("Guessed by North").length).toBeGreaterThanOrEqual(2); // goal and build kept from North, and the summary
  expect(screen.getAllByText("Stated by you").length).toBeGreaterThanOrEqual(4);
  expect(screen.getAllByRole("button", { name: "Change" })).toHaveLength(6);
  expect(screen.getByText(/the wall opens for \d+ working days, to 2 people/)).toBeInTheDocument();
});

test("open sends the title and summary to the start open route and lands on the intent", async () => {
  const calls = mock(ALL); view("review");
  fireEvent.change(await screen.findByLabelText("Title"), { target: { value: "Faster client report" } });
  fireEvent.click(screen.getByRole("button", { name: "That is right, open this intent" }));
  await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("/centre/intent/ini-1"));
  const open = calls.find((c) => c.url === "/api/intents/ini-1/start/open")!;
  expect(open.body).toMatchObject({ version: 3, title: "Faster client report", summary: { mark: "guessed" } });
  expect(String((open.body.summary as { text: string }).text)).toContain("Cut the days");
});

test("save and leave keeps the draft: nothing is cancelled", async () => {
  const calls = mock({ goal: ALL.goal }); view("people");
  fireEvent.click(await screen.findByRole("button", { name: "Save and leave" }));
  await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("/centre/intent"));
  expect(calls.some((c) => c.url.includes("/cancel"))).toBe(false);
  expect(calls.some((c) => c.method === "DELETE")).toBe(false);
});

test("filler words from the goal and why are not offered as terms", () => {
  const t = termsOf("Show unfunded commitments to the family council within three days of quarter end. The council waits two weeks for it.");
  expect(t).toEqual(expect.arrayContaining(["unfunded", "commitments", "council"]));
  for (const w of ["show", "waits", "within"]) expect(t).not.toContain(w);
});

const M2 = "/api/modules/m2_baseline/baselines";
const row = (o: Record<string, string>) => Object.fromEntries(Object.entries(o).map(([k, v]) => [k, { value: v }]));
const BASELINE = {
  [M2]: { baselines: [{ id: "b1", state: "signed", kpi_count: 1 }] },
  [`${M2}/b1/catalogue`]: {
    signed: true, kpis: [row({ "KPI ID": "K02", "KPI name": "Unfunded commitments", "Business owner": "Daniel Kerr", "Data owner": "Harvey Rowley" })],
    tables: [row({ "Item ID": "T01", "Name of table, file or document type": "Commitments by fund" })], fields: [],
    technical: { kpis: { K02: { calculation: "Sum of called less funded", confirmed: "Harvey Rowley, 2026-04-24" } } },
  },
};

test("question 4 lists real technical definitions and catalogue entries with their owners, and counts them", async () => {
  mock({ goal: ALL.goal, people: ALL.people, build: ALL.build }, BASELINE);
  view("definitions");
  fireEvent.change(await screen.findByPlaceholderText("Add a term"), { target: { value: "commitments" } });
  fireEvent.click(screen.getByRole("button", { name: "Add a term" }));
  expect(await screen.findByText(/commitments: Unfunded commitments, Signed\. Owner: Harvey Rowley/)).toBeInTheDocument();
  expect(screen.getByText(/commitments: Commitments by fund, Signed/)).toBeInTheDocument();
  expect(screen.getByText(/1 has a technical definition\. 1 is in the catalogue\./)).toBeInTheDocument();
  expect(screen.queryByText(/not built yet/)).toBeNull();
});

test("question 4 says what is missing when there is no baseline or it cannot be read", async () => {
  mock({ goal: ALL.goal, people: ALL.people, build: ALL.build }, { [M2]: { baselines: [] } });
  view("definitions");
  expect(await screen.findAllByText(/No baseline exists yet/)).toHaveLength(2);
});

test("the sponsor is pre-filled as a guess from the company list's sponsor flag", async () => {
  mock({ goal: ALL.goal }, { "/api/intents/people": { people: [{ person_id: "a1", name: "Daniel Kerr", role: "Chief Investment Officer", area: "Investments", is_sponsor: true },
    { person_id: "a2", name: "Aaron Lyle", role: null, area: "Finance", is_sponsor: false }] } });
  view("people");
  expect(await screen.findByText(/Sponsor: Daniel Kerr\. Named as the sponsor in the company profile\./)).toBeInTheDocument();
});

test("no sponsor flag, no sponsor guess", async () => {
  mock({ goal: ALL.goal }); view("people");
  await screen.findByRole("button", { name: "Next" });
  expect(screen.queryByText(/Named as the sponsor in the company profile/)).not.toBeInTheDocument();
});
