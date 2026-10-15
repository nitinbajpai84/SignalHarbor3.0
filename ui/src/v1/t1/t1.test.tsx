import type { ReactElement } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import AdminAgents from "./AdminAgents";
import RequestBox from "./RequestBox";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

function mock(roles: string[], sent: string[], answer: (url: string) => Response | null) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Arjun Mehta", company_id: "neera", roles });
    if (init?.method && init.method !== "GET") sent.push(`${init.method} ${url} ${String(init.body ?? "")}`);
    return answer(url) ?? json(404, { error: "not_found", message: "Not found." });
  }));
}
const wrap = (el: ReactElement) => render(<MemoryRouter><ThemeProvider><SessionProvider>{el}</SessionProvider></ThemeProvider></MemoryRouter>);

test("the console is for the company admin only", async () => {
  mock(["analyst"], [], () => null);
  wrap(<AdminAgents />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Only your company admin");
});

test("the admin sees templates, requests and can adopt", async () => {
  const sent: string[] = [];
  const row = { id: "standard-intent-of-work", kind: "intent_of_work", kind_name: "Intent of work", name: "Standard intent of work", description: "", version: 1,
    state: "adopted", standard: true, required: ["x"], good_to_have: [], examples: [], unadopted_changes: false, adopted_by: "Seeded", adopted_at: null };
  const full = { ...row, fields: [{ key: "goal", label: "What you want to build", help: "", required: true, type: "long_text" }], free_text: { label: "Comments and anything else", required: false }, examples: [] };
  mock(["company_admin"], sent, (url) => url.startsWith("/api/v1/templates?") ? json(200, [row])
    : url.endsWith("/adopt") ? json(200, { ...full, version: 2 }) : url === "/api/v1/templates/standard-intent-of-work" ? json(200, full)
    : url === "/api/v1/admin/requests" ? json(200, [{ id: "REQ-0001", kind: "template", about: "", text: "A fee review template", by: "Leela Raman", at: "2026-10-08T10:00:00", state: "open", note: "" }]) : null);
  wrap(<AdminAgents />);
  await userEvent.click(await screen.findByRole("button", { name: "Standard intent of work" }));
  expect(await screen.findByText("Every template ends with “Comments and anything else”.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Adopt" }));
  expect(await screen.findByText("Adopted: a new version.")).toBeInTheDocument();
  expect(sent[0]).toMatch(/^POST \/api\/v1\/templates\/standard-intent-of-work\/adopt/);
  await userEvent.click(screen.getByText("Requests"));
  expect(await screen.findByText("A fee review template")).toBeInTheDocument();
});

test("a person asks the company admin for a template", async () => {
  const sent: string[] = [];
  mock(["analyst"], sent, (url) => url === "/api/v1/template-requests" ? json(200, { id: "REQ-0001" }) : null);
  wrap(<RequestBox />);
  await userEvent.click(screen.getByRole("button", { name: "Ask your company admin" }));
  await userEvent.type(screen.getByLabelText("What template do you need"), "A fee review");
  await userEvent.click(screen.getByRole("button", { name: "Send request" }));
  expect(await screen.findByText(/Your company admin has your request/)).toBeInTheDocument();
  expect(sent[0]).toMatch(/A fee review/);
});
