import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import App from "../../../App";
import { setSessionExpiredHandler } from "../../../api/client";
import type { LensState, PreRead, Prov } from "../api";
import { m2Lens, m2Nira, m2Pre } from "../copy";

// M2-AGENTS: Lens's own block with Nira's small strip, on every module 2 screen; and the pre-read step. fetch is stubbed.

const BASE = "/api/modules/m2_baseline";
const BID = "a".repeat(32);
const prov = (value: string | null, mark: Prov["mark"] = "guessed", by = "Lens", from = "Reporting note"): Prov => ({ value, mark, by, from, at: "2026-10-04T10:00:00+00:00" });
const lens = (over: Partial<LensState> = {}): LensState => ({
  available: true, locked: false, pack: { available: true, label: "Family office" }, pending: [], failed: [], drafting: [], documents: 2, people: [{ account_id: "x", display_name: "Mei Tan" }],
  refine: [], asks: [], say: { did: "I read 2 documents you gave me. I filled a definition for 1 of 2.", next: "Use a definition, edit it, or tell me what to change.", need: "Nothing right now." }, ...over,
});
const item = { id: "K1", name: "Excess return", kind: "measure" as const, definition: prov("Return above the benchmark."), label: null, problems: ["Managers ahead or behind benchmarks"] };
const sug = { id: "K2", name: "Net return", kind: "suggestion" as const, definition: prov("What others track.", "guessed", "the pack", "Family office industry pack (suggestion)"), label: "What others in the industry usually track", problems: [] };

interface W {
  lens?: LensState | "fail";
  pre?: PreRead;
}
const calls: { method: string; url: string; body: unknown }[] = [];
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
function mock(w: W) {
  calls.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    if (url === "/api/auth/me") return json(200, { display_name: "Pat Owner", company_id: "co-a", roles: ["company_admin"] });
    if (url === "/api/company") return json(200, { company_id: "co-a", name: "Harbor Test Co", industry: "family_office" });
    if (url === "/api/modules") return json(200, [{ id: "m2_baseline", number: 2, name: "Baseline", description: "d", agent: "Lens" }]);
    if (url === `${BASE}/baselines/${BID}/lens` && method === "GET") return w.lens === "fail" ? json(500, {}) : json(200, w.lens ?? lens());
    if (url === `${BASE}/baselines/${BID}/nira`) {
      const k = (JSON.parse(String(init?.body)) as { kind: string }).kind;
      return json(200, { name: "Nira", role: "the guide", available: true, text: k === "now" ? "Name the owners of each measure." : k === "ask" ? "Click a row to name its owners." : "You are on step 1 of 5, the work list. Still waiting for an answer from Mei Tan." });
    }
    if (url === `${BASE}/baselines/${BID}/preread` && method === "GET") return json(200, w.pre ?? pre());
    if (url.startsWith(`${BASE}/baselines/${BID}/preread/`)) return json(200, pre({ kinds: pre().kinds.map((k, i) => (i === 0 ? { ...k, none: true } : k)) }));
    if (url === `${BASE}/baselines/${BID}/lens/ask`) return json(200, { name: "Lens", role: "the business analyst", available: true, changed: true, text: "I redrafted it." });
    if (method !== "GET" && url.startsWith(`${BASE}/baselines/${BID}/`)) return json(200, { baseline: { id: BID, state: "draft" }, kpis: [], problems: [], suggestions: [], suggestion_label: "s", pack: { available: true, label: "x" }, owners_complete: 0, lens_available: true });
    if (url === `${BASE}/baselines/${BID}`) return json(200, { baseline: { id: BID, charter_outcome_id: null, state: "draft", created_at: "2026-10-04T10:00:00+00:00" }, charter: null, problems: [], kpis: [], suggestions: [], suggestion_label: "s", pack: { available: true, label: "x" }, owners_complete: 0, lens_available: true });
    return json(404, {});
  }));
}
const pre = (over: Partial<PreRead> = {}): PreRead => ({
  kinds: [{ key: "glossary", label: "Business glossary", help: "The words your company uses.", none: false, docs: [] },
    { key: "procedures", label: "Process or procedure documents", help: "How the numbers are produced.", none: false, docs: [{ doc_id: "d1", title: "Reporting note" }] }],
  documents: [{ doc_id: "d1", title: "Reporting note", restricted: false }, { doc_id: "d2", title: "Pay bands", restricted: true }], can_upload: true, pack: { available: true, label: "Family office" }, ...over,
});
const open = (path: string) => render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
const screens = ["baselines", "requests", "process-map", "catalogue", "signoff"];

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  sessionStorage.clear();
  setSessionExpiredHandler(null);
});

