import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { routes as i3 } from "../i3/routes";
import { routes } from "./routes";

// I6b against I6a's routes (docs/plan/v1-landings/I6a.md); fetch is stubbed with synthetic data.
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const STEPS = [
  { n: 1, name: "Pull custodian file", who: "Operations", does: "Downloads the month-end file", inputs: [], outputs: [], system: "Custodian portal" },
  { n: 2, name: "Reconcile cash", who: "Finance", does: "Matches cash in a spreadsheet", inputs: [], outputs: [], system: "Ledger" },
];
const SOW = {
  id: "s1", intent_id: "i1", title: "Monthly returns against benchmark", state: "draft", version: 2,
  goal: { line: "See monthly returns against the benchmark", why: "Rebalancing", readers: [], decisions: [], needed_by: "" },
  process: { steps: STEPS, handovers: [{ from_step: 1, to_step: 2, what: "Positions file" }] }, catalogue: [], governance: [],
  sources: [{ id: "src1", name: "Custodian positions", kind: "file", holds: "Monthly positions", sample_path: null, owner: "", fields: [] }],
  kpis: [{ code: "twr", name: "Time-weighted return", definition: "Return net of flows", formula: "", unit: "%", period: "month", owner: "",
    source_ids: [], status: "defined", pack_suggested: true }],
  unclear: [{ id: "u1", question: "Net or gross of fees?", about: "twr", who_can_settle: "Priya Nair", settled: false, answer: null }],
  signature: null,
};
const CLOSE = "Here is the intent of work as I understand it; shall I hand it to the architect?";
const CHAT = {
  id: "i1", intent_id: "i1", project_id: "prj-1a2b3c4d", state: "sow_ready", needs_done: [], sow: SOW, process_map: SOW.process,
  turns: [
    { id: "t1", by: "person", name: "Arjun Mehta", text: "Monthly returns against benchmark", at: "2026-10-08T09:00:00Z", need: null, files: [] },
    { id: "t2", by: "north", name: "North", text: CLOSE, at: "2026-10-08T09:00:05Z", need: null, files: [] },
  ],
};
const COMPANY = { who: { name: { value: "Neera Family Office" }, about: { value: "Wealth for one family" } }, systems: [], documents: [] };

function mock({ chatStatus = 200, open = null as string | null, chat = CHAT as object } = {}) {
  const calls: { method: string; url: string; body?: Record<string, unknown> }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    if (url === "/api/v1/company") return json(200, COMPANY);
    if (url === "/api/v1/intents/open") return json(200, { id: open, greeting: "Hello, I am North. I know Neera Family Office. What would you like to build?" });
    if (url === "/api/v1/projects") return json(200, { projects: [{ id: "prj-1a2b3c4d", title: "Quarterly returns pack" }] });
    if (url.endsWith("/context")) return json(200, { library_ids: [], items: [] });
    if (url.endsWith("/project")) return json(200, { id: "prj-1a2b3c4d" });
    if (url.endsWith("/chat")) return chatStatus === 200 ? json(200, chat) : json(chatStatus, { error: "forbidden" });
    if (url.endsWith("/sow") && method === "PUT") return json(200, { ...SOW, version: 3, goal: { ...SOW.goal, why: "Monthly rebalancing" } });
    return json(404, {});
  }));
  return calls;
}
const view = (at: string) => render(
  <ThemeProvider><MemoryRouter initialEntries={[at]}><Routes>
    {[{ path: "intent", element: routes[0]?.element }, ...routes, ...i3]  /* the bare path is P3's now; the page still starts a blank talk */.map((r) => <Route key={r.path} path={`/centre/${r.path}`} element={r.element} />)}
  </Routes></MemoryRouter></ThemeProvider>,
);
const posts = (calls: ReturnType<typeof mock>) => calls.filter((c) => c.method === "POST");

afterEach(() => vi.unstubAllGlobals());

