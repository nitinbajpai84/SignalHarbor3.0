import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { setSessionExpiredHandler } from "../../api/client";
import ScanPage from "./ScanPage";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const VIEW = {
  names: { TWR: "Time-weighted return", BMK: "Benchmark relative" }, files: [],
  scan: { intent_id: "i1", at: "2026-10-07T10:00:00+00:00", agreed: null, kpis: [
    { code: "TWR", status: "available", sources_used: ["custodian"], missing: [] },
    { code: "BMK", status: "not", sources_used: [], missing: [{ what: "index_level (Benchmark prices)", where_expected: "landing/" }] },
  ] },
};
const page = () => render(
  <MemoryRouter initialEntries={["/build/i1/scan"]}><Routes><Route path="/build/:iid/scan" element={<ScanPage />} /></Routes></MemoryRouter>);

afterEach(() => { vi.unstubAllGlobals(); setSessionExpiredHandler(null); });

it("shows N of M and agrees the available KPIs", async () => {
  const posts: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") posts.push(`${url} ${String(init.body)}`);
    return json(200, VIEW);
  }));
  page();
  expect(await screen.findByText("These 1 of 2 can be built now.")).toBeInTheDocument();
  expect(screen.getByLabelText("Include BMK")).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: "Agree 1 KPI" }));
  expect(posts[0]).toContain("/api/v1/build/i1/scan/agree");
  expect(posts[0]).toContain('"scope":["TWR"]');
});

it("shows a refusal", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(409, { error: "not_signed", message: "Sign the intent of work first; the scan reads the signed version." })));
  page();
  expect(await screen.findByRole("alert")).toHaveTextContent("Sign the intent of work first");
});
