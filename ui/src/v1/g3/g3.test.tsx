import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { setSessionExpiredHandler } from "../../api/client";
import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import { routes as p1 } from "../p1/routes";
import { routes as g3 } from "./routes";

// G3 and G4 against g3_routes.py and g4_routes.py; fetch is stubbed with synthetic data.
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const row = (id: string, o = {}) => ({ id, code: "NW", kpi: "Net worth", dims: { period: "2026-09", entity: "Tan Family Trust" }, reported: 12400000, expected: 12400000,
  tolerance: 1000, source: "report.md, line 4", source_doc: "documents/report.md", line: 4, stated_by: "Arjun", proposed: false, dropped: false, status: "ready", ...o });
const SHEET = { sheet: { version: 1, state: "draft", rows: [row("r1"), row("r2", { dims: { period: "2026-09", entity: "Lim Holdings" }, reported: null, expected: null, status: "needs figure", source_doc: null, line: null })] },
  columns: ["period", "entity"], sign_block: "x", required: ["Arjun"], missing: ["Net worth"] };
const CHECKS = [{ code: "NW", period: "2026-09", expected: 12400000, got: 12100000, tolerance: 1000, met: false, row_id: "r1" }];
const PROJECT = { id: "prj-1", intent_id: "i1", title: "Wealth report", started_by: "Arjun", started_at: "", stage: "built", artefacts: [],
  people: { raiser: "Arjun", sponsor: "Priya", builder: "Leela", head_of_data: "Leela", ops: null } };
const DEV = { id: "dv_1", summary: "take Net worth from the statements", about: "Net worth", before: "Custodian file", after: "Statements", why: "The file is a month late.",
  effect: ["r1"], effect_labels: ["Net worth, Tan Family Trust"], status: "pending", asks: [{ name: "Leela", cid: "c1" }], decisions: {} };

let calls: { method: string; url: string; body?: unknown }[];
function open(path: string, me: string, extra: (url: string, method: string) => Response | null = () => null) {
  calls = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    const x = extra(url, method);
    if (x) return x;
    if (url === "/api/auth/me") return json({ display_name: me, company_id: "neera", roles: ["analyst"] });
    if (url === "/api/company") return json({ company_id: "neera", name: "Neera", industry: "family_office" });
    if (url === "/api/v1/projects/prj-1") return json(PROJECT);
    if (url.startsWith("/api/v1/projects/prj-1/artefacts/")) return json({ project: "prj-1", kind: "benchmarks", name: "Document", title: "", state: "draft", version: 1, signed_by: null, signed_at: null, signers: [], me, sections: [], comments: [] });
    if (url === "/api/v1/build/i1/benchmarks/sheet") return json(SHEET);
    if (url === "/api/v1/build/i1/benchmarks") return json({ verify: CHECKS });
    if (url === "/api/v1/build/i1/deviations") return json({ intent_id: "i1", deviations: [DEV], pending: null });
    return json({});
  }));
  render(<MemoryRouter initialEntries={[path]}><ThemeProvider><SessionProvider>
    <Routes>{[...p1, ...g3].map((r) => <Route key={r.path} path={`/centre/${r.path}`} element={r.element} />)}</Routes>
  </SessionProvider></ThemeProvider></MemoryRouter>);
}
afterEach(() => { vi.unstubAllGlobals(); setSessionExpiredHandler(null); });

test("the sheet has a column per dimension, flags a missing figure, shows met or missed, and sign shows the refusal", async () => {
  open("/centre/project/prj-1?artefact=benchmarks", "Arjun", (url, m) =>
    url.endsWith("/sheet/sign") && m === "POST" ? json({ message: "1 row has no reported figure yet (Net worth)." }, 409) : null);
  const sheet = await screen.findByLabelText("Benchmark figures");
  expect(sheet).toHaveTextContent("entity");
  expect(sheet).toHaveTextContent("Missed");
  expect(sheet).toHaveTextContent("got 12100000");
  expect(sheet).toHaveTextContent("report.md, line 4");
  expect(screen.getAllByText("needs figure")).toHaveLength(1);
  expect(screen.getByText(/No figure yet for Net worth, 2026-09, Lim Holdings/)).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Reported figure for Net worth"), "8100000");
  await userEvent.click(screen.getByRole("button", { name: "Save figure" }));
  expect(calls.find((c) => c.url.endsWith("/rows/r2"))?.body).toEqual({ reported: "8100000" });
  await userEvent.click(screen.getByRole("button", { name: "Sign the sheet" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("1 row has no reported figure yet");
});

test("the head of data approves a deviation or says Not this with a reason; others only read", async () => {
  open("/centre/project/prj-1", "Leela");
  expect(await screen.findByLabelText("Deviation: take Net worth from the statements")).toHaveTextContent("Net worth, Tan Family Trust");
  await userEvent.click(screen.getByRole("button", { name: "Not this" }));
  await userEvent.type(screen.getByLabelText("Why not"), "Keep the custodian file");
  await userEvent.click(screen.getByRole("button", { name: "Send reason" }));
  expect(calls.find((c) => c.url.endsWith("/decide"))?.body).toEqual({ decision: "not approved", reason: "Keep the custodian file" });
});

test("someone not asked sees the card without buttons", async () => {
  open("/centre/build/i1/deviations", "Arjun");
  expect(await screen.findByText(/Waiting for Leela/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
});

test("Drop last month's report uploads through the library, then the sheet reads that item", async () => {
  open("/centre/project/prj-1?artefact=benchmarks", "Arjun", (url, m) =>
    url === "/api/v1/library" && m === "POST" ? json({ item: { id: "lib_1", name: "sept.md" } })
      : url.endsWith("/sheet/read") && m === "POST" ? json({ ...SHEET, read: 2 }) : null);
  await screen.findByLabelText("Benchmark figures");
  await userEvent.upload(screen.getByLabelText("Drop last month's report"), new File(["Net worth: 1"], "sept.md", { type: "text/markdown" }));
  await vi.waitFor(() => expect(calls.find((c) => c.url.endsWith("/sheet/read"))?.body).toEqual({ item_id: "lib_1" }));
  expect(calls.findIndex((c) => c.url === "/api/v1/library")).toBeLessThan(calls.findIndex((c) => c.url.endsWith("/sheet/read")));
});

test("the source link opens the document at the line, and a locked file shows the server's sentence", async () => {
  open("/centre/build/i1/source?file=documents/report.md&line=2", "Arjun", (url) =>
    url.startsWith("/api/v1/build/i1/benchmarks/sheet/doc") ? json({ name: "report.md", line: 2, lines: [{ n: 1, text: "# Report" }, { n: 2, text: "Net worth: 12,400,000" }] }) : null);
  expect(await screen.findByText("Net worth: 12,400,000")).toBeInTheDocument();
  expect(screen.getByText("Net worth: 12,400,000").closest("li")).toHaveAttribute("aria-current", "true");
});

test("a locked source document says so", async () => {
  open("/centre/build/i1/source?file=documents/board.md&line=1", "Leela", (url) =>
    url.startsWith("/api/v1/build/i1/benchmarks/sheet/doc") ? json({ error: "not_allowed", message: "That file is locked for you." }, 403) : null);
  expect(await screen.findByRole("alert")).toHaveTextContent("That file is locked for you.");
});
