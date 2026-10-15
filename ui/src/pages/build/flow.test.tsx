import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import DialectPanel from "./DialectPanel";
import FlowIncidentNotes from "./FlowIncidentNote";
import FlowRunNote, { SetAside } from "./FlowRunNote";
import SpanTargetCard from "./SpanTargetCard";
import { flowCopy, setAside } from "./flowCopy";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
type Reply = [number, unknown];
let calls: string[] = [];
function mock(routes: Record<string, Reply>, roles = ["analyst"]) {
  calls = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Katie", company_id: "co", roles });
    calls.push(`${init?.method ?? "GET"} ${url} ${init?.body ?? ""}`.trim());
    const hit = Object.entries(routes).find(([k]) => `${init?.method ?? "GET"} ${url}`.startsWith(k));
    return hit ? json(...hit[1]) : json(404, { message: "no" });
  }));
}
const wrap = (el: ReactElement) => render(<MemoryRouter><ThemeProvider><SessionProvider>{el}</SessionProvider></ThemeProvider></MemoryRouter>);
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

const SVG = "<svg xmlns='http://www.w3.org/2000/svg' width='10' height='10'></svg>";
const TARGET = { draft: { placements: [{ id: "a-b", label: "Gold marts" }], lines: ["One", "Two", "Three", "Four"], by: "Span" }, svg: SVG, empty: null };
const T = "GET /api/company/build/span/target";

describe("Span's target card", () => {
  test("populated: tag, diagram as an image, three why lines", async () => {
    mock({ [T]: [200, TARGET] });
    wrap(<SpanTargetCard intentId="ini-1" />);
    expect(await screen.findByText("Span's suggestion")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /target architecture/ }).getAttribute("src")).toMatch(/^data:image\/svg\+xml/);
    expect(screen.getAllByRole("listitem").map((l) => l.textContent)).toEqual(["One", "Two", "Three"]);
  });
  test("empty, error, refused, loading", async () => {
    mock({ [T]: [200, { draft: null, empty: flowCopy.target.empty }] });
    const a = wrap(<SpanTargetCard intentId="ini-1" />);
    expect(screen.getByRole("status")).toHaveTextContent(flowCopy.target.loading);
    expect(await screen.findByText(flowCopy.target.empty)).toBeInTheDocument();
    a.unmount();
    mock({ [T]: [500, { message: "x" }] });
    const b = wrap(<SpanTargetCard intentId="ini-1" />);
    expect(await screen.findByRole("alert")).toHaveTextContent(flowCopy.target.error);
    b.unmount();
    mock({ [T]: [403, { error: "forbidden", message: "no" }] });
    wrap(<SpanTargetCard intentId="ini-1" />);
    expect(await screen.findByText(flowCopy.target.refused)).toBeInTheDocument();
  });
  test("asking shows the fallback sentence and reloads", async () => {
    mock({ [T]: [200, { draft: null, empty: "none" }], "POST /api/company/build/span/target": [200, { fallback: true, message: "Span could not reach the model." }] });
    wrap(<SpanTargetCard intentId="ini-1" />);
    await userEvent.click(await screen.findByRole("button", { name: flowCopy.target.ask }));
    expect(await screen.findByText("Span could not reach the model.")).toBeInTheDocument();
    expect(calls.some((c) => c.includes('"intent_id":"ini-1"'))).toBe(true);
  });
  test("only the data team is offered the ask button", async () => {
    mock({ [T]: [200, TARGET] }, ["sponsor"]);
    wrap(<SpanTargetCard intentId="ini-1" />);
    await screen.findByText("Span's suggestion");
    expect(screen.queryByRole("button", { name: flowCopy.target.ask })).toBeNull();
  });
});

describe("Flow's run note and the rows set aside", () => {
  const R = "GET /api/company/build/flow/runs/abc";
  test("a count under five is never a figure; none is not a zero", () => {
    expect(flowCopy.rows(3)).toBe("Fewer than five rows");
    expect(flowCopy.rows(0)).toBe("No rows");
    expect(flowCopy.rows(undefined)).toBe("Not available yet");
    expect(setAside({ rule: "k12:fund id must not be empty", field: "fund_id", count: 12 })).toBe("12 rows set aside for fund id must not be empty");
    expect(setAside({ rule: "k12:fund id must not be empty", field: "fund_id", count: 2 })).toBe("Fewer than five rows set aside for fund id must not be empty");
  });
  test("set aside lines come from the run record, nothing when none", () => {
    const a = wrap(<SetAside held={[{ rule: "k12:fund id must not be empty", field: "fund_id", count: 12 }]} />);
    expect(screen.getByText("12 rows set aside for fund id must not be empty")).toBeInTheDocument();
    a.unmount();
    const { container } = wrap(<SetAside held={[]} />);
    expect(container.querySelector("ul")).toBeNull();
  });
  test("a masked set aside line names no check and keeps the count", () => {
    wrap(<SetAside held={[{ rule: "", field: "", count: 3, masked: true }, { rule: "", field: "", count: 12, masked: true }]} />);
    expect(screen.getByText("Fewer than five rows set aside for a check you cannot see")).toBeInTheDocument();
    expect(screen.getByText("12 rows set aside for a check you cannot see")).toBeInTheDocument();
  });
  test("populated with the fallback sentence, then asked again", async () => {
    mock({ [R]: [200, { lines: ["bank failed."], text: null, fallback: true, sentence: "Flow could not reach the model. These lines come from the run log." }], "POST /api/company/build/flow/runs/abc/explain": [200, { lines: ["again."] }] });
    wrap(<FlowRunNote runId="abc" title="Bank" canAsk onClose={() => undefined} />);
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(await screen.findByText("bank failed.")).toBeInTheDocument();
    expect(screen.getByText(/These lines come from the run log/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: flowCopy.run.again }));
    expect(await screen.findByText("again.")).toBeInTheDocument();
  });
  test("empty, error and refused", async () => {
    mock({ [R]: [200, { lines: [] }] });
    const a = wrap(<FlowRunNote runId="abc" title="Bank" canAsk={false} onClose={() => undefined} />);
    expect(await screen.findByText(flowCopy.run.empty)).toBeInTheDocument();
    a.unmount();
    mock({ [R]: [500, {}] });
    const b = wrap(<FlowRunNote runId="abc" title="Bank" canAsk={false} onClose={() => undefined} />);
    expect(await screen.findByRole("alert")).toHaveTextContent(flowCopy.run.error);
    b.unmount();
    mock({ [R]: [403, { error: "forbidden", message: "no" }] });
    wrap(<FlowRunNote runId="abc" title="Bank" canAsk={false} onClose={() => undefined} />);
    expect(await screen.findByText(flowCopy.run.refused)).toBeInTheDocument();
  });
});

