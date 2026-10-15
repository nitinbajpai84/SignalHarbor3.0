import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { SessionProvider } from "../../useSession";
import { GlossaryTab } from "./GlossaryTab";

// Spec 29 Screens A, B and C. fetch is stubbed with synthetic terms.

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const cell = (value: string | null) => ({ value, mark: value ? "guessed" : "unknown", by: "Lens", at: "", from: "" });
const text = (term: string, definition: string, owner: string) => ({
  term, aliases: "", definition, how_sure: "A guess (Lens)", previous: "Not available yet", owner, frequency: "", who: "", personal: "", change: "New",
  assumption: "", source: "", reviewed: "", decided_by: "", proposal: "",
});
const entry = (kpi: string, term: string, owner: string, reviewed = false) => ({
  kpi_id: kpi, change: "new", business_definition: cell(`${term} meaning`), previous: cell(null), assumption: "", source_document: "Fund report pack",
  reviewed: reviewed ? { by: "x", at: "y" } : null, text: text(term, `${term} meaning`, owner),
});
const VIEW = {
  baseline_id: "b1", signed: false, lens_available: true, built: true, waiting: 0, provided: null, unmatched_terms: [],
  entries: [entry("k1", "Net return", "Harvey Rowley"), entry("k2", "Exposure", "Grace Ward", true)],
  counts: { all: 2, changed: 0, new: 2, unchanged: 0, reviewed: 1 },
};
const AMB = { id: "amb-1", kpi_id: "k1", kpi_name: "Net return", text: "return on assets, or return of capital", question: "Which return?", where: "finance pack",
  status: "open", raised_by: "Lens", resolution: null, by: null, at: "2026-10-04T00:00:00Z", kind: "other", owner: "Harvey Rowley", derived: false };

function mock(name: string, roles: string[], opts: { baseline?: string | null; glossary?: number; view?: unknown } = {}) {
  const posts: { url: string; body: unknown }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method && init.method !== "GET") {
      posts.push({ url, body: init.body ? JSON.parse(String(init.body)) : {} });
      return json(200, VIEW);
    }
    if (url === "/api/auth/me") return json(200, { display_name: name, company_id: "co-a", roles });
    if (url.endsWith("/glossary-start")) return json(200, { intent_id: "i1", baseline_id: opts.baseline === undefined ? "b1" : opts.baseline, terms: [], counts: null, questions_left: 2, people: [{ display_name: "Harvey Rowley" }, { display_name: "Aaron Lyle" }], can_settle: roles.includes("company_admin") });
    if (url.endsWith("/glossary")) return opts.glossary ? json(opts.glossary, { detail: "No." }) : json(200, opts.view ?? VIEW);
    if (url.endsWith("/ambiguities")) return json(200, { ambiguities: [AMB] });
    return json(200, {});
  }));
  return posts;
}
const view = (path = "/centre/intent/i1/define?tab=glossary") =>
  render(<MemoryRouter initialEntries={[path]}><SessionProvider><GlossaryTab intentId="i1" /></SessionProvider></MemoryRouter>);

afterEach(() => vi.unstubAllGlobals());

test("Screen A: counts, chips, rows, search and the drawer", async () => {
  mock("Janet Shaw", ["company_admin"]); view();
  expect(await screen.findByText("2 terms: 1 confirmed, 1 draft, 0 ambiguous accepted")).toBeInTheDocument();
  expect(screen.getByText("Not available yet. Sources not counted.")).toBeInTheDocument();
  expect(screen.getByText("Update draft")).toBeInTheDocument();
  expect(screen.getByText("Mine 0")).toHaveAttribute("aria-disabled", "true");
  fireEvent.click(screen.getByRole("button", { name: "Confirmed" }));
  expect(screen.queryByText("Net return")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "All" }));
  fireEvent.change(screen.getByLabelText("Search terms"), { target: { value: "zzz" } });
  expect(screen.getByText("No term matches")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Search terms"), { target: { value: "net" } });
  fireEvent.click(screen.getByText("Net return"));
  expect(await screen.findByText("return on assets, or return of capital")).toBeInTheDocument();
  expect(screen.getByText("A guess by Lens")).toBeInTheDocument();
});

test("Screen A empty", async () => {
  mock("Janet Shaw", ["company_admin"], { view: { ...VIEW, built: false, entries: [], counts: { all: 0, changed: 0, new: 0, unchanged: 0, reviewed: 0 } } }); view();
  expect(await screen.findByText("No terms yet. Lens drafts them when the wall closes.")).toBeInTheDocument();
  expect(screen.getByText("Ask Lens to draft now")).toBeInTheDocument();
});

test("a role the glossary is closed to reads Not available yet", async () => {
  mock("Aaron Lyle", ["participant"], { glossary: 403 }); view();
  expect(await screen.findByText(/Not available yet. The terms open to the organiser/)).toBeInTheDocument();
  expect(screen.queryByText("Ask Lens to draft now")).not.toBeInTheDocument();
});

