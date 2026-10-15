import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import DesignDocPanel from "./DesignDocPanel";
import SpanModelPanel from "./SpanModelPanel";
import SuggestionsPanel from "./SuggestionsPanel";
import { plain, sc, SECTIONS } from "./spanCopy";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const P = {
  id: "P-0004", kind: "model_change", by_agent: "Span", to: "Marcus Todd", to_role: "data owner", title: "Retain Manager Attribute History",
  what: "Change dim_manager from a Type 1 to a Type 2 Slowly Changing Dimension.", why: "The measure K15, manager performance, relies on dim_manager.",
  technique: "Slowly changing dimension", evidence: { counts: [], fields: ["Fund / Manager"] },
  impact: { contracts: ["performance_workbook"], marts: ["gold.k15.manager_performance"], dashboards: [] },
  alternatives: [{ option: "keep type 1", why_not: "loses the history." }], effort: "medium", state: "proposed", thread: [], can_decide: true, outside_note: null,
};
const DOC = {
  doc: { version: 2, state: "draft", signed_by: [], sections: { purpose: [{ text: "N-0001: Valuation chase protocol", mark: "guessed" }], risks: [{ text: "Late files", mark: "stated" }] } },
  diagrams: { target: "<svg viewBox='0 0 10 10'><rect width='5' height='5'/></svg>" }, fallback: false, message: null, empty: null, can_edit: true,
};
type Reply = [number, unknown];
function mock(roles: string[], routes: Record<string, Reply>, sent: string[] = []) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Marcus", company_id: "co", roles });
    if (init?.method && init.method !== "GET") sent.push(`${init.method} ${url} ${String(init.body ?? "")}`);
    const write = !!init?.method && init.method !== "GET";
    const r = write ? routes[`${init?.method} ${url}`] ?? [200, {}] : Object.entries(routes).find(([k]) => !/^(POST|PUT) /.test(k) && url.startsWith(k))?.[1];
    return r ? json(r[0], r[1]) : json(404, { message: "no" });
  }));
  return sent;
}
const wrap = (el: ReactElement) => render(<MemoryRouter><ThemeProvider><SessionProvider>{el}</SessionProvider></ThemeProvider></MemoryRouter>);
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

const MD = "/api/company/build/span/model-draft";
const PR = "/api/company/build/proposals";
const DS = "/api/company/build/design";

describe("Span's model draft", () => {
  test("loading, then the empty sentence", async () => {
    mock(["analyst"], { [MD]: [200, { state: "none", message: sc.modelEmpty, fallback: false }] });
    wrap(<SpanModelPanel />);
    expect(screen.getByText(sc.loading)).toBeInTheDocument();
    expect(await screen.findByText(sc.modelEmpty)).toBeInTheDocument();
  });
  test("error offers a retry, refused says who may ask", async () => {
    mock(["analyst"], { [MD]: [500, {}] });
    const { unmount } = wrap(<SpanModelPanel />);
    expect(await screen.findByRole("button", { name: sc.retry })).toBeInTheDocument();
    unmount();
    mock(["analyst"], { [MD]: [403, { error: "forbidden" }] });
    wrap(<SpanModelPanel />);
    expect(await screen.findByText(sc.refused)).toBeInTheDocument();
  });
  test("a fallback draft says so, a failed one gives its reasons in plain words", async () => {
    mock(["analyst"], { [MD]: [200, { state: "fallback", fallback: true, message: sc.fallback }] });
    const { unmount } = wrap(<SpanModelPanel />);
    expect(await screen.findByText(sc.fallback)).toBeInTheDocument();
    unmount();
    mock(["analyst"], { [MD]: [200, { state: "failed", message: "Span could not make this build.", errors: ["fact_valuation: grain fund_id is not unique"] }] });
    wrap(<SpanModelPanel />);
    expect(await screen.findByText("Span could not make this build.")).toBeInTheDocument();
    expect(screen.getByText("valuation: grain fund id is not unique")).toBeInTheDocument();
  });
  test("a ready draft can be filed by the architect and says where it went", async () => {
    const sent = mock(["analyst"], {
      [MD]: [200, { state: "ready", id: "D1", rounds: 2, message: "Span's suggestion: the model builds in the sandbox.", counts: [{ label: "fact_valuation", value: 1180 }, { label: "dim_fund", text: "fewer than five" }] }],
      [`POST ${MD}/D1/file`]: [200, { state: "filed", id: "D1", filed: { by: "Marcus", at: "x", version: 3, skipped: [] } }],
    });
    wrap(<SpanModelPanel />);
    expect(await screen.findByText("valuation: 1180")).toBeInTheDocument();
    expect(screen.getByText("fund: fewer than five")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: sc.file }));
    expect(await screen.findByText(sc.filed(3))).toBeInTheDocument();
    expect(sent).toEqual([`POST ${MD}/D1/file `]);
  });
  test("asking an empty company shows the server's plain refusal", async () => {
    mock(["analyst"], { [MD]: [200, { state: "none" }], [`POST ${MD}`]: [409, { error: "nothing_to_draft", message: "Span needs a signed blueprint and at least one landed source first." }] });
    wrap(<SpanModelPanel />);
    await userEvent.click(await screen.findByRole("button", { name: sc.askModel }));
    expect(await screen.findByText(/Span needs a signed blueprint/)).toBeInTheDocument();
  });
  test("revising asks for a note first and sends it", async () => {
    const sent = mock(["analyst"], { [MD]: [200, { state: "failed", message: "Span could not make this build." }], [`POST ${MD}`]: [202, { state: "drafting" }] });
    wrap(<SpanModelPanel />);
    await userEvent.click(await screen.findByRole("button", { name: sc.askRevise }));
    await userEvent.type(screen.getByLabelText(sc.reviseLabel), "Keep history on funds");
    await userEvent.click(screen.getByRole("button", { name: sc.send }));
    expect(await screen.findByText(sc.drafting)).toBeInTheDocument();
    expect(sent).toEqual([`POST ${MD} {"changes":"Keep history on funds"}`]);
  });
  test("a person with no say sees no buttons", async () => {
    mock(["participant"], { [MD]: [200, { state: "ready", id: "D1" }] });
    wrap(<SpanModelPanel />);
    await screen.findByText(sc.modelTitle);
    expect(screen.queryByRole("button", { name: sc.file })).toBeNull();
  });
});