describe("Flow's incident notes", () => {
  const I = "GET /api/company/build/flow/incidents";
  const item = (can: boolean) => ({ incidents: [{ alert_id: "bank:failed", fallback: false, note: { id: "P-0001", title: "Flow's note on the bank alert", what: "Bank failed its checks.", why: "Rows were empty.", next_step: "Ask for a new file.", to: "Katie", can_decide: can } }] });
  test("acknowledge with the note posts the accept", async () => {
    const done = vi.fn();
    mock({ [I]: [200, item(true)], "POST /api/company/build/proposals/P-0001/accept": [200, {}] });
    wrap(<FlowIncidentNotes onDone={done} />);
    await userEvent.click(await screen.findByRole("button", { name: flowCopy.incident.ack }));
    await waitFor(() => expect(done).toHaveBeenCalled());
  });
  test("edit sends the person's own words to the alert", async () => {
    mock({ [I]: [200, item(true)], "POST /api/company/build/alerts/bank%3Afailed/ack": [200, {}] });
    wrap(<FlowIncidentNotes onDone={() => undefined} />);
    await userEvent.click(await screen.findByRole("button", { name: flowCopy.incident.edit }));
    const box = screen.getByLabelText("Your note");
    await userEvent.clear(box);
    await userEvent.type(box, "Chasing the provider");
    await userEvent.click(screen.getByRole("button", { name: flowCopy.incident.save }));
    await waitFor(() => expect(calls.some((c) => c.includes("/alerts/bank%3Afailed/ack") && c.includes("Chasing the provider"))).toBe(true));
  });
  test("a person who may not decide sees who it waits for; empty, error, refused", async () => {
    mock({ [I]: [200, item(false)] });
    const a = wrap(<FlowIncidentNotes onDone={() => undefined} />);
    expect(await screen.findByText(flowCopy.incident.waits("Katie"))).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: flowCopy.incident.ack })).toBeNull();
    a.unmount();
    mock({ [I]: [200, { incidents: [] }] });
    const b = wrap(<FlowIncidentNotes onDone={() => undefined} />);
    expect(await screen.findByText(flowCopy.incident.empty)).toBeInTheDocument();
    b.unmount();
    mock({ [I]: [500, {}] });
    const c = wrap(<FlowIncidentNotes onDone={() => undefined} />);
    expect(await screen.findByRole("alert")).toHaveTextContent(flowCopy.incident.error);
    c.unmount();
    mock({ [I]: [403, { error: "forbidden", message: "no" }] });
    wrap(<FlowIncidentNotes onDone={() => undefined} />);
    expect(await screen.findByText(flowCopy.incident.refused)).toBeInTheDocument();
  });
});

describe("SQL for your warehouse", () => {
  const D = "GET /api/company/build/dialect";
  test("nothing is shown when no target is stated, or when refused", async () => {
    mock({ [D]: [200, { state: "none", message: "none" }] });
    const a = wrap(<DialectPanel />);
    await waitFor(() => expect(screen.queryByRole("status")).toBeNull());
    expect(screen.queryByText(flowCopy.dialect.title)).toBeNull();
    a.unmount();
    mock({ [D]: [403, { error: "forbidden", message: "no" }] });
    wrap(<DialectPanel />);
    await waitFor(() => expect(screen.queryByText(flowCopy.dialect.title)).toBeNull());
  });
  test("ready: statements and the download; error", async () => {
    mock({ [D]: [200, { state: "ready", message: "A draft for your warehouse.", statements: [{ name: "silver_bank", sql: "select 1" }] }] });
    const a = wrap(<DialectPanel />);
    expect(await screen.findByText("A draft for your warehouse.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: flowCopy.dialect.download })).toHaveAttribute("href", "/api/company/build/dialect/download");
    a.unmount();
    mock({ [D]: [500, {}] });
    wrap(<DialectPanel />);
    expect(await screen.findByRole("alert")).toHaveTextContent(flowCopy.dialect.error);
  });
  test("unsupported target shows the sentence and no download", async () => {
    mock({ [D]: [200, { state: "unsupported", message: "Not available yet: Span and Flow cannot write SQL for X yet.", statements: [] }] });
    wrap(<DialectPanel />);
    expect(await screen.findByText(/Not available yet: Span and Flow/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: flowCopy.dialect.download })).toBeNull();
  });
});

describe("copy rules", () => {
  test("no vendor names, no em dashes in screen copy", () => {
    const all = JSON.stringify(flowCopy, (_k, v) => (typeof v === "function" ? v(5) : v));
    expect(all).not.toMatch(/duckdb|archify|claude|anthropic|openai|—/i);
  });
});
