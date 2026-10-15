import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import IntentWelcome from "../p3/IntentWelcome";
import { routes } from "../i6/routes";
import type { Layout, LayoutSection, OutlineItem, TemplateSummary } from "./api";

// T1b: templates as documents. Fetch is stubbed with synthetic data.
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

const outline: OutlineItem[] = [
  { key: "goal", heading: "What is needed and why", required: true, type: "long_text" },
  { key: "kpis", heading: "The figures wanted", required: true, type: "list" },
];
const sum = (id: string, name: string, standard: boolean): TemplateSummary => ({
  id, kind: "intent_of_work", kind_name: "Intent of work", name, description: `${name} description`, version: 1, state: "adopted", standard, required: [], good_to_have: [],
  examples: [], unadopted_changes: false, adopted_by: "Seeded", adopted_at: null, outline, companions: { process_map: { id: "step-list", name: "Step list" } },
});
const full = { ...sum("quick-data-request", "Quick data request", false), fields: [], free_text: { label: "Comments", required: false },
  sections: [{ key: "goal", heading: "What is needed and why", instruction: "One line: what you need.", example: "September custody fees", required: true, type: "long_text" },
    { key: "kpis", heading: "The figures wanted", instruction: "Each figure, in your words.", example: "", required: true, type: "table", columns: ["name", "definition"] }] };

test("the welcome shows each template as a card with a thumbnail, chooses one and opens its full preview", async () => {
  const sent: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Arjun Mehta", company_id: "neera", roles: ["company_admin"] });
    if (init?.method && init.method !== "GET") sent.push(`${init.method} ${url} ${String(init.body ?? "")}`);
    if (url.startsWith("/api/v1/intents/open")) return json(200, { id: null, greeting: "Hello" });
    if (url === "/api/v1/templates/quick-data-request") return json(200, full);
    if (url.startsWith("/api/v1/templates")) return json(200, [sum("standard-intent-of-work", "Reporting automation", true), sum("quick-data-request", "Quick data request", false)]);
    if (url === "/api/v1/intents/chat") return json(200, { id: "int-9", intent_id: "int-9" });
    return json(404, {});
  }));
  render(<MemoryRouter initialEntries={["/centre/intent"]}><ThemeProvider><SessionProvider><Routes>
    <Route path="/centre/intent" element={<IntentWelcome />} /><Route path="/centre/intent/:iid" element={<p>conversation</p>} /></Routes></SessionProvider></ThemeProvider></MemoryRouter>);
  const group = await screen.findByRole("radiogroup", { name: "Templates" });
  expect(group.querySelectorAll(".tpl-thumb")).toHaveLength(2);                              // a thumbnail drawn from the sections, not an image
  expect(within(group).getAllByText("Comes with: Step list")).toHaveLength(2);
  expect(screen.getByRole("radio", { name: /Reporting automation/ })).toBeChecked();         // the company's standard is pre-selected
  await userEvent.click(screen.getByRole("radio", { name: /Quick data request/ }));
  await userEvent.click(screen.getByRole("button", { name: "Preview Quick data request" }));
  const preview = await screen.findByLabelText("Preview of Quick data request");
  expect(within(preview).getByText("One line: what you need.")).toBeInTheDocument();         // the grey instruction
  expect(within(preview).getByText("For example: September custody fees")).toBeInTheDocument();
  expect(within(preview).getByText("Definition")).toBeInTheDocument();                       // the empty table keeps its columns
  expect(within(preview).getAllByText("Required")).toHaveLength(2);
  await userEvent.type(screen.getByLabelText("What you would like to build"), "Fees");
  await userEvent.click(screen.getByRole("button", { name: "Start" }));
  expect(await screen.findByText("conversation")).toBeInTheDocument();
  expect(sent[0]).toMatch(/quick-data-request/);
});

const S = (o: Partial<LayoutSection> & Pick<LayoutSection, "key" | "heading">): LayoutSection => ({
  instruction: "Grey instruction for " + o.heading, example: "", required: false, type: "text", filled: false, value: "", edits: [], from: [], ...o });