describe("Lens's block: the five states", () => {
  test("populated: what Lens did, proposes and needs, and what to review", async () => {
    mock({ lens: lens({ refine: [item, sug] }) });
    open(`/modules/m2_baseline/baselines/${BID}`);
    expect(await screen.findByText(/I read 2 documents you gave me/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: `${m2Lens.use}: Excess return` })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: `${m2Lens.tell}: Excess return` })).toBeInTheDocument();
    expect(screen.getByText(/What others in the industry usually track/)).toBeInTheDocument(); // a suggestion is labelled as one
  });

  test("loading, then empty (nothing to review yet)", async () => {
    mock({ lens: lens() });
    open(`/modules/m2_baseline/baselines/${BID}`);
    expect(await screen.findByText(m2Lens.loading)).toBeInTheDocument(); // the block opens at once; its content follows
    expect(await screen.findByText(m2Lens.noItems)).toBeInTheDocument();
  });

  test("error and refused read the same in plain words, with a way to try again", async () => {
    mock({ lens: "fail" });
    open(`/modules/m2_baseline/baselines/${BID}`);
    expect(await screen.findByText(new RegExp(m2Lens.loadFailed))).toBeInTheDocument();
    expect(screen.getByRole("button", { name: m2Lens.retry })).toBeInTheDocument();
  });

  test("it says honestly when there is no industry text and nothing uploaded", async () => {
    mock({ lens: lens({ pack: { available: false, label: "" }, documents: 0, say: { did: "I have no industry knowledge for this company yet and no documents to read, so I have nothing to suggest. I will have to ask you.", next: "x", need: "Nothing right now." } }) });
    open(`/modules/m2_baseline/baselines/${BID}`);
    expect(await screen.findByText(/no industry knowledge for this company/)).toBeInTheDocument();
  });

  test("a model that is not set up is said, and a signed baseline is read-only", async () => {
    mock({ lens: lens({ available: false, locked: true }) });
    open(`/modules/m2_baseline/baselines/${BID}`);
    expect(await screen.findByText(m2Lens.signedNote)).toBeInTheDocument();
  });
});

describe("the first move, without a click", () => {
  test("Lens drafts what is pending one at a time, suggestions by suggestion id, and shows progress", async () => {
    mock({ lens: lens({ pending: ["K1", "K2"], refine: [item, sug] }) });
    open(`/modules/m2_baseline/baselines/${BID}`);
    await waitFor(() => expect(calls.filter((c) => c.url.endsWith("/lens/draft"))).toHaveLength(2));
    const drafts = calls.filter((c) => c.url.endsWith("/lens/draft")).map((c) => c.body);
    expect(drafts).toEqual([{ kpi_ids: ["K1"] }, { suggestion_ids: ["K2"] }]);
  });

  test("locked: Lens drafts nothing", async () => {
    mock({ lens: lens({ locked: true, pending: ["K1"], refine: [item] }) });
    open(`/modules/m2_baseline/baselines/${BID}`);
    await screen.findByText(m2Lens.signedNote);
    expect(calls.some((c) => c.url.endsWith("/lens/draft"))).toBe(false);
  });
});

