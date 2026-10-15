import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { setSessionExpiredHandler } from "../../api/client";
import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import { routes } from "./routes";

// F1 against f1_routes.py; fetch is stubbed with synthetic data.
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const P1 = { id: "pa", kind: "formula", row: 3, about: "Concentration", understood: "Largest issuer over the total.", needs: "the rule in your words, or the SQL",
  why: "Flow could not write the SQL.", question: "Row 3: Concentration. Confirm, tell me the rule, or paste the SQL.", sql: null, flagged: null };
const P2 = { id: "pb", kind: "check", row: null, about: "Custodian positions", understood: "The check failed on 12 rows.", needs: "whether the file or the check is wrong",
  why: null, question: "Is the file wrong, or the check?", sql: null, flagged: null };
const CTX = { catalogue_tables: 4, mapping_rows: 3, mapping_version: 1, transformations: 3, sql_rows: 0, data_model_tables: 2, runs: 1, skill: "Data engineer playbook" };
const VIEW = { intent_id: "i1", turns: [], opening: "I have read the catalogue (4 tables). I have 2 open points; here is the first. Row 3: Concentration.",
  points: [P1, P2], current: "pa", context: CTX, handed_over: false };
const AFTER = { ...VIEW, points: [P2], current: "pb", turns: [
  { id: "t1", by: "flow", name: "Flow", text: VIEW.opening, at: "2026-10-08T09:00:00Z", point: null },
  { id: "t2", by: "person", name: "Leela Raman", text: "Confirmed", at: "2026-10-08T09:01:00Z", point: "pa" },
  { id: "t3", by: "flow", name: "Flow (rules only)", text: "Confirmed as I understood it. Next: Is the file wrong, or the check?", at: "2026-10-08T09:01:01Z", point: "pa" }] };

let calls: { method: string; url: string; body?: unknown }[];
function open(roles: string[], engineer: () => Response = () => json(VIEW)) {
  calls = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    if (url === "/api/auth/me") return json({ display_name: "Leela", company_id: "neera", roles });
    if (url === "/api/company") return json({ company_id: "neera", name: "Neera", industry: "family_office" });
    if (url === "/api/v1/build/i1/engineer") return method === "POST" ? json(AFTER) : engineer();
    if (url === "/api/v1/build/i1/runs") return json({ contracts: [], runs: [] });
    return json({});
  }));
  render(<MemoryRouter initialEntries={["/centre/build/i1/engineer"]}><ThemeProvider><SessionProvider>
    <Routes>{routes.map((r) => <Route key={r.path} path={`/centre/${r.path}`} element={r.element} />)}</Routes>
  </SessionProvider></ThemeProvider></MemoryRouter>);
}
afterEach(() => { vi.unstubAllGlobals(); setSessionExpiredHandler(null); });

test("Flow opens with the first point, lists the open points and walks to the next on an answer", async () => {
  open(["analyst"]);
  expect(await screen.findByText(/I have 2 open points/)).toBeInTheDocument();
  expect(screen.getByLabelText("Open point: Concentration")).toHaveTextContent("Largest issuer over the total.");
  expect(screen.getByText(/Skill: Data engineer playbook/)).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Your message"), "Confirmed");
  await userEvent.click(screen.getByRole("button", { name: "Send" }));
  expect(await screen.findByText(/Next: Is the file wrong/)).toBeInTheDocument();
  expect(calls.find((c) => c.method === "POST")?.body).toEqual({ text: "Confirmed" });
  expect(screen.getByLabelText("Point to flag")).toBeInTheDocument();
});

test("a sponsor reads without a composer, and a missing sheet says so", async () => {
  open(["sponsor"]);
  expect(await screen.findByText(/the head of data answers Span/)).toBeInTheDocument();
  expect(screen.queryByLabelText("Your message")).toBeNull();
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
  open(["analyst"], () => json({ error: "not_found", message: "There is no mapping sheet for this intent yet." }, 404));
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("no mapping sheet"));
});
