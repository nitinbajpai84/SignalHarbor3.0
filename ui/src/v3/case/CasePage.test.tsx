import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import CasePage from "./CasePage";
import type { CaseView } from "./caseApi";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

const open: CaseView = {
  id: "c1", number: "CASE-0001", title: "Trade T-005 is not at the administrator", status: "open", owner: "Anita", due: "", thread: "t1",
  what: "Trade T-005 is in the trading export but not in the statement.", amount: 592000, currency: "USD", closed: false,
  evidence: [{ source: "Trading export", row: "T-005 booked", side: "have" }, { source: "Not there", row: "No row for T-005", side: "missing" }],
  steps: [{ label: "Ask the administrator", answer: "ask" }, { label: "Mark as timing, expect next month", answer: "timing" }],
  history: [{ at: "2026-10-14T06:12:00", text: "Case opened as CASE-0001." }],
  draft: { to: "[administrator contact]", subject: "T-005", body: "Hello, trade T-005 is missing.", sent: false },
};
const closedCase: CaseView = { ...open, status: "closed", closed: true, steps: [], draft: null, history: [...open.history, { at: "2026-10-14T07:00:00", text: "Booked on the 3rd." }] };

function mock(sent: string[]) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Anita", company_id: "evergreen", roles: ["analyst"] });
    if (init?.method === "POST") { sent.push(`${url} ${String(init.body)}`); return json(200, url.endsWith("/act") ? closedCase : { answer: "I cannot tell yet." }); }
    if (url === "/api/v3/cases/c1") return json(200, open);
    return json(404, { error: "not_found", message: "Not found." });
  }));
}
const show = () => render(<MemoryRouter initialEntries={["/v3/case/c1"]}><ThemeProvider><SessionProvider>
  <Routes><Route path="/v3/case/:id" element={<CasePage />} /></Routes></SessionProvider></ThemeProvider></MemoryRouter>);

test("shows both sides of the evidence and a draft that needs an OK", async () => {
  mock([]);
  show();
  expect(await screen.findByRole("heading", { name: "Trade T-005 is not at the administrator" })).toBeInTheDocument();
  expect(screen.getByText("No row for T-005")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Ask the administrator" }));
  expect(screen.getByLabelText("Drafted email to the administrator")).toHaveTextContent("trade T-005 is missing");
  expect(screen.getByText("Needs your OK.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /send/i })).toBeNull();
});

test("closing needs a reason, then posts it and shows the case closed", async () => {
  const sent: string[] = [];
  mock(sent);
  show();
  const resolved = await screen.findByRole("button", { name: "Resolved" });
  expect(resolved).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Reason (required)"), "Booked on the 3rd.");
  expect(resolved).toBeEnabled();
  await userEvent.click(resolved);
  expect(sent).toEqual(['/api/v3/cases/c1/act {"answer":"resolved","reason":"Booked on the 3rd."}']);
  expect(await screen.findByText("Closed")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Resolved" })).toBeNull();
});

test("the talk box asks Harbor and shows the answer", async () => {
  const sent: string[] = [];
  mock(sent);
  show();
  await userEvent.type(await screen.findByPlaceholderText("Ask about this case…"), "Is this timing?");
  await userEvent.click(screen.getByRole("button", { name: "Ask" }));
  expect(await screen.findByText("I cannot tell yet.")).toBeInTheDocument();
  expect(sent[0]).toContain("/api/v1/cases/c1/ask");
});