test("a blank conversation greets, starts with the first message, then shows context, SOW, swimlane, closing and hand-over", async () => {
  const calls = mock();
  view("/centre/intent");
  expect(await screen.findByText(/I know Neera Family Office/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Your message"), { target: { value: "Monthly returns against benchmark" } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));

  expect(await screen.findByText(CLOSE)).toBeInTheDocument();
  expect(posts(calls)[0]).toEqual({ method: "POST", url: "/api/v1/intents/chat", body: { text: "Monthly returns against benchmark" } });
  expect(await screen.findByText(/North is reading only what you add/)).toBeInTheDocument();  // the chips under the box; nothing auto-ticked
  expect(screen.getByRole("button", { name: "Add context for a more relevant conversation" })).toBeInTheDocument();
  expect(screen.queryByText("Context")).toBeNull();
  expect(screen.queryByText("Open the company page")).toBeNull();
  expect(screen.getByText("See monthly returns against the benchmark")).toBeInTheDocument();
  expect(screen.getByText("Suggestion")).toBeInTheDocument();
  expect(screen.getByText("Net or gross of fees?")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Sign the intent of work" })).toHaveAttribute("href", "/centre/intent/i1/sow");
  expect(screen.getByRole("link", { name: "Download a copy" })).toHaveAttribute("href", "/api/v1/intents/i1/sow/download");

  // a line edit saves through I4's PUT
  fireEvent.click(screen.getByRole("button", { name: "Edit Why" }));
  fireEvent.change(screen.getByLabelText("Why"), { target: { value: "Monthly rebalancing" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("Monthly rebalancing")).toBeInTheDocument();
  expect(calls.find((c) => c.method === "PUT")).toEqual({ method: "PUT", url: "/api/v1/intents/i1/sow",
    body: { section: "goal", field: "why", value: "Monthly rebalancing", version: 2 } });

  // the swimlane: lanes by who, steps in order, the manual step flagged, the hand-over on its step
  expect(screen.getByRole("heading", { name: "Definitions" })).toBeInTheDocument();  // the three documents sit side by side
  expect(await screen.findByRole("link", { name: "Open the benchmark sheet" })).toHaveAttribute("href", "/centre/project/prj-1a2b3c4d?artefact=benchmarks");
  expect(screen.getByText("Operations")).toBeInTheDocument();
  expect(screen.getByText("Finance")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Step 2: Reconcile cash" })).toHaveTextContent("Manual");
  expect(screen.getByRole("button", { name: "Step 1: Pull custodian file" })).not.toHaveTextContent("Manual");
  expect(screen.getByText("To step 2: Positions file")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Step 2: Reconcile cash" }));
  fireEvent.click(screen.getByRole("button", { name: "Correct a step" }));
  expect(screen.getByLabelText("Your message")).toHaveValue("Step 2: ");
  fireEvent.click(screen.getByRole("button", { name: "That's right" }));
  await waitFor(() => expect(posts(calls).pop()).toEqual({ method: "POST", url: "/api/v1/intents/i1/chat", body: { text: "The process map is right" } }));

  // a message with a file travels inline as base64
  const file = new File(["a,b\n1,2"], "cash.csv", { type: "text/csv" });
  fireEvent.drop(screen.getByRole("form", { name: "Message North" }), { dataTransfer: { files: [file] } });  // the only attach control is "Add context"; a file can still be dropped on the box
  fireEvent.change(screen.getByLabelText("Your message"), { target: { value: "Here is the cash file." } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  await waitFor(() => expect(posts(calls).pop()).toEqual({ method: "POST", url: "/api/v1/intents/i1/chat",
    body: { text: "Here is the cash file.", files: [{ name: "cash.csv", data: btoa("a,b\n1,2"), kind: "sample" }] } }));
});

test("the entry opens the open intent, and the old thread link redirects", async () => {
  mock({ open: "i1" });
  view("/centre/intent");
  expect(await screen.findByText(CLOSE)).toBeInTheDocument();
  view("/centre/intent/i1/thread");
  await waitFor(() => expect(screen.getAllByText(CLOSE)).toHaveLength(2));
});

test("N1-INT-01: a question on the landing is answered with no draft and no project line", async () => {
  mock({ open: "i1", chat: { ...CHAT, landing: true, project_id: null, state: "gathering", sow: { ...SOW, title: "New intent" }, process_map: SOW.process } });
  view("/centre/intent");
  expect(await screen.findByText(CLOSE)).toBeInTheDocument();
  expect(screen.getByText(/nothing is drafted yet/)).toBeInTheDocument();
  expect(screen.queryByText(/Project:/)).toBeNull();
});

test("a refused conversation says so in plain words", async () => {
  mock({ chatStatus: 403 });
  view("/centre/intent/i1");
  expect(await screen.findByRole("alert")).toHaveTextContent(/access/i);
  expect(screen.queryByText(CLOSE)).not.toBeInTheDocument();
});

test("I1: sources show structure, owner, arrival and samples; a signed intent can be sent to Build", async () => {
  const signed = { ...CHAT, state: "sow_ready", project_id: "prj-1a2b3c4d", build: null as null | { by: string; at: string; project_id: string },
    sow: { ...SOW, state: "signed", signature: { name: "Arjun Mehta", role: "x", at: "2026-10-09T09:00:00Z" },
      sources: [{ ...SOW.sources[0], owner: "Leela Raman", arrives: "monthly", structure: "structured", samples: ["admin_sep.csv"] },
                { id: "src2", name: "Manager statements", kind: "document", holds: "Valuations", sample_path: null, owner: "Mei", fields: [] }] } };
  const calls: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push(`${init?.method ?? "GET"} ${url}`);
    if (url.endsWith("/send-to-build")) { signed.build = { by: "Arjun Mehta", at: "now", project_id: "prj-1a2b3c4d" }; return json(200, signed.build); }
    if (url.endsWith("/project")) return json(200, { id: "prj-1a2b3c4d" });
    if (url.endsWith("/context")) return json(200, { library_ids: [], items: [] });
    if (url.endsWith("/chat")) return json(200, signed);
    return json(404, {});
  }));
  view("/centre/intent/i1");
  expect(await screen.findByText("Sources: systems and files")).toBeInTheDocument();
  expect(screen.getByText(/Owner: Leela Raman\. Arrives monthly\. Sample: admin_sep\.csv\./)).toBeInTheDocument();
  expect(screen.getByText("Unstructured")).toBeInTheDocument();  // a document source defaults to unstructured
  expect(await screen.findByRole("link", { name: "Open the project page" })).toHaveAttribute("href", "/centre/project/prj-1a2b3c4d");
  expect(screen.queryByText(/prj-1a2b3c4d/)).toBeNull();  // j-uc10a.0: never the raw project id
  fireEvent.click(screen.getByRole("button", { name: "Send to Build" }));
  expect(await screen.findByText("Sent to Build")).toBeInTheDocument();
  expect(calls).toContain("POST /api/v1/intents/i1/send-to-build");
});

test("a9.1: a project the person may not read shows the lock card with Request access, not Try again", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url.endsWith("/chat")) return json(403, { detail: { error: "not_allowed", message: "This project is Internal. Ask for access and Daniel Foo will answer." } });
    if (url.endsWith("/project")) return json(200, { id: "prj-9", locked: true, access: "preview", sensitivity: "internal", can_request: true,
      title: "Monthly investment report", stage: "live", owner: "Daniel Foo", request: null });
    return json(404, {});
  }));
  view("/centre/intent/i1");
  expect(await screen.findByRole("button", { name: "Request access" })).toBeInTheDocument();
  expect(screen.getByText(/Owner: Daniel Foo/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
});

test("a9.2, a9.3: a signed intent whose project is live says Live once, offers no Send to Build, and North is not waiting", async () => {
  const live = { ...CHAT, state: "open", stage: "live", build: null, project_id: "prj-1a2b3c4d",
    sow: { ...SOW, state: "signed", signature: { name: "Daniel Foo", role: "sponsor", at: "2026-10-09T09:00:00Z" } } };
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url.endsWith("/project")) return json(200, { id: "prj-1a2b3c4d", stage: "live" });
    if (url.endsWith("/context")) return json(200, { library_ids: [], items: [] });
    if (url.endsWith("/chat")) return json(200, live);
    return json(404, {});
  }));
  view("/centre/intent/i1");
  expect(await screen.findByText("Live")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Send to Build" })).toBeNull();
  expect(screen.queryByText(/waiting/i)).toBeNull();
  expect(await screen.findByRole("link", { name: "Open the project page (live)" })).toBeInTheDocument();
});

test("NI1: the header names the project (never its id) and offers to start a new intent; a blank talk invites the first description", async () => {
  mock();
  view("/centre/intent/i1");
  expect(await screen.findByText("Quarterly returns pack")).toBeInTheDocument();
  expect(screen.queryByText(/prj-1a2b3c4d/)).toBeNull();
  expect(screen.getByRole("link", { name: "Start a new intent" })).toHaveAttribute("href", "/centre/intent?new=1");
});

test("NI1: a brand-new intent's box invites the first description", async () => {
  mock();
  view("/centre/intent");
  expect(await screen.findByPlaceholderText(/Describe what you need in your own words/)).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Start a new intent" })).toBeNull();
});
