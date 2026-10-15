import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { num, signed } from "../b9verify/format";
import type { BuilderView, Connection, Round, Variance } from "./api";
import BuilderPanel from "./BuilderPanel";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());

const conn = (o: Partial<Connection>): Connection => ({ code: "a", name: "Fund administrator positions", kind: "structured", how: "sftp", how_words: "SFTP", status: "connected", detail: "Reused the connection already set up. 1 file waiting.",
  owner: null, seen: {}, mismatches: [], from_intent: true, ...o });
const VAR: Variance = {
  benchmark: "September report as issued.pdf", at: "2026-10-11T08:00:00Z", headline: "1 unexplained variance", summary: { matches: 1, explained: 1, unexplained: 1 }, unmatched: [{ label: "Pages", value: "4", unit: "money" }],
  lines: [{ figure: "Total holdings, 30 Sep", run: "57780000", report: "57600000", unit: "money", diff: "180000", status: "explained", evidence: [{ text: "Fund A amended 7 Oct" }] }],
  legs: [{ figure: "Global equity index plus a spread", run: "28.0000", report: "30", unit: "pct", diff: "-2.0000", status: "unexplained", evidence: [] }],
};
const ROUND: Round = { pack_version: 1, started_at: "2026-10-11T08:00:00Z", connections: [conn({})], state: "ran", outcome: null, variance: null,
  run: { status: "ok", pack_version: 1, error: null, started: "2026-10-11T08:00:00Z", tables: { bronze: 1, silver: 0, gold: 2 }, gold_rows: 5940, checks: { passed: 3, total: 3 }, steps: [{ label: "Holdings", layer: "gold", rows: 462, status: "ok" }] } };
const BASE: BuilderView = {
  project_id: "prj-1", waiting: null, newer: null, round: ROUND, rounds: [], benchmark: null, signed_reports: [{ id: "rv1", name: "Monthly report, 2026-08-31", issued_at: "2026-09-03" }], needs: [],
  thread: [{ who: "Span the builder", at: "2026-10-11T08:00:00Z", text: "I took design pack version 1 as it was approved.", evidence: [] }],
  pack: { version: 1, state: "approved", approved_by: "Anita Rao", approved_at: null, sources: 1, tables: { bronze: 1, silver: 0, gold: 2 }, schedule: { freq: "daily", at: "06:00", day: null }, change_from: null, sql: [{ table: "gold_x", label: "Holdings", sql: "select 1" }] },
  can: { start: false, recheck: false, benchmark: true, go_live: true, send_back: false, settle: true, issue: false },
};

function mock(first: BuilderView, sent: string[], next?: BuilderView) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method && init.method !== "GET") { sent.push(`${init.method} ${url} ${String(init.body ?? "")}`); return json(200, next ?? first); }
    return json(200, first);
  }));
}
const view = () => render(<MemoryRouter><BuilderPanel pid="prj-1" /></MemoryRouter>);

describe("number and date words", () => {
  it("groups figures as text and signs differences", () => {
    expect(num("10500000")).toBe("10,500,000");
    expect(num("4.1700")).toBe("4.17");
    expect(num("28.0000", 2)).toBe("28.00");
    expect(num(null)).toBe("Not available yet");
    expect(signed("180000")).toBe("+180,000");
    expect(signed("-2.0000", 2)).toBe("-2.00");
  });
});

