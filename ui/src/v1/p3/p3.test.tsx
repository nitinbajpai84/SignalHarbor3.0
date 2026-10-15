import type { ReactElement } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import BuildEntry from "./BuildEntry";
import IntentWelcome from "./IntentWelcome";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const item = (id: string, name: string, mine: boolean) => ({ id, name, kind: "document", note: "board pack", uploaded_by: "Priya Nair", at: "2026-10-01",
  size: 1, visibility: "company", path: "", tags: [], mine, can_change: mine });

afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

function mock(sent: string[], answer: (url: string, init?: RequestInit) => Response | null) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Arjun Mehta", company_id: "neera", roles: ["company_admin"] });
    if (init?.method && init.method !== "GET") sent.push(`${init.method} ${url} ${String(init.body ?? "")}`);
    return answer(url, init) ?? json(404, { error: "not_found", message: "Not found." });
  }));
}
const wrap = (path: string, el: ReactElement) => render(<MemoryRouter initialEntries={[path]}><ThemeProvider><SessionProvider><Routes>
  <Route path={path} element={el} /><Route path="/centre/intent/:iid" element={<p>conversation</p>} />
  <Route path="/centre/build/:iid" element={<p>design room</p>} /></Routes></SessionProvider></ThemeProvider></MemoryRouter>);

const tpl = { id: "standard-intent-of-work", kind: "intent_of_work", kind_name: "Intent of work", name: "Standard intent of work", description: "The things the architect needs.",
  version: 1, state: "adopted", standard: true, required: ["Who reads the result and what they decide from it", "How you will know it worked"],
  good_to_have: ["Documents or emails it depends on"], examples: [{ id: "ex-1", name: "Quarterly fee review" }], unadopted_changes: false, adopted_by: "Seeded", adopted_at: null };

test("the welcome greets by first name, shows the template's questions, starts with the chosen template and no longer shows colleagues' items", async () => {
  const sent: string[] = [];
  mock(sent, (url) => url.startsWith("/api/v1/intents/open") ? json(200, { id: null, greeting: "Hello" })
    : url.startsWith("/api/v1/templates") ? json(200, [tpl])
    : url === "/api/v1/intents/chat" ? json(200, { id: "int-9", intent_id: "int-9" })
    : url.endsWith("/template") ? json(200, { id: "standard-intent-of-work", version: 1 }) : null);
  wrap("/centre/intent", <IntentWelcome />);
  expect(await screen.findByText("Hi Arjun. What are you planning to build today?")).toBeInTheDocument();
  expect(await screen.findByText("How you will know it worked")).toBeInTheDocument();
  expect(screen.getByText("Documents or emails it depends on")).toBeInTheDocument();
  expect(screen.getByText("What you will leave with")).toBeInTheDocument();
  expect(screen.getByText("Need a different template?", { exact: false })).toBeInTheDocument();
  expect(screen.queryByText("Your colleagues shared")).toBeNull();
  await userEvent.type(screen.getByLabelText("What you would like to build"), "A monthly performance pack");
  await userEvent.click(screen.getByRole("button", { name: "Start" }));
  expect(await screen.findByText("conversation")).toBeInTheDocument();
  expect(sent[0]).toMatch(/^POST \/api\/v1\/intents\/chat .*A monthly performance pack.*standard-intent-of-work/);  // the template goes with the first message
});

test("an open conversation skips the welcome", async () => {
  mock([], (url) => url.startsWith("/api/v1/intents/open") ? json(200, { id: "int-3", greeting: "" }) : url.startsWith("/api/v1/library") ? json(200, []) : null);
  wrap("/centre/intent", <IntentWelcome />);
  expect(await screen.findByText("conversation")).toBeInTheDocument();
});

test("NI1: 'Start a new intent' (?new=1) shows the start box even when a conversation is open", async () => {
  mock([], (url) => url.startsWith("/api/v1/intents/open") ? json(200, { id: "int-3", greeting: "" }) : url.startsWith("/api/v1/templates") ? json(200, [tpl]) : null);
  render(<MemoryRouter initialEntries={["/centre/intent?new=1"]}><ThemeProvider><SessionProvider><Routes>
    <Route path="/centre/intent" element={<IntentWelcome />} /><Route path="/centre/intent/:iid" element={<p>conversation</p>} /></Routes></SessionProvider></ThemeProvider></MemoryRouter>);
  expect(await screen.findByText("What do you need?")).toBeInTheDocument();
  expect(screen.getByPlaceholderText(/For example: a monthly report/)).toBeInTheDocument();
  expect(screen.queryByText("conversation")).toBeNull();
});

test("the build entry lists waiting work, picks one up and shows a refusal in plain words", async () => {
  const sent: string[] = [];
  const list = { waiting: [{ intent_id: "int-1", title: "Monthly pack", pid: null, signed_by: "Arjun Mehta", signed_at: "2026-10-07" },
    { intent_id: "int-2", title: "Fee review", pid: null, signed_by: null, signed_at: null }],
  in_build: [{ intent_id: "int-0", title: "Cash view", pid: "prj-1", builder: "Leela Raman", stage: "designed" }] };
  mock(sent, (url) => url === "/api/v1/build/waiting" ? json(200, list)
    : url.endsWith("int-2") ? json(409, { detail: { error: "taken", message: "Leela Raman has already picked this up." } })
    : url.endsWith("int-1") ? json(200, { builder: "Arjun Mehta" }) : null);
  wrap("/centre/build", <BuildEntry />);
  expect(await screen.findByText("Cash view")).toBeInTheDocument();
  expect(screen.getByText("Builder: Leela Raman")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Pick up Fee review" }));
  expect(await screen.findByText("Leela Raman has already picked this up.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Pick up Monthly pack" }));
  expect(await screen.findByText("design room")).toBeInTheDocument();
  expect(sent).toEqual(["POST /api/v1/build/pickup/int-2 ", "POST /api/v1/build/pickup/int-1 "]);
});