describe("review: use, edit, tell Lens what to change", () => {
  test("use this definition records the person's own; edit saves their words; tell Lens redrafts that one measure", async () => {
    mock({ lens: lens({ refine: [item] }) });
    const user = userEvent.setup();
    open(`/modules/m2_baseline/baselines/${BID}`);
    await user.click(await screen.findByRole("button", { name: `${m2Lens.use}: Excess return` }));
    await waitFor(() => expect(calls.find((c) => c.method === "PUT" && c.url.endsWith("/kpis/K1/triage"))?.body).toEqual({ definition: { text: "Return above the benchmark.", mark: "stated" } }));
    await user.click(screen.getByRole("button", { name: `${m2Lens.edit}: Excess return` }));
    await user.clear(screen.getByRole("textbox", { name: m2Lens.editLabel("Excess return") }));
    await user.type(screen.getByRole("textbox", { name: m2Lens.editLabel("Excess return") }), "Our own words");
    await user.click(screen.getByRole("button", { name: m2Lens.save }));
    await waitFor(() => expect(calls.filter((c) => c.url.endsWith("/kpis/K1/triage"))).toHaveLength(2));
    await user.click(screen.getByRole("button", { name: `${m2Lens.tell}: Excess return` }));
    await user.type(screen.getByRole("textbox", { name: m2Lens.tellLabel("Excess return") }), "make it about net returns");
    await user.click(screen.getByRole("button", { name: m2Lens.redraft }));
    await waitFor(() => expect(calls.find((c) => c.url.endsWith("/lens/redraft"))?.body).toEqual({ kpi_id: "K1", instruction: "make it about net returns" }));
  });

  test("Lens asks one question; the answer goes to the field the table uses", async () => {
    const ask = { id: "K1:producer", kpi_id: "K1", kpi_name: "Excess return", field: "producer" as const, role: null, question_id: null, text: "Who produces the data for \"Excess return\"?", draft: null };
    mock({ lens: lens({ refine: [item], asks: [ask, { ...ask, id: "K1:gathered", field: "gathered" as const }], say: { ...lens().say, need: ask.text } }) });
    const user = userEvent.setup();
    open(`/modules/m2_baseline/baselines/${BID}`);
    expect(await screen.findAllByText(ask.text)).not.toHaveLength(0);
    await user.type(screen.getByRole("textbox", { name: m2Lens.answerLabel }), "The fund administrator");
    await user.click(screen.getByRole("button", { name: m2Lens.answer }));
    await waitFor(() => expect(calls.find((c) => c.url.endsWith("/kpis/K1/triage"))?.body).toEqual({ producer: { text: "The fund administrator", mark: "stated" } }));
  });

  test("typing to Lens shows the conversation, and a change reloads the block", async () => {
    mock({ lens: lens() });
    const user = userEvent.setup();
    open(`/modules/m2_baseline/baselines/${BID}`);
    await screen.findByText(m2Lens.noItems);
    await user.type(screen.getByRole("textbox", { name: m2Lens.askLabel }), "make the definition of Excess return shorter{Enter}");
    expect(await screen.findByText("I redrafted it.")).toBeInTheDocument();
    expect(calls.find((c) => c.url.endsWith("/lens/ask"))?.body).toEqual({ question: "make the definition of Excess return shorter" });
    await waitFor(() => expect(calls.filter((c) => c.url === `${BASE}/baselines/${BID}/lens`).length).toBeGreaterThan(1));
  });
});

describe("two agents in one dock", () => {
  test.each(screens)("on %s: Lens is the panel, Nira is one small line inside it", async (s) => {
    mock({ lens: lens() });
    open(`/modules/m2_baseline/${s}/${BID}`);
    expect(await screen.findByRole("complementary", { name: m2Lens.region })).toBeInTheDocument();
    expect(await screen.findByText(/You are on step 1 of 5/)).toBeInTheDocument();
    expect(screen.getAllByRole("complementary")).toHaveLength(1); // one dock, never two panels fighting for space
  });

  test("Nira expands to what is next and answers how-to questions", async () => {
    mock({ lens: lens() });
    const user = userEvent.setup();
    open(`/modules/m2_baseline/baselines/${BID}`);
    await screen.findByText(/Still waiting for an answer from Mei Tan/);
    await user.click(screen.getByRole("button", { name: m2Nira.open }));
    expect(screen.getByText("Name the owners of each measure.")).toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: m2Nira.askLabel }), "How do I name an owner?{Enter}");
    expect(await screen.findByText("Click a row to name its owners.")).toBeInTheDocument();
  });
});