describe("BuilderPanel", () => {
  it("waits for an approved pack and says so", async () => {
    mock({ ...BASE, round: null, pack: null, waiting: "The design pack is not approved yet. The builder starts when it is.", thread: [], can: { ...BASE.can, benchmark: false } }, []);
    view();
    expect(await screen.findByText(/design pack is not approved yet/)).toBeInTheDocument();
  });

  it("starts by itself when the pack is approved, with no click", async () => {
    const sent: string[] = [];
    mock({ ...BASE, round: null, thread: [], can: { ...BASE.can, start: true } }, sent, BASE);
    view();
    expect(await screen.findByText("Connecting the 1 source")).toBeInTheDocument();
    expect(sent).toEqual(["POST /api/v1/build/p/prj-1/builder/start {}"]);
  });

  it("shows connections, the run and asks for a benchmark; a signed report can be picked", async () => {
    const sent: string[] = [];
    mock(BASE, sent);
    view();
    expect(await screen.findByText("Fund administrator positions")).toBeInTheDocument();
    expect(screen.getByText("Connected")).toBeInTheDocument();
    expect(screen.getByText("5,940")).toBeInTheDocument();
    expect(screen.getByText("3 of 3")).toBeInTheDocument();
    expect(screen.getByText(/Do you have last month/)).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Or pick a signed report"), "rv1");
    await userEvent.click(screen.getByRole("button", { name: "Check against it" }));
    await waitFor(() => expect(sent).toEqual(['POST /api/v1/build/p/prj-1/builder/benchmark {"report_version_id":"rv1"}']));
  });

  it("raises a failed connection to the right person and a mismatch once with the intent value beside it", async () => {
    const sent: string[] = [];
    const bad = conn({ code: "t", name: "Trading export", status: "failed", detail: "That address is not allowed." });
    const mm = conn({ code: "m", name: "Manager statements", status: "mismatch", detail: "1 file landed.", mismatches: [{ field: "file", pack: "stmt_*.pdf", intent: "statements.pdf", seen: "stmt_sep.pdf" }] });
    mock({ ...BASE, round: { ...ROUND, state: "blocked", run: null, connections: [conn({}), bad, mm] }, needs: [{ id: "n", kind: "connection_failed", source: "t", name: "Trading export", to: ["Anita Rao"], text: "x", at: "" }],
      can: { ...BASE.can, recheck: true } }, sent);
    view();
    expect(await screen.findByText(/Raised to Anita Rao in Action/)).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
    const box = screen.getByRole("group", { name: "Manager statements: file differs" });
    expect(within(box).getByText("statements.pdf")).toBeInTheDocument(); // the intent's value
    expect(within(box).getByText("stmt_*.pdf")).toBeInTheDocument();
    await userEvent.click(within(box).getByRole("button", { name: "Use statements.pdf" }));
    await waitFor(() => expect(sent).toEqual(['POST /api/v1/build/p/prj-1/builder/settle {"source":"m","field":"file","value":"statements.pdf"}']));
    expect(screen.getByRole("button", { name: "Check again" })).toBeInTheDocument();
  });

  it("lets the data engineer mark a source with no sample as not needed, only after a confirm", async () => {
    const sent: string[] = [];
    const ghost = conn({ code: "g", name: "Closing cash figure", status: "needs_sample", detail: "No sample file has arrived for this source yet." });
    mock({ ...BASE, round: { ...ROUND, state: "blocked", run: null, connections: [conn({}), ghost] }, can: { ...BASE.can, not_needed: true } }, sent);
    vi.stubGlobal("confirm", vi.fn(() => true));
    view();
    await userEvent.click(await screen.findByRole("button", { name: "Mark as not needed" }));
    await waitFor(() => expect(sent).toEqual(['POST /api/v1/build/p/prj-1/builder/not-needed {"source":"g"}']));
  });

  it("shows the variance line by line, explained with its evidence, and sends it back or goes live anyway", async () => {
    const sent: string[] = [];
    const r = { ...ROUND, state: "checked" as const, variance: VAR };
    mock({ ...BASE, round: r, benchmark: { kind: "upload", name: VAR.benchmark, by: "Leo Park", at: "", figures: 9 }, can: { ...BASE.can, send_back: true } }, sent);
    view();
    const row = (await screen.findByText("Total holdings, 30 Sep")).closest("tr")!;
    expect(within(row).getByText("57,780,000")).toBeInTheDocument();
    expect(within(row).getByText("+180,000")).toBeInTheDocument();
    expect(within(row).getByText("Explained")).toBeInTheDocument();
    expect(within(row).getByText("Fund A amended 7 Oct")).toBeInTheDocument();
    const leg = screen.getByText("Global equity index plus a spread").closest("tr")!;
    expect(leg).toHaveAttribute("data-status", "unexplained");
    expect(within(leg).getByText("28.00%")).toBeInTheDocument();
    expect(screen.queryByText(/IDX:/)).toBeNull();
    expect(screen.getByText(/no figure for it: Pages/)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/Note to the architect/), "Check the sleeve");
    await userEvent.click(screen.getByRole("button", { name: "Send back to the architect" }));
    await waitFor(() => expect(sent).toEqual(['POST /api/v1/build/p/prj-1/builder/send-back {"note":"Check the sleeve"}']));
    await userEvent.click(screen.getByRole("button", { name: "Go live anyway" }));
    await waitFor(() => expect(sent[1]).toBe('POST /api/v1/build/p/prj-1/builder/go-live {"accept_variance":true}'));
  });

  it("after pack version 2 the variance is cleared and Go live uses the pack schedule", async () => {
    const sent: string[] = [];
    const clear: Variance = { ...VAR, headline: "Matches, with explained differences", summary: { matches: 2, explained: 1, unexplained: 0 }, legs: [{ ...VAR.legs[0]!, run: "30.0000", diff: "0.0000", status: "matches" }] };
    mock({ ...BASE, round: { ...ROUND, pack_version: 2, state: "checked", variance: clear }, pack: { ...BASE.pack!, version: 2, change_from: { version: 1, changes: [] } },
      thread: [...BASE.thread, { who: "Span the architect", at: "2026-10-11T09:00:00Z", text: "Pack version 2 issued.", evidence: [{ text: "Holdings: sleeve is 30" }] }] }, sent);
    view();
    expect(await screen.findByText("Variance cleared")).toBeInTheDocument();
    expect(screen.getByText(/Span the architect · 11 Oct 2026/)).toBeInTheDocument();
    expect(screen.getByText(/Going live uses the schedule in the pack: every day at 06:00/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Go live" }));
    await waitFor(() => expect(sent).toEqual(["POST /api/v1/build/p/prj-1/builder/go-live {\"accept_variance\":false}"]));
  });

  it("FIX1: a pack with no sources never says Connecting the 0 sources, and a monthly pack's day is said as the pack says it", async () => {
    const clear: Variance = { ...VAR, summary: { matches: 2, explained: 1, unexplained: 0 }, legs: [] };
    mock({ ...BASE, round: { ...ROUND, connections: [], state: "checked", variance: clear }, pack: { ...BASE.pack!, sources: 0, schedule: { freq: "monthly", at: "06:00", day: "5th business day" } } }, []);
    view();
    expect(await screen.findByText("5,940")).toBeInTheDocument();
    expect(screen.queryByText(/Connecting the 0/)).toBeNull();
    expect(screen.getByText(/every month at 06:00, by the 5th business day/)).toBeInTheDocument();
  });

  it("says plainly when the builder cannot be opened", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(404, { error: "not_found", message: "Not found." })));
    view();
    expect(await screen.findByText(/builder is not available right now/)).toBeInTheDocument();
  });
});