describe("Span's suggestions", () => {
  test("empty, error and refused", async () => {
    mock(["analyst"], { [PR]: [200, { proposals: [], empty: sc.sugEmpty }] });
    const a = wrap(<SuggestionsPanel />);
    expect(await screen.findByText(sc.sugEmpty)).toBeInTheDocument();
    a.unmount();
    mock(["analyst"], { [PR]: [500, {}] });
    const b = wrap(<SuggestionsPanel />);
    expect(await screen.findByRole("button", { name: sc.retry })).toBeInTheDocument();
    b.unmount();
    mock(["analyst"], { [PR]: [403, { error: "forbidden" }] });
    wrap(<SuggestionsPanel />);
    expect(await screen.findByText(sc.refused)).toBeInTheDocument();
  });
  test("a card names the addressee, reads in plain words and is labelled a suggestion", async () => {
    mock(["analyst"], { [PR]: [200, { proposals: [P, { ...P, id: "P-0005", title: "Retain Vehicle Attribute History", to: "Harvey Rowley", can_decide: false }], empty: null }] });
    wrap(<SuggestionsPanel />);
    expect(await screen.findByText("For Marcus Todd, the data owner, to decide")).toBeInTheDocument();
    expect(screen.getByText("Harvey Rowley decides this.")).toBeInTheDocument();
    expect(screen.getAllByText(sc.tag).length).toBeGreaterThanOrEqual(2);
    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/P-\d{4}|K15|dim_|gold\.|_workbook/);
    expect(text).toContain("manager performance");
    expect(screen.getAllByRole("button", { name: sc.accept })).toHaveLength(1); // only the addressee decides
  });
  test("decline stays disabled until a reason is typed, then sends it", async () => {
    const sent = mock(["analyst"], { [PR]: [200, { proposals: [P], empty: null }], [`POST ${PR}/P-0004/decline`]: [200, { ...P, state: "declined", can_decide: false }] });
    wrap(<SuggestionsPanel />);
    await userEvent.click(await screen.findByRole("button", { name: sc.decline }));
    const send = screen.getByRole("button", { name: sc.send });
    expect(send).toBeDisabled();
    await userEvent.type(screen.getByLabelText(sc.reasonLabel), "Not now");
    expect(send).toBeEnabled();
    await userEvent.click(send);
    expect(await screen.findByText(sc.declined)).toBeInTheDocument();
    expect(sent).toEqual([`POST ${PR}/P-0004/decline {"reason":"Not now"}`]);
  });
  test("accept sends nothing but the accept, and a refusal reads as one sentence", async () => {
    mock(["analyst"], { [PR]: [200, { proposals: [P], empty: null }], [`POST ${PR}/P-0004/accept`]: [409, { error: "stale", message: "The model changed since this was suggested. Ask Span to review it again." }] });
    wrap(<SuggestionsPanel />);
    await userEvent.click(await screen.findByRole("button", { name: sc.accept }));
    expect(await screen.findByText(/The model changed since this was suggested/)).toBeInTheDocument();
  });
  test("a review that falls back says so", async () => {
    mock(["analyst"], { [PR]: [200, { proposals: [], empty: null }], "POST /api/company/build/span/review": [200, { proposals: [], fallback: true, message: sc.reviewFallback }] });
    wrap(<SuggestionsPanel />);
    await userEvent.click(await screen.findByRole("button", { name: sc.review }));
    expect(await screen.findByText(sc.reviewFallback)).toBeInTheDocument();
  });
});

