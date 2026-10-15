import type { ReactElement } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import type { Case, CaseRow } from "./api";
import realCase from "./case.real.json";
import realList from "./cases.real.json";
import CasePage from "./CasePage";
import CasesPage from "./CasesPage";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

// The real responses of GET /api/v1/cases/{id} and GET /api/v1/cases, written by tests/v1/test_e4a.py (not a guess of what the server sends).
const base = realCase as unknown as Case;
const row = (realList as unknown as { cases: CaseRow[] }).cases[0]!;
const URL_ = `/api/v1/cases/${base.id}`;

function mock(can: Record<string, boolean>, sent: string[]) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Mei", company_id: "evergreen", roles: ["analyst"] });
    if (init?.method && init.method !== "GET") { sent.push(`${init.method} ${url} ${String(init.body ?? "")}`); return json(200, { ...base, can }); }
    if (url === URL_) return json(200, { ...base, can });
    if (url === "/api/v1/cases") return json(200, { cases: [
      { ...row, id: "c2", number: "CASE-0002", materiality: "low", due: "2026-10-10T00:00:00+00:00" }, { ...row, id: "c3", number: "CASE-0003", materiality: "medium", due: "2026-10-20T00:00:00+00:00" }, { ...row }] });
    return json(404, { error: "not_found", message: "Not found." });
  }));
}
const wrap = (el: ReactElement, at: string) => render(<MemoryRouter initialEntries={[at]}><ThemeProvider><SessionProvider>
  <Routes><Route path="/centre/desk" element={el} /><Route path="/centre/desk/:caseId" element={el} /></Routes></SessionProvider></ThemeProvider></MemoryRouter>);

test("the maker sees Submit but not Approve; the case shows its parts", async () => {
  mock({ explain: true, submit: true, dismiss: false }, []);
  wrap(<CasePage />, `/centre/desk/${base.id}`);
  expect(await screen.findByRole("button", { name: "Submit for check" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
  expect(screen.getByText(/High · maker Mei Tan · checker Raj Iyer/)).toBeInTheDocument();
  expect(screen.getByText(/Affects: September investment report, issued 3 Oct/)).toBeInTheDocument();
  expect(screen.getByText("Proposed by Tally")).toBeInTheDocument();
  expect(screen.getByText("Waiting for a check")).toBeInTheDocument();
  expect(screen.getByText(/Mei Tan: Took the case\./)).toBeInTheDocument();
});

test("the checker sees Approve and Send back, and send back posts the reason the server reads", async () => {
  const sent: string[] = [];
  mock({ approve: true, send_back: true }, sent);
  wrap(<CasePage />, `/centre/desk/${base.id}`);
  await userEvent.click(await screen.findByRole("button", { name: "Send back" }));
  expect(screen.queryByRole("button", { name: "Submit for check" })).toBeNull();
  expect(screen.getByRole("button", { name: "Confirm" })).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Reason for sending back"), "bridge is missing");
  await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
  expect(sent[0]).toBe(`POST ${URL_}/send_back {"reason":"bridge is missing"}`);
});

test("submit sends the explanation (the agent's proposal to start with) and Ask Finance names the person", async () => {
  const sent: string[] = [];
  mock({ submit: true, ask_finance: true }, sent);
  wrap(<CasePage />, `/centre/desk/${base.id}`);
  await userEvent.click(await screen.findByRole("button", { name: "Submit for check" }));
  expect(screen.getByLabelText("Explanation to send for check")).toHaveValue(base.proposal!.text);
  await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
  expect(sent[0]).toContain(`${URL_}/submit {"explanation":"The manager sent an amended statement."}`);
  await userEvent.click(await screen.findByRole("button", { name: "Ask Finance" }));
  await userEvent.type(screen.getByLabelText("Who in Finance should look"), "Raj Iyer");
  await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
  expect(sent[1]).toBe(`POST ${URL_}/ask_finance {"to":"Raj Iyer"}`);
});

test("Ask Tally to write this up posts to /explain", async () => {
  const sent: string[] = [];
  mock({ explain: true }, sent);
  wrap(<CasePage />, `/centre/desk/${base.id}`);
  await userEvent.click(await screen.findByRole("button", { name: "Ask Tally to write this up" }));
  expect(sent[0]).toBe(`POST ${URL_}/explain {}`);
});

test("the list is ordered by materiality then due, from the real list shape", async () => {
  mock({}, []);
  wrap(<CasesPage />, "/centre/desk");
  const links = await screen.findAllByRole("link", { name: /CASE-/ });
  expect(links.map((l) => l.textContent)).toEqual(["CASE-0001", "CASE-0003", "CASE-0002"]);
  expect(screen.getAllByText("High")).toHaveLength(1);
});

test("the Tally file button follows is_owner: an administrator who is not the owner does not see it", async () => {
  const get = (isOwner: boolean) => vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Mei", company_id: "evergreen", roles: ["analyst"] });
    if (url === URL_) return json(200, { ...base, can: { explain: true, submit: true, take: true }, is_owner: isOwner });
    if (url.endsWith("/tally")) return json(200, { case_id: base.id, kind: "cash_break", worded_by: "rules", question: null, answer: null, summary: "s", findings: [], next_steps: [], missing: [],
      proposals: [{ kind: "next_step", who: "Operations", text: "Ask the administrator to confirm the item." }] });
    return json(404, { error: "not_found", message: "Not found." });
  }));
  get(false);
  const first = wrap(<CasePage />, `/centre/desk/${base.id}`);
  expect(await screen.findByText("Only the case owner can file these.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "File these proposals on the case" })).toBeNull();
  first.unmount();
  get(true);
  wrap(<CasePage />, `/centre/desk/${base.id}`);
  expect(await screen.findByRole("button", { name: "File these proposals on the case" })).toBeInTheDocument();
});