test("Screen B: the owner confirms a term", async () => {
  const posts = mock("Harvey Rowley", ["analyst"]); view("/centre/intent/i1/define?tab=glossary&view=mine");
  expect(await screen.findByText("Term 1 of 1. You have 2 questions left of 3.")).toBeInTheDocument();
  expect(screen.getByText("Which return?")).toBeInTheDocument();
  fireEvent.click(screen.getByText("Mine, wording is right"));
  await waitFor(() => expect(posts[0]).toEqual({ url: "/api/intents/i1/glossary/k1/reply", body: { action: "mine" } }));
});

test("Screen C: accepting a risk needs a reason", async () => {
  const posts = mock("Janet Shaw", ["company_admin"]); view("/centre/intent/i1/define?tab=glossary&view=ambiguities");
  fireEvent.click(await screen.findByText("Net return"));
  fireEvent.click(screen.getByText("Accept as a known risk"));
  expect(screen.getByText("A reason is required")).toBeInTheDocument();
  expect(posts).toHaveLength(0);
  fireEvent.change(screen.getByLabelText("Why you accept it"), { target: { value: "Both meanings are in use" } });
  fireEvent.click(screen.getByText("Accept as a known risk"));
  await waitFor(() => expect(posts[0]?.url).toBe("/api/modules/m2_baseline/baselines/b1/kpis/k1/ambiguities/amb-1/accept"));
});

test("Screen B: not mine, it is Aaron; both are used; change the wording", async () => {
  const posts = mock("Harvey Rowley", ["owner"]); view("/centre/intent/i1/define?tab=glossary&view=mine");
  await screen.findByText("Term 1 of 1. You have 2 questions left of 3.");
  fireEvent.change(screen.getByLabelText("Who owns it"), { target: { value: "Aaron Lyle" } });
  fireEvent.click(screen.getByText("Not mine, it is Aaron Lyle"));
  await waitFor(() => expect(posts[0]).toEqual({ url: "/api/intents/i1/glossary/k1/reply", body: { action: "not_mine", owner: "Aaron Lyle" } }));
  fireEvent.change(screen.getByLabelText("A note for the governance lead (optional)"), { target: { value: "Both in the pack" } });
  fireEvent.click(screen.getByText("Both are used, send to the governance lead"));
  await waitFor(() => expect(posts[1]).toEqual({ url: "/api/intents/i1/glossary/k1/reply", body: { action: "both_used", amb_id: "amb-1", note: "Both in the pack" } }));
  fireEvent.click(screen.getByText("Mine, change the wording"));
  fireEvent.change(screen.getByLabelText("Mine, change the wording"), { target: { value: "Return after fees." } });
  fireEvent.click(screen.getByText("Save wording"));
  await waitFor(() => expect(posts[2]?.body).toEqual({ action: "mine", wording: "Return after fees." }));
});

test("Screen C: keep both names the second term; a settled row can be reopened; a non-settler reads only", async () => {
  const posts = mock("Janet Shaw", ["company_admin"]); view("/centre/intent/i1/define?tab=glossary&view=ambiguities");
  fireEvent.click(await screen.findByText("Net return"));
  fireEvent.change(screen.getByLabelText("Name of the second term"), { target: { value: "Return of capital" } });
  fireEvent.click(screen.getByText("Keep both, name the second term"));
  await waitFor(() => expect(posts[0]).toEqual({ url: "/api/intents/i1/glossary/k1/reply", body: { action: "keep_both", amb_id: "amb-1", second_term: "Return of capital" } }));
});

test("Screen C: reopen with a reason", async () => {
  const posts = mock("Janet Shaw", ["company_admin"]); view("/centre/intent/i1/define?tab=glossary&view=ambiguities");
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method && init.method !== "GET") { posts.push({ url, body: JSON.parse(String(init.body)) }); return json(200, VIEW); }
    if (url === "/api/auth/me") return json(200, { display_name: "Janet Shaw", company_id: "co-a", roles: ["company_admin"] });
    if (url.endsWith("/glossary-start")) return json(200, { intent_id: "i1", baseline_id: "b1", terms: [], counts: null, questions_left: 2, can_settle: true });
    if (url.endsWith("/glossary")) return json(200, VIEW);
    if (url.endsWith("/ambiguities")) return json(200, { ambiguities: [{ ...AMB, status: "accepted", resolution: "Both used", by: "Harvey Rowley" }] });
    return json(200, {});
  }));
  view("/centre/intent/i1/define?tab=glossary&view=ambiguities");
  fireEvent.click((await screen.findAllByText("Net return")).pop() as HTMLElement);
  expect(screen.getByRole("button", { name: "Reopen" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Why you reopen it"), { target: { value: "Pack changed" } });
  fireEvent.click(screen.getByRole("button", { name: "Reopen" }));
  await waitFor(() => expect(posts.at(-1)?.body).toEqual({ action: "reopen", amb_id: "amb-1", reason: "Pack changed" }));
});