const layout = (kpiFilled: boolean): Layout => ({ documents: [
  { kind: "intent_of_work", title: "Intent of work", template: { id: "quick-data-request", name: "Quick data request", version: 1 }, choices: [], sections: [
    S({ key: "goal", heading: "What is needed and why", required: true, filled: true, value: "Custody fees", edits: [{ label: "Goal", section: "goal", field: "line", value: "Custody fees" }] }),
    kpiFilled ? S({ key: "kpis", heading: "The figures wanted", required: true, type: "list", filled: true, value: ["Custody fees: fees paid"] })
      : S({ key: "kpis", heading: "The figures wanted", required: true, type: "list", instruction: "Each figure, in your words.", example: "Custody fees by manager" }),
    S({ key: "inputs", heading: "Where the data is", required: true, type: "list", filled: kpiFilled, value: kpiFilled ? ["Finance invoices"] : [], from: kpiFilled ? ["Finance invoices"] : [] })] },
  { kind: "process_map", title: "Process map", template: { id: "standard-process-map", name: "Swim lane", version: 1 },
    choices: [{ id: "standard-process-map", name: "Swim lane" }, { id: "step-list", name: "Step list" }], sections: [
      S({ key: "steps", heading: "Lanes and steps", type: "table", view: "swimlane", columns: ["name", "who"], value: { columns: ["name", "who"], rows: [] } })] },
  { kind: "definitions", title: "Definitions", template: { id: "kpi-cards", name: "KPI cards", version: 1 }, choices: [], sections: [
    S({ key: "kpis", heading: "KPI cards", required: true, type: "table", view: "cards", columns: ["name", "definition"], value: { columns: ["name", "definition"], rows: [] } })] },
] });
const sow = { id: "s1", intent_id: "i1", title: "Fees", state: "draft", version: 1, goal: { line: "Custody fees", why: "", readers: [], decisions: [], needed_by: "" },
  process: { steps: [], handovers: [] }, catalogue: [], governance: [], sources: [], kpis: [], unclear: [], signature: null };

test("the three documents open laid out: grey sections stay grey, North's fill is highlighted until accepted, and the process map template switches", async () => {
  const calls: string[] = [];
  let filled = false;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    if (url === "/api/v1/company") return json(200, { who: {}, systems: [], documents: [] });
    if (url.endsWith("/context")) return json(200, { library_ids: [], items: [] });
    if (url.endsWith("/project")) return json(200, { id: null });
    if (method === "PUT" && url.includes("/template/")) { calls.push(`${method} ${url} ${String(init?.body)}`); return json(200, { id: "i1", version: 1 }); }
    if (url.endsWith("/chat")) { const lay = layout(filled); return json(200, { id: "i1", intent_id: "i1", state: "open", needs_done: [], sow, process_map: sow.process, layout: lay, turns: [] }); }
    return json(404, {});
  }));
  const route = routes.find((r) => r.path.startsWith("intent/:iid"));
  render(<ThemeProvider><MemoryRouter initialEntries={["/centre/intent/i1"]}><Routes>
    <Route path="/centre/intent/:iid" element={route?.element} /></Routes></MemoryRouter></ThemeProvider>);
  expect(await screen.findByText("Grey instruction for Where the data is")).toBeInTheDocument();   // grey placeholder, nothing blank
  expect(screen.getByText("Each figure, in your words.")).toBeInTheDocument();
  expect(screen.getByText("For example: Custody fees by manager")).toBeInTheDocument();
  expect(screen.getAllByText("Required").length).toBeGreaterThanOrEqual(3);
  expect(screen.getByText(/2 required sections still to fill in/)).toBeInTheDocument();
  expect(screen.queryByText(/North just filled this in/)).toBeNull();
  // switching the process map template goes through the intent's template route
  filled = true;
  fireEvent.change(screen.getByLabelText("Template for Process map"), { target: { value: "step-list" } });
  await waitFor(() => expect(calls[0]).toBe('PUT /api/v1/intents/i1/template/process_map {"template_id":"step-list"}'));
  // the reload brings North's fill: highlighted, marked as read from a file, and accepted with one click
  expect(await screen.findByText("Custody fees: fees paid")).toBeInTheDocument();
  expect(screen.getAllByText(/North just filled this in/)).toHaveLength(2);
  expect(screen.getByText("From Finance invoices")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Looks right: The figures wanted" }));
  expect(screen.getAllByText(/North just filled this in/)).toHaveLength(1);
});

test("a9.2: a signed document does not say sections are still to fill in, nor mark them Required", async () => {
  const { default: DocumentLayout } = await import("./DocumentLayout");
  const doc = layout(false).documents[0];
  if (!doc) throw new Error("no document in the layout");
  const save = async () => undefined;
  const { unmount } = render(<ThemeProvider><DocumentLayout doc={doc} can save={save} /></ThemeProvider>);
  expect(screen.getByText(/still to fill in/)).toBeInTheDocument();
  unmount();
  render(<ThemeProvider><DocumentLayout doc={doc} can={false} save={save} /></ThemeProvider>);
  expect(screen.queryByText(/still to fill in/)).toBeNull();
  expect(screen.queryByText("Required")).toBeNull();
});
