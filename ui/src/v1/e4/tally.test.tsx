import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import type { Tally } from "./api";
import TallyPanel from "./TallyPanel";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

// The shape tests/v1/test_n1_tally.py asserts for the Entity B cash break (GET /api/v1/cases/{id}/tally).
const tally: Tally = {
  case_id: "c1", kind: "cash_break", worded_by: "rules", question: null, answer: null,
  summary: "Entity B cash on 8 Oct 2026: the administrator reports 880,400 USD and the trading export 868,000 USD, a difference of 12,400 USD.",
  findings: [
    { key: "sides", text: "The difference is 12,400 USD, the administrator being higher.", figure: "12,400 USD", chips: [{ label: "Fund administrator · Sheet1 row 4", kind: "position", id: "p1" }] },
    { key: "candidate", text: "A 12,400 USD movement has no match at the other side.", figure: null, chips: [{ label: "Cash call notice", kind: "document", id: "d1" }, { label: "Transaction T-1", kind: "transaction", id: "t1" }] },
  ],
  next_steps: [{ who: "Operations", text: "Ask the administrator for the cash movements posted on 8 Oct 2026." }],
  missing: ["The files carry balances only."],
};

function mock(sent: string[], answer = "No item in the last days appears on one side only.") {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Mei", company_id: "evergreen", roles: ["participant"] });
    if (init?.method === "POST") { sent.push(`${init.method} ${url} ${String(init.body)}`); return json(200, { ...tally, question: "is this timing?", answer }); }
    if (url === "/api/v1/cases/c1/tally") return json(200, tally);
    if (url.startsWith("/api/v1/trail?")) { sent.push(`GET ${url}`); return json(200, { kind: "position", id: "p1", title: "Cash, position", figure: null, steps: [] }); }
    return json(404, { error: "not_found", message: "Not found." });
  }));
}
const show = (props: { canFile?: boolean; onFiled?: () => void } = {}) =>
  render(<MemoryRouter><ThemeProvider><SessionProvider><TallyPanel caseId="c1" {...props} /></SessionProvider></ThemeProvider></MemoryRouter>);
const proposals: Tally["proposals"] = [
  { kind: "explanation", text: "Cause proposed: a timing difference. 12,400 USD cash movement wire W-9.", note: "", item_ref: "W-9", sources: ["Fund administrator · Sheet1 row 4"] },
  { kind: "next_step", who: "Operations", text: "Ask the administrator to confirm the item." }];
function mockProposals(sent: string[]) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Mei", company_id: "evergreen", roles: ["participant"] });
    if (init?.method === "POST") { sent.push(`POST ${url}`); return json(200, { id: "c1" }); }
    return json(200, { ...tally, proposals });
  }));
}

test("the panel shows the summary, findings with source chips, next steps and what is missing", async () => {
  mock([]);
  show();
  expect(await screen.findByRole("heading", { name: "Tally, the data analyst" })).toBeInTheDocument();
  expect(await screen.findByText(/880,400 USD and the trading export 868,000 USD/)).toBeInTheDocument();
  const findings = within(screen.getByRole("list", { name: "Findings" }));
  expect(findings.getByText(/administrator being higher/)).toBeInTheDocument();
  expect(findings.getByRole("link", { name: "Cash call notice" })).toHaveAttribute("href", "/centre/action/evidence/d1");
  expect(within(screen.getByRole("list", { name: "Next steps" })).getByText(/Ask the administrator/)).toBeInTheDocument();
  expect(within(screen.getByRole("list", { name: "Missing" })).getByText("The files carry balances only.")).toBeInTheDocument();
  expect(screen.queryByText(/investigation agent/i)).toBeNull();
});

test("a source chip of a stored fact opens its trail", async () => {
  const sent: string[] = [];
  mock(sent);
  show();
  await userEvent.click(await screen.findByRole("button", { name: "Fund administrator · Sheet1 row 4" }));
  expect(await screen.findByLabelText("Where this is from")).toBeInTheDocument();
  expect(sent).toContain("GET /api/v1/trail?kind=position&id=p1");
});

test("Ask Tally posts the question and shows the answer; nothing else is sent", async () => {
  const sent: string[] = [];
  mock(sent);
  show();
  await userEvent.type(await screen.findByLabelText("Ask Tally a question about this case"), "is this timing?");
  await userEvent.click(screen.getByRole("button", { name: "Ask Tally" }));
  expect(await screen.findByText("No item in the last days appears on one side only.")).toBeInTheDocument();
  expect(sent).toEqual(['POST /api/v1/cases/c1/ask {"question":"is this timing?"}']);
});

test("when Tally cannot answer the person gets a sentence, not a crash", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => url === "/api/auth/me" ? json(200, { display_name: "Mei", company_id: "evergreen", roles: ["analyst"] })
    : json(409, { error: "tally", message: "Tally could not look at this case just now. Please try again in a moment." })));
  show();
  expect(await screen.findByRole("alert")).toHaveTextContent("Tally could not look at this case just now.");
});

test("the case owner files the proposals through the explain route; the proposals show the item and source chip", async () => {
  const sent: string[] = [], filed = vi.fn();
  mockProposals(sent);
  show({ canFile: true, onFiled: filed });
  const list = within(await screen.findByRole("list", { name: "Proposals" }));
  expect(list.getByText("W-9")).toBeInTheDocument();
  expect(list.getByText("Fund administrator · Sheet1 row 4")).toBeInTheDocument();
  expect(list.getByText(/Ask the administrator to confirm the item/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "File these proposals on the case" }));
  expect(await screen.findByRole("button", { name: "Filed on the case" })).toBeDisabled();
  expect(sent).toEqual(["POST /api/v1/cases/c1/explain"]);
  expect(filed).toHaveBeenCalled();
});

test("anyone else sees the proposals read-only", async () => {
  mockProposals([]);
  show();
  await screen.findByRole("list", { name: "Proposals" });
  expect(screen.queryByRole("button", { name: /File these proposals/ })).toBeNull();
  expect(screen.getByText("Only the case owner can file these.")).toBeInTheDocument();
});

// TEACH1: a link to teach Tally for those allowed, and the passages Tally quoted under its answer.
function mockTaught(roles: string[]) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Mei", company_id: "evergreen", roles });
    if (init?.method === "POST") return json(200, { ...tally, question: "when is rebalancing?", answer: "In the first week after quarter end.", used: [{ id: "kn_1", title: "Rebalancing timing", passage: 1, line: "Used: Rebalancing timing, passage 1" }] });
    return json(200, tally);
  }));
}

test("the business owner sees Teach Tally beside Ask Tally, and the answer says which passage was used", async () => {
  mockTaught(["owner"]);
  show();
  const link = await screen.findByRole("link", { name: "Teach Tally" });
  expect(link).toHaveAttribute("href", "/centre/settings/teach?agent=tally");
  await userEvent.type(screen.getByLabelText("Ask Tally a question about this case"), "when is rebalancing?");
  await userEvent.click(screen.getByRole("button", { name: "Ask Tally" }));
  expect(await screen.findByLabelText("Taught knowledge used")).toHaveTextContent("Used: Rebalancing timing, passage 1");
});

test("a participant is not offered Teach Tally", async () => {
  mockTaught(["participant"]);
  show();
  await screen.findByRole("heading", { name: "Ask Tally" });
  expect(screen.queryByRole("link", { name: "Teach Tally" })).toBeNull();
});
