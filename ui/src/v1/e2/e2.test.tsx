import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import real from "./detail.real.json";
import type { DocDetail } from "./api";
import EvidenceList from "./EvidenceList";
import EvidencePage from "./EvidencePage";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

// The real response of GET /api/v1/evidence/documents/{id}, written by tests/v1/test_e2d.py (not a guess of what the server sends).
const detail = real as unknown as DocDetail;
const field = detail.fields.find((f) => f.field === "Net asset value")!;
const DETAIL_URL = `/api/v1/evidence/documents/${detail.id}`;

function mock(sent: string[]) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Mei", company_id: "evergreen", roles: ["analyst"] });
    if (init?.method === "POST") { sent.push(`${url} ${String(init.body ?? "")}`); return json(200, { ...field, state: url.endsWith("/correct") ? "corrected" : "confirmed", valuation_id: "v", exception_id: "e" }); }
    if (url === DETAIL_URL) return json(200, detail);
    if (url === "/api/v1/evidence/documents") return json(200, { documents: [{ id: detail.id, title: "Amended statement", instrument_name: detail.instrument_name,
      valuation_date: detail.valuation_date, received_at: "2026-10-09", label: "Current" }] });
    return json(404, { error: "not_found", message: "Not found." });
  }));
}
const wrap = () => render(<MemoryRouter initialEntries={[`/centre/evidence/${detail.id}`]}><ThemeProvider><SessionProvider>
  <Routes><Route path="/centre/evidence/:documentId" element={<EvidencePage />} /></Routes></SessionProvider></ThemeProvider></MemoryRouter>);

test("shows both statements, the page reference and the match", async () => {
  mock([]);
  wrap();
  expect(await screen.findByText("Superseded")).toBeInTheDocument();
  expect(screen.getByText("Current")).toBeInTheDocument();
  expect(screen.getAllByRole("link", { name: /Page 2, line 2/ })).toHaveLength(2);
  expect(screen.getByText('Matched "Evergreen Growth I" to Evergreen Growth I.')).toBeInTheDocument();
});

test("Confirm reads posts the confirmation and shows Confirmed", async () => {
  const sent: string[] = [];
  mock(sent);
  wrap();
  await userEvent.click(await screen.findByRole("button", { name: "Confirm reads" }));
  await waitFor(() => expect(screen.queryByRole("button", { name: "Confirm reads" })).toBeNull());
  expect(sent[0]).toContain(`/api/v1/evidence/fields/${field.id}/confirm`);
});

test("Not right sends the corrected value", async () => {
  const sent: string[] = [];
  mock(sent);
  wrap();
  await userEvent.click(await screen.findByRole("button", { name: "Not right" }));
  await userEvent.type(screen.getByLabelText("Correct value for Net asset value"), "10,150,000");
  await userEvent.click(screen.getByRole("button", { name: "Save the right value" }));
  expect(await screen.findByText("Corrected")).toBeInTheDocument();
  expect(sent[0]).toContain("/correct");
  expect(sent[0]).toContain("10,150,000");
});

test("the statement list shows the fund name and Current from the real list shape", async () => {
  mock([]);
  render(<MemoryRouter initialEntries={["/centre/evidence"]}><ThemeProvider><SessionProvider><Routes><Route path="/centre/evidence" element={<EvidenceList />} /></Routes></SessionProvider></ThemeProvider></MemoryRouter>);
  expect(await screen.findByText("Evergreen Growth I")).toBeInTheDocument();
  expect(screen.getByText("Current")).toBeInTheDocument();
});

test("a3.14: dates read as on every other screen ('30 Sep 2026'), never ISO", async () => {
  mock([]);
  wrap();
  expect(await screen.findByRole("heading", { name: /valued 30 Sep 2026/ })).toBeInTheDocument();
  expect(screen.getByText(/received 9 Oct 2026/)).toBeInTheDocument();
  expect(screen.queryByText(/2026-\d\d-\d\d/)).toBeNull();
});