describe("the pre-read step", () => {
  test("lists what helps, tags documents, says we do not have this, and starts the work list", async () => {
    mock({});
    const user = userEvent.setup();
    open(`/modules/m2_baseline/preread/${BID}`);
    expect(await screen.findByText("Business glossary")).toBeInTheDocument();
    expect(screen.getAllByText("Reporting note").length).toBeGreaterThan(0);
    await user.click(screen.getAllByRole("checkbox")[0]!);
    await waitFor(() => expect(calls.find((c) => c.method === "PUT" && c.url.endsWith("/preread/glossary"))?.body).toEqual({ none: true }));
    await user.selectOptions(screen.getByRole("combobox", { name: `${m2Pre.attach}: Process or procedure documents` }), "d2");
    await waitFor(() => expect(calls.find((c) => c.url.endsWith("/preread/procedures"))?.body).toEqual({ docs: ["d1", "d2"] }));
    await user.click(screen.getByRole("button", { name: m2Pre.start }));
    expect(await screen.findByRole("complementary", { name: m2Lens.region })).toBeInTheDocument();
  });

  test("with no documents it says Lens will use the industry text only; with no pack either, that Lens will ask", async () => {
    mock({ pre: pre({ documents: [] }) });
    open(`/modules/m2_baseline/preread/${BID}`);
    expect(await screen.findByText(m2Pre.noDocs)).toBeInTheDocument();
  });

  test("a document that mentions personal data asks the admin: mark it restricted (the Company context route) or say it is not personal", async () => {
    const withPay = pre({ documents: [{ doc_id: "d1", title: "Technical notes", restricted: false, personal_words: ["salary", "bonus"], restrict_path: "/api/agents/lens/docs/d1/visibility" }] });
    mock({ pre: withPay });
    open(`/modules/m2_baseline/preread/${BID}`);
    expect(await screen.findByText(m2Pre.personalNotice(["salary", "bonus"]))).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: m2Pre.markRestricted }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.url === "/api/agents/lens/docs/d1/visibility" && JSON.stringify(c.body) === '{"restricted":true}')).toBe(true));
  });

  test("no documents and no pack: honest empty state", async () => {
    mock({ pre: pre({ documents: [], pack: { available: false, label: "" } }) });
    open(`/modules/m2_baseline/preread/${BID}`);
    expect(await screen.findByText(m2Pre.noDocsNoPack)).toBeInTheDocument();
  });
});

describe("documents waiting for the organiser's decision", () => {
  const waiting = [{ doc_id: "d1", title: "Technical notes", personal_words: ["salary", "bonus"], restrict_path: "/api/agents/lens/docs/d1/visibility" }];

  test("Lens's block counts them, names each with its words, and a decision makes Lens draft the unknown measures again", async () => {
    mock({ lens: lens({ waiting, refine: [{ ...item, definition: prov(null, "unknown") }] }) });
    open(`/modules/m2_baseline/baselines/${BID}`);
    expect(await screen.findByText(m2Pre.waiting(1))).toBeInTheDocument();
    expect(screen.getByText("Technical notes")).toBeInTheDocument();
    expect(screen.getByText(m2Pre.personalNotice(["salary", "bonus"]))).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: m2Pre.notPersonal }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.url.endsWith("/lens/draft") && JSON.stringify(c.body) === '{"kpi_ids":["K1"],"suggestion_ids":[],"retry":true}')).toBe(true));
  });

  test("nothing is shown when no document waits", async () => {
    mock({ lens: lens() });
    open(`/modules/m2_baseline/baselines/${BID}`);
    await screen.findByText(/I read 2 documents/);
    expect(screen.queryByText(/wait for your decision/)).toBeNull();
  });
});
