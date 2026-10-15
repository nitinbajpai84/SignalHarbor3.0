import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import CaseView from "./CaseView";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

// Real case shape (see ui/src/v1/e4/case.real.json): exception_type and description come from the server.
const base = { id: "e1", number: "CASE-0001", title: "Cash differs · Entity B · 2026-09-30", materiality: "high", due: null, state: "assigned", amount: 12400, currency: "USD",
  maker_name: "Mei Tan", checker_name: null, proposal: null, affects: [], history: [], can: {} };
const brk = { ...base, exception_type: "break", description: "Entity B cash, administrator against trading export: 1,000,000.00 against 987,600.00 USD on 2026-09-30, a difference of 12,400.00 USD." };
const rev = { ...base, id: "e2", exception_type: "revision", title: "Investigate the difference in Evergreen Growth I", description: null };
const doc = { id: "d1", title: "Evergreen Growth I statement", instrument_name: "Evergreen Growth I", valuation_date: "2026-09-30", received_at: "2026-10-09", label: "Current" };

function open(c: unknown, id: string) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Mei", company_id: "evergreen", roles: ["analyst"] });
    if (url === `/api/v1/cases/${id}`) return json(200, c);
    if (url === "/api/v1/documents" || url.startsWith("/api/v1/evidence")) return json(200, { documents: [doc] });
    return json(404, { error: "not_found", message: "Not found." });
  }));
  render(<MemoryRouter initialEntries={[`/centre/action/cases/${id}`]}><ThemeProvider><SessionProvider>
    <Routes><Route path="/centre/action/cases/:caseId" element={<CaseView />} /></Routes></SessionProvider></ThemeProvider></MemoryRouter>);
}

test("a break shows what was compared, no evidence region, and Where is this from? inside the page frame", async () => {
  open(brk, "e1");
  expect(await screen.findByRole("region", { name: "What was compared" })).toHaveTextContent(/987,600.00 USD/);
  expect(screen.queryByRole("region", { name: "Evidence" })).toBeNull();
  const button = await screen.findByRole("button", { name: "Where is this from?" });
  expect(button.closest("main.ds-frame")).not.toBeNull();
});

test("a revision keeps the evidence region with its statements", async () => {
  open(rev, "e2");
  expect(await screen.findByRole("region", { name: "Evidence" })).toBeInTheDocument();
  expect(await screen.findByRole("link", { name: "Evergreen Growth I statement" })).toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "What was compared" })).toBeNull();
});

test("a case opened by its number gives the trail the case id, and the evidence sits inside the page frame, newest first with dates (a2.3, a1.9, a2.8)", async () => {
  const notice = { id: "d9", title: "Evergreen Growth I distribution notice", instrument_name: "Evergreen Growth I", valuation_date: "", received_at: "2026-10-05", label: "Current" };
  const olds = [1, 2, 3].map((n) => ({ ...doc, id: `o${n}`, title: `Evergreen Growth I statement 2025-0${n}`, valuation_date: `2025-0${n}-28` }));
  const seen: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    seen.push(url);
    if (url === "/api/auth/me") return json(200, { display_name: "Mei", company_id: "evergreen", roles: ["analyst"] });
    if (url === "/api/v1/cases/CASE-0001") return json(200, rev);
    if (url.startsWith("/api/v1/evidence")) return json(200, { documents: [...olds, doc, notice] });
    return json(404, { error: "not_found", message: "Not found." });
  }));
  render(<MemoryRouter initialEntries={["/centre/action/cases/CASE-0001"]}><ThemeProvider><SessionProvider>
    <Routes><Route path="/centre/action/cases/:caseId" element={<CaseView />} /></Routes></SessionProvider></ThemeProvider></MemoryRouter>);
  const region = await screen.findByRole("region", { name: "Evidence" });
  expect(region.closest("main.ds-frame")).not.toBeNull();
  const notes = await screen.findByText(/received 5 Oct 2026/);
  expect(notes.textContent).not.toMatch(/valued ,/);
  const links = within(region).getAllByRole("link").map((a) => a.textContent);
  expect(links.slice(0, 2)).toEqual(["Evergreen Growth I distribution notice", "Evergreen Growth I statement"]);
  expect(links).toHaveLength(3);
  expect(screen.getByRole("button", { name: "Show all 5 documents" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Where is this from?" }));
  await waitFor(() => expect(seen.some((u) => u.includes("trail") && u.includes("id=e2"))).toBe(true));
  expect(seen.some((u) => u.includes("trail") && u.includes("CASE-0001"))).toBe(false);
});
