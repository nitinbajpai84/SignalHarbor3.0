import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import { routes } from "./routes";
import changes from "./fixtures/changes.json";
import followup from "./fixtures/followup.json";
import inbox from "./fixtures/inbox.json";
import profile from "./fixtures/profile.json";

// The fixtures are real responses of sh_platform/v1/k5_managers.py (a Fund set with one late, one amended and one late-received statement).
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

function mock(sent: string[], over: Record<string, () => Response> = {}) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Mei", company_id: "evergreen", roles: ["analyst"] });
    if (init?.method && init.method !== "GET") sent.push(`${init.method} ${url} ${String(init.body ?? "")}`);
    for (const [k, v] of Object.entries(over)) if (url.startsWith(k)) return v();
    if (url === "/api/v1/managers/inbox") return json(200, inbox);
    if (url === "/api/v1/managers/alder-capital/followup") return json(200, followup);
    if (url === "/api/v1/managers/alder-capital") return json(200, profile);
    if (url.startsWith("/api/v1/managers/alder-capital/changes")) return json(200, changes);
    if (url.startsWith("/api/v1/managers/alder-capital/notes")) return json(200, { id: "n", kind: "note", text: "x" });
    if (url.startsWith("/api/v1/pulse2/items")) return json(200, { role: "cio", roles: ["cio"], items: [] });
    return json(404, { error: "not_found", message: "Not found." });
  }));
}
function open(at: string) {
  render(<MemoryRouter initialEntries={[at]}><ThemeProvider><SessionProvider><Routes>
    {routes.map((r) => <Route key={r.path} path={`/centre/${r.path}`} element={r.element} />)}</Routes></SessionProvider></ThemeProvider></MemoryRouter>);
}

