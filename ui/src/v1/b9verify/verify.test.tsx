import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import type { Comparison, VerifyView } from "./api";
import VerifyPanel from "./VerifyPanel";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());

const row = (component: string, signed: string, used: string, gap: string, differs: boolean) =>
  ({ component, return_pct: "3.5002", signed_weight_pct: signed, used_weight_pct: used, gap_pts: gap, differs });
const CMP: Comparison = {
  month: "2026-09", table: "gold", benchmark_name: "Office blend", signed_version: 1, portfolio_pct: "4.1667", benchmark_run_pct: "2.8562", benchmark_signed_pct: "2.7072",
  difference_run_pts: "1.3105", difference_signed_pts: "1.4595", same: false, problems: [],
  rows: [row("Equity index", "42.0000", "36.0000", "-6.0000", true), row("Bond index", "28.0000", "28.0000", "0.0000", false)],
};
const BASE: VerifyView = {
  project_id: "prj-1", owner: "Mei Chen", matched: 2, total: 2, verified: null, review: null, comparison: null, comparison_error: null,
  figures: [
    { figure: "Market value total", source: "30", run: "30", traced_to: "Positions.xlsx, batch sep", check: "Match", trail: null },
    { figure: "Total: rows", source: null, run: "1", traced_to: "Pipeline run on the copy", check: "Not compared", trail: null },
  ],
  can: { verify: true, send: false, flag: false, accept: false, fix: false },
};

function mock(first: VerifyView, sent: string[], next?: VerifyView) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method && init.method !== "GET") { sent.push(`${init.method} ${url} ${String(init.body ?? "")}`); return json(200, next ?? first); }
    return json(200, first);
  }));
}
const view = () => render(<MemoryRouter><VerifyPanel pid="prj-1" /></MemoryRouter>);

describe("VerifyPanel", () => {
  it("shows the figures with their check and marks the run verified", async () => {
    const sent: string[] = [];
    mock(BASE, sent, { ...BASE, verified: { by: "Leo Park", at: "2026-10-11T08:00:00+00:00", matched: 2, total: 2, run_id: "r1" }, can: { ...BASE.can, send: true } });
    view();
    expect(await screen.findByText("Market value total")).toBeInTheDocument();
    expect(screen.getByText("Match")).toBeInTheDocument();
    expect(screen.getByText(/does not confirm the business definitions/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Mark this run as verified" }));
    expect(await screen.findByText(/Leo Park, data engineer, verified on/)).toBeInTheDocument();
    expect(sent).toEqual(["POST /api/v1/build/p/prj-1/verify/mark {}"]);
    expect(screen.getByRole("heading", { name: "Send for business review" })).toBeInTheDocument();
  });

  it("highlights the differing weights, blocks accept and sends the issue back", async () => {
    const sent: string[] = [];
    const rv = { state: "requested" as const, owner: "Mei Chen", requested_by: "Leo Park", requested_at: "2026-10-11T08:00:00+00:00", portfolio: "P", code: "B", month: "2026-09", message: "", issues: [], case_id: null, first: null, accepted_by: null, accepted_at: null };
    mock({ ...BASE, review: rv, comparison: CMP, can: { verify: false, send: false, flag: true, accept: true, fix: false } }, sent);
    view();
    const cell = await screen.findByText("-6.00 pts");
    expect(cell.closest("tr")).toHaveAttribute("data-differs", "true");
    expect(screen.getByText("signed definition gives 2.71%")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Accept the numbers" })).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Add to your comment"), "Sleeve is 40 percent");
    await userEvent.click(screen.getByRole("button", { name: "Send back with this issue" }));
    await waitFor(() => expect(sent).toEqual(['POST /api/v1/build/p/prj-1/verify/flag {"text":"Sleeve is 40 percent"}']));
  });

  it("lets the owner accept once the mix is the signed one, and says who and when", async () => {
    const sent: string[] = [];
    const rv = { state: "requested" as const, owner: "Mei Chen", requested_by: "Leo Park", requested_at: "2026-10-11T08:00:00+00:00", portfolio: "P", code: "B", month: "2026-09", message: "", issues: [], case_id: null, first: null, accepted_by: null, accepted_at: null };
    const ok = { ...CMP, same: true, rows: CMP.rows.map((r) => ({ ...r, differs: false, gap_pts: "0.0000" })) };
    mock({ ...BASE, review: rv, comparison: ok, can: { verify: false, send: false, flag: true, accept: true, fix: false } }, sent,
      { ...BASE, review: { ...rv, state: "accepted", accepted_by: "Mei Chen", accepted_at: "2026-10-11T09:00:00+00:00" }, comparison: ok });
    view();
    await userEvent.click(await screen.findByRole("button", { name: "Accept the numbers" }));
    expect(await screen.findByText(/Mei Chen, business owner, accepted the numbers on/)).toBeInTheDocument();
    expect(sent).toEqual(["POST /api/v1/build/p/prj-1/verify/accept {}"]);
  });

  it("says plainly when the call fails", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(403, { detail: { error: "not_allowed", message: "You do not have access to this." } })));
    view();
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});

describe("VerifyPanel W3", () => {
  it("opens the send form already filled in, and the review links the signed benchmark and carries Lumen's note", async () => {
    const sg = { portfolio: "EG-LIQUID", code: "BLEND", month: "2026-09", message: "Hi Mei, here is the outcome." };
    mock({ ...BASE, verified: { by: "Leo Park", at: "2026-10-11T08:00:00+00:00", matched: 2, total: 2, run_id: "r1" }, can: { ...BASE.can, send: true }, suggest: sg }, []);
    const { unmount } = view();
    expect(await screen.findByLabelText("Portfolio")).toHaveValue("EG-LIQUID");
    expect(screen.getByLabelText("Benchmark code")).toHaveValue("BLEND");
    expect(screen.getByLabelText(/Month/)).toHaveValue("2026-09");
    expect(screen.getByLabelText("Message")).toHaveValue("Hi Mei, here is the outcome.");
    expect(screen.getByText(/Verification: 2 of 2 figures match/)).toBeInTheDocument();
    unmount();
    const rv = { state: "requested" as const, owner: "Mei Chen", requested_by: "Leo Park", requested_at: "2026-10-11T08:00:00+00:00", portfolio: "P", code: "B", month: "2026-09", message: "", issues: [], case_id: null, first: null, accepted_by: null, accepted_at: null };
    mock({ ...BASE, review: rv, comparison: { ...CMP, lumen_note: "1 of 2 weights differ from version 1." } }, []);
    view();
    expect(await screen.findByText(/1 of 2 weights differ from version 1\./)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open the signed benchmark definition" })).toHaveAttribute("href", "/centre/consume/benchmark?portfolio=P&code=B&start=2026-09&end=2026-09");
  });
});