describe("Design document", () => {
  test("empty, error and refused", async () => {
    mock(["analyst"], { [DS]: [200, { doc: null, diagrams: {}, empty: sc.designEmpty, can_edit: false }] });
    const a = wrap(<DesignDocPanel />);
    expect(await screen.findByText(sc.designEmpty)).toBeInTheDocument();
    a.unmount();
    mock(["analyst"], { [DS]: [500, {}] });
    const b = wrap(<DesignDocPanel />);
    expect(await screen.findByRole("button", { name: sc.retry })).toBeInTheDocument();
    b.unmount();
    mock(["analyst"], { [DS]: [403, { error: "forbidden" }] });
    wrap(<DesignDocPanel />);
    expect(await screen.findByText(sc.refused)).toBeInTheDocument();
  });
  test("populated: sections in template order, the diagram in a frame with no permissions, downloads", async () => {
    mock(["analyst"], { [DS]: [200, DOC] });
    wrap(<DesignDocPanel />);
    const frame = await screen.findByTitle(/Diagram of the architecture: Target/);
    expect(frame.getAttribute("sandbox")).toBe("");
    expect(frame.getAttribute("srcdoc")).toContain("<svg");
    expect(screen.getByText("Valuation chase protocol")).toBeInTheDocument(); // the id in front of it is not shown
    expect(screen.getByText(sc.draftBanner)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: sc.download })).toHaveAttribute("href", "/api/company/build/design/download");
    expect(screen.getByRole("link", { name: sc.downloadSpec })).toHaveAttribute("href", "/api/company/build/design/spec?kind=target");
    const heads = screen.getAllByText((_, el) => el?.tagName === "SUMMARY").map((e) => e.textContent);
    expect(heads).toEqual(SECTIONS.filter(([id]) => ["purpose", "risks"].includes(id)).map(([, t]) => t));
    await userEvent.click(screen.getByRole("button", { name: sc.tabs.current }));
    expect(screen.getByText(/The diagram could not be drawn|Not available yet/)).toBeInTheDocument();
  });
  test("the spec tools are the architect's; a fallback draft and a signed one say so", async () => {
    mock(["participant"], { [DS]: [200, { ...DOC, can_edit: false, fallback: true, message: "Span could not reach the model. Sections below are filled from the records only." }] });
    const a = wrap(<DesignDocPanel />);
    expect(await screen.findByText(/filled from the records only/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: sc.uploadSpec })).toBeNull();
    a.unmount();
    mock(["analyst"], { [DS]: [200, { ...DOC, doc: { ...DOC.doc, state: "signed", signed_by: [{ name: "Grace", at: "2026-10-07T09:00:00Z" }] } }] });
    wrap(<DesignDocPanel />);
    expect(await screen.findByText("Signed by Grace on 7 October 2026")).toBeInTheDocument();
  });
  test("a bad upload says why in one sentence; a refused spec shows the server's words", async () => {
    mock(["analyst"], { [DS]: [200, DOC], "PUT /api/company/build/design/spec": [422, { error: "invalid_spec", message: "The diagram could not be drawn: every component needs a position and a size." }] });
    wrap(<DesignDocPanel />);
    await screen.findByTitle(/Diagram of the architecture/);
    const input = screen.getByLabelText(sc.uploadSpec, { selector: "input" });
    await userEvent.upload(input, new File(["not json"], "spec.json", { type: "application/json" }));
    expect(await screen.findByText(sc.specBad)).toBeInTheDocument();
    await userEvent.upload(input, new File(["{}"], "spec.json", { type: "application/json" }));
    expect(await screen.findByText(/every component needs a position/)).toBeInTheDocument();
  });
});

describe("Screen copy", () => {
  test("no vendor, tool or format words and no em dashes in the copy", () => {
    const all = JSON.stringify([sc, SECTIONS]);
    expect(all).not.toMatch(/Archify|DuckDB|OpenAI|Anthropic|Claude|GPT|Gemini|sqlglot|JSON schema/i);
    expect(all).not.toContain("—");
  });
  test("plain() drops ids, codes and table prefixes", () => {
    expect(plain("dim_vehicle")).toBe("vehicle");
    expect(plain("gold.k05.unfunded_commitments")).toBe("unfunded commitments");
    expect(plain("The measure K05, unfunded commitments, relies on dim_vehicle.")).toBe("The measure unfunded commitments, relies on vehicle.");
  });
});