it("the Managers tab shows expected, received, late and revised per fund, in words", async () => {
  mock([]);
  open("/centre/action/managers");
  const alder = (await screen.findByRole("heading", { name: "Alder Capital" })).closest("li") as HTMLElement;
  expect(within(alder).getByText("3 expected · 2 received · 2 late · 1 revised")).toBeInTheDocument();
  expect(within(alder).getByText("6 business days late")).toBeInTheDocument();
  expect(within(alder).getByText("Received 2 business days late")).toBeInTheDocument();
  expect(within(alder).getByText("Revised once")).toBeInTheDocument();
  expect(within(alder).getByText(/Last value USD 5,000,000 on 31 Aug 2026 \(official\)/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Back to today" })).toHaveAttribute("href", "/centre/action");
  expect(screen.getByRole("link", { name: "Alder Capital" })).toHaveAttribute("href", "/centre/consume/managers/alder-capital");
});

it("Draft a follow-up shows a plain-text draft that is marked not sent, and posts nothing but the request for it", async () => {
  const sent: string[] = [];
  mock(sent);
  open("/centre/action/managers");
  const alder = (await screen.findByRole("heading", { name: "Alder Capital" })).closest("li") as HTMLElement;
  await userEvent.click(within(alder).getByRole("button", { name: "Draft a follow-up" }));
  const box = (await screen.findByLabelText(/Draft email \(not sent\)/)) as HTMLTextAreaElement;
  expect(box.value).toContain("Alder Credit Fund II: due 14 Oct 2026, 6 days overdue");
  expect(screen.getByText("This email has not been sent. Copy it into your own email to send it.")).toBeInTheDocument();
  expect(sent).toEqual(["POST /api/v1/managers/alder-capital/followup {}"]);
});

it("says when no signed rule exists, and when nothing is late the follow-up button is hidden", async () => {
  const quiet = { ...inbox, due_rule_signed: false, rule_note: "No signed rule says when statements are due, so lateness cannot be judged yet.",
    managers: inbox.managers.map((m) => ({ ...m, counts: { ...m.counts, late: 0 } })) };
  mock([], { "/api/v1/managers/inbox": () => json(200, quiet) });
  open("/centre/action/managers");
  expect(await screen.findByText(/No signed rule says when statements are due/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Draft a follow-up" })).toBeNull();
  expect(screen.getAllByText("Nothing is late.").length).toBeGreaterThan(0);
});

it("an empty company and a refused request each say so in words", async () => {
  mock([], { "/api/v1/managers/inbox": () => json(200, { as_of: "2026-10-20", due_rule_signed: true, rule_note: null, managers: [] }) });
  open("/centre/action/managers");
  expect(await screen.findByText(/No managers are set up yet/)).toBeInTheDocument();
  vi.unstubAllGlobals();
  mock([], { "/api/v1/managers/inbox": () => json(403, { detail: { error: "not_allowed", message: "You do not have access to this." } }) });
  open("/centre/action/managers");
  expect((await screen.findAllByRole("alert"))[0]).toHaveTextContent(/access|did not go through/);
});

it("the manager page shows funds, statements with revisions, notes, questions and documents", async () => {
  mock([]);
  open("/centre/consume/managers/alder-capital");
  expect(await screen.findByRole("heading", { name: "Alder Capital" })).toBeInTheDocument();
  expect(screen.getByText("No commitments are recorded for this manager's funds.")).toBeInTheDocument();
  const st = screen.getByRole("region", { name: "Statements" });
  expect(within(st).getByText(/received 12 Oct 2026, final, replaces an earlier statement/)).toBeInTheDocument();
  expect(within(st).getByText(/received 9 Oct 2026, estimate, replaced by a later one/)).toBeInTheDocument();
  expect(screen.getByText(/Quarterly catch-up/)).toBeInTheDocument();
  expect(screen.getByText("Why was the Growth NAV amended?")).toBeInTheDocument();
  expect(screen.getByText(/Alder Capital newsletter.txt/)).toBeInTheDocument();
  expect(screen.getByText("The last meeting on record was on 10 Oct 2026.")).toBeInTheDocument();
});

it("What changed shows dated lines each with a source chip, document passages, and the no-verdict line", async () => {
  mock([]);
  open("/centre/consume/managers/alder-capital");
  await userEvent.click(await screen.findByRole("button", { name: "Show what changed" }));
  expect(await screen.findByText(/dated items, newest first/)).toBeInTheDocument();
  const st = screen.getByRole("link", { name: "Alder Income Fund III" });
  expect(st).toHaveAttribute("href", expect.stringContaining("/centre/action/evidence/"));
  expect(screen.getByText(/our head of credit has left the firm/)).toBeInTheDocument();
  expect(screen.getByText("Alder Capital newsletter.txt, lines 1 to 2")).toBeInTheDocument();
  expect(screen.getByText(/does not say whether the manager is doing well or badly/)).toBeInTheDocument();
});

it("saving a note, a meeting and a question posts each kind; a refused manager says so", async () => {
  const sent: string[] = [];
  mock(sent);
  open("/centre/consume/managers/alder-capital");
  await userEvent.type(await screen.findByLabelText("Add a note"), "Fees agreed");
  await userEvent.click(screen.getByRole("button", { name: "Save the note" }));
  await userEvent.selectOptions(screen.getByLabelText("What kind"), "question");
  await userEvent.type(screen.getByLabelText("Add a note"), "Who is the new head of credit?");
  await userEvent.click(screen.getByRole("button", { name: "Add the question" }));
  await waitFor(() => expect(sent.length).toBe(2));
  expect(sent[0]).toBe('POST /api/v1/managers/alder-capital/notes {"text":"Fees agreed","kind":"note"}');
  expect(sent[1]).toContain('"kind":"question"');
});

it("a manager the person cannot see shows the refusal in words", async () => {
  mock([], { "/api/v1/managers/alder-capital": () => json(404, { error: "not_found", message: "We could not find that manager, or you do not have access to its funds." }) });
  open("/centre/consume/managers/alder-capital");
  expect(await screen.findByRole("alert")).toHaveTextContent("We could not find that manager, or you do not have access to its funds.");
});

// ---- cycle 1 fixes (TRIAGE-cycle-1 P5) ----
it("a3.11/a7.5/j-uc3a.0: the header always says late, counts a missing earlier statement, and the fund line flags it first", async () => {
  const missing = { ...inbox, managers: inbox.managers.map((m, k) => k ? m : {
    ...m, counts: { expected: 2, received: 0, late: 0, missing_earlier: 1, revised: 0 },
    funds: m.funds.map((f, j) => j ? f : { ...f, state: "not_due", state_word: "Not due yet", days_late: null,
      earlier_missing: [{ period_end: "2026-06-30", due: "2026-07-14", days_late: 63 }] }) }) };
  mock([], { "/api/v1/managers/inbox": () => json(200, missing) });
  open("/centre/action/managers");
  const alder = (await screen.findByRole("heading", { name: "Alder Capital" })).closest("li") as HTMLElement;
  expect(within(alder).getByText("2 expected · 0 received · 0 late this month · 1 missing from earlier months")).toBeInTheDocument();
  expect(within(alder).getByText("Earlier statement missing")).toBeInTheDocument();
  expect(within(alder).getByText(/the statement for 30 Jun 2026, due 14 Jul 2026, 63 business days late/)).toBeInTheDocument();
});

it("a3.10: a role the server refuses a draft is not offered the button", async () => {
  mock([], { "/api/v1/managers/inbox": () => json(200, { ...inbox, can_draft: false }) });
  open("/centre/action/managers");
  await screen.findByRole("heading", { name: "Alder Capital" });
  expect(screen.queryByRole("button", { name: "Draft a follow-up" })).toBeNull();
});

it("a3.15: the Managers tab sits inside the page gutters", async () => {
  mock([]);
  open("/centre/action/managers");
  await screen.findByRole("heading", { name: "Alder Capital" });
  expect(screen.getByRole("region", { name: "Managers" })).toHaveClass("ds-frame");
});

it("j-uc3a.2/a7.8: a late first statement says its business days late, fund values answer 'Where is this from?', a reader gets no note form", async () => {
  const late = { ...profile, can_write: false, timeline: profile.timeline.map((t, k) => (k ? t : { ...t, days_late: 5 })) };
  mock([], { "/api/v1/managers/alder-capital": () => json(200, late) });
  open("/centre/consume/managers/alder-capital");
  const st = await screen.findByRole("region", { name: "Statements" });
  expect(within(st).getByText(/, 5 business days late/)).toBeInTheDocument();
  expect(within(screen.getByRole("region", { name: "Funds" })).getAllByRole("button", { name: "Where is this from?" })).toHaveLength(3);
  expect(screen.queryByLabelText("Add a note")).toBeNull();
});

// ---- cycle 2 fixes (TRIAGE-cycle-2 P2) ----
it("AUC3-04: a date judges a past month; the inbox and the draft are asked for that day", async () => {
  const sent: string[] = [];
  const asked: string[] = [];
  mock(sent, { "/api/v1/managers/inbox?as_of=": () => { asked.push("as_of"); return json(200, { ...inbox, as_of: "2026-09-10" }); } });
  open("/centre/action/managers");
  await screen.findByRole("heading", { name: "Alder Capital" });
  await userEvent.type(screen.getByLabelText("Judge as of"), "2026-09-10");
  await waitFor(() => expect(asked.length).toBeGreaterThan(0));
  expect(await screen.findByText(/Judged on 10 Sep 2026/)).toBeInTheDocument();
  await userEvent.click(within((await screen.findByRole("heading", { name: "Alder Capital" })).closest("li") as HTMLElement).getByRole("button", { name: "Draft a follow-up" }));
  await waitFor(() => expect(sent.some((s) => s.includes('"as_of":"2026-09-10"'))).toBe(true));
});

it("AUC3-05/C2-UC7-02: a revised statement shows old and new figures; the commitments table scrolls in its own box", async () => {
  const rev = { from: "8420000", to: "8275000", change: "-145000", currency: "USD" };
  const withRev = { ...profile, timeline: profile.timeline.map((t, k) => (k ? t : { ...t, replaces: "x", value: { amount: "8275000", currency: "USD" }, revision: rev })),
    commitments: { available: true, message: null, rows: [{ commitment_id: "c1", fund_id: profile.funds[0]?.fund_id ?? "", entity: "E", currency: "USD", committed_on: null, commitment: "2000000", called: "50000", uncalled: "1950000" }] } };
  mock([], { "/api/v1/managers/alder-capital": () => json(200, withRev) });
  open("/centre/consume/managers/alder-capital");
  const st = await screen.findByRole("region", { name: "Statements" });
  expect(within(st).getByText(/revised from USD 8,420,000 to USD 8,275,000 \(-145,000\)/)).toBeInTheDocument();
  const table = within(screen.getByRole("region", { name: "Commitments" })).getByRole("table");
  expect(table.parentElement).toHaveStyle({ overflowX: "auto" });
});

it("C2-UC7-08: a document chip in 'what changed' with a link opens it", async () => {
  const withDoc = { ...changes, items: [{ date: "2026-09-28", kind: "document", text: "Document added: N.pdf.", source: { label: "N.pdf", link: "/centre/library/view?file=library%2FN.pdf" } }] };
  mock([], { "/api/v1/managers/alder-capital/changes": () => json(200, withDoc) });
  open("/centre/consume/managers/alder-capital");
  await userEvent.click(await screen.findByRole("button", { name: "Show what changed" }));
  expect(await screen.findByRole("link", { name: "N.pdf" })).toHaveAttribute("href", "/centre/library/view?file=library%2FN.pdf");
});
