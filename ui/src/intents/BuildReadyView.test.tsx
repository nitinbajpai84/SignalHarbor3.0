import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import BuildReadyView, { GapAnalysisRoom } from "./views/BuildReadyView";

vi.mock("../useSession", () => ({ useSession: () => ({ user: { roles: ["company_admin"] } }) }));

// File 33: the check page and the room 0 banner. fetch is stubbed with synthetic records.

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const line = (n: number, ok: boolean, extra: object = {}) => ({ n, key: `k${n}`, title: `Line ${n} title`, group: n === 1 || n === 7 ? "Agreed on paper" : n < 4 ? "Defined" : "Owned", ok, count: ok ? 2 : 1, of: 2,
  missing: ok ? [] : [{ kind: "process", ref: "p1", label: "Fund a call", turn_of: { name: "Harvey Rowley", role: "business owner" }, href: "/centre/intent/i1/define?tab=process-map&process=p1", fix: "Fix it in the process map" }],
  evidence: { record: "Process map", id: "i1", read_at: "2026-10-07T06:05:00+00:00" }, text: ok ? "" : "1 processes have no confirmed owner.", ...extra });
const DATA = (n_ok: number, extra: object = {}) => ({ id: "i1", title: "Capital calls", type: "initiative", state: "closing", level: "full", time_zone: "UTC", n_ok, of: 7,
  verdict: n_ok === 7 ? "ready" : "incomplete", checked_at: "2026-10-07T06:05:00+00:00", lines: [1, 2, 3, 4, 5, 6, 7].map((n) => line(n, n <= n_ok)),
  todo: [{ line: 4, text: "Harvey, business owner: Fund a call", turn_of: null, href: "/centre/intent/i1/define?tab=process-map", fix: "Fix it in the process map", since: "2026-10-06T06:00:00+00:00" }],
  build_needed: n_ok === 7 ? true : null, is_organiser: true, can_answer: true, may_hand_over: true, may_recheck: true, can_hand_over: n_ok === 7, stops: "Line 4 stops this: 1 processes have no confirmed owner.",
  measure_count: 12, source_count: 3, catalogue_version: 1, handoff: null, assessment_id: null, gap_analysis_href: "/centre/build/gap-analysis?from=i1", ...extra });

function mount(body: unknown, path = "/centre/intent/i1/build-ready") {
  const calls: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => { calls.push(`${init?.method ?? "GET"} ${url}`); return json(200, body); }));
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/centre/intent/:intentId/build-ready" element={<BuildReadyView />} />
        <Route path="/centre/build/gap-analysis" element={<GapAnalysisRoom />} />
        <Route path="*" element={<p>elsewhere</p>} />
      </Routes>
    </MemoryRouter>,
  );
  return calls;
}
afterEach(() => vi.unstubAllGlobals());

describe("build-ready check", () => {
  it("shows the chip, seven lines, the failing line's fix link and the first failing line beside a disabled button", async () => {
    mount(DATA(3, { can_hand_over: false }));
    expect(await screen.findByText("Build-ready: 3 of 7")).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(7);
    expect(screen.getAllByRole("link", { name: "Fix it in the process map" }).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Hand to Build" })).toBeDisabled();
    expect(screen.getAllByText(/Line 4 stops this/).length).toBeGreaterThan(0);
  });

  it("at 7 of 7 the organiser confirms, then the hand-off is posted", async () => {
    const calls = mount(DATA(7));
    await userEvent.click(await screen.findByRole("button", { name: "Hand to Build" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("The charter stays signed and read-only");
    await userEvent.click(screen.getAllByRole("button", { name: "Hand to Build" })[1]!);
    expect(calls).toContain("POST /api/intents/i1/handoff");
  });

  it("someone who is not the organiser (the sponsor, the company admin) sees the button disabled with the reason", async () => {
    mount(DATA(7, { is_organiser: false, may_hand_over: false, can_hand_over: false }));
    expect(await screen.findByText("Only the organiser hands over.")).toBeInTheDocument();
  });

  it("an affected person sees counts and the verdict, no names", async () => {
    mount({ ...DATA(3), level: "counts", todo: [], lines: DATA(3).lines.map(({ n, key, title, group, ok, count, of }) => ({ n, key, title, group, ok, count, of })) });
    expect(await screen.findByText("Build-ready: 3 of 7")).toBeInTheDocument();
    expect(screen.queryByText(/Harvey/)).toBeNull();
  });

  it("room 0 shows the hand-over banner and the reads strip", async () => {
    mount(DATA(7, { verdict: "handed_over", handoff: { by: { name: "Janet Shaw" }, at: "2026-10-07T07:00:00+00:00", catalogue_version: 1, source_count: 3, measure_count: 12, definition_changed: false, current_catalogue_version: 1 } }),
      "/centre/build/gap-analysis?from=i1");
    expect(await screen.findByText(/Handed over from Capital calls on 7 October 2026 by Janet Shaw/)).toBeInTheDocument();
    expect(screen.getByText("Reading: baseline version 1, 3 sources")).toBeInTheDocument();
  });

  it("room 0 lists the processes and the sources, strategic and not strategic apart", async () => {
    const handoff = { by: { name: "Janet Shaw" }, at: "2026-10-07T07:00:00+00:00", catalogue_version: 1, source_count: 2, measure_count: 12, definition_changed: false, current_catalogue_version: 1,
      processes: [{ id: "p1", name: "Fund a call", owner: "Harvey Rowley", confirmed: true }],
      source_map: [{ id: "S01", name: "Custodian file", zone: "p1", strategic: true }, { id: "S02", name: "Mail archive", zone: "identify", strategic: false }] };
    mount(DATA(7, { verdict: "handed_over", handoff }), "/centre/build/gap-analysis?from=i1");
    expect(await screen.findByText("Fund a call, owner Harvey Rowley, confirmed")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Strategic sources" })).getByText(/Custodian file/)).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Not strategic sources" })).getByText(/Mail archive/)).toBeInTheDocument();
  });

  it("Nudge posts for the row and shows the draft when it was not sent", async () => {
    const calls: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      calls.push(`${init?.method ?? "GET"} ${url}`);
      return json(200, url.endsWith("/nudge") ? { sent: false, text: "Harvey, it is waiting.", note: "North wrote this reminder. It was not sent." } : DATA(3, { todo: [{ line: 4, ref: "p1", text: "Harvey, business owner: Fund a call", turn_of: { name: "Harvey Rowley", role: "business owner" }, href: null, fix: null, since: null }] }));
    }));
    render(<MemoryRouter initialEntries={["/centre/intent/i1/build-ready"]}><Routes><Route path="/centre/intent/:intentId/build-ready" element={<BuildReadyView />} /></Routes></MemoryRouter>);
    await userEvent.click(await screen.findByRole("button", { name: "Nudge" }));
    expect(calls).toContain("POST /api/intents/i1/build-ready/nudge");
    expect(await screen.findByText(/It was not sent\. .Harvey, it is waiting\./)).toBeInTheDocument();
    expect(screen.getByText("Draft by North")).toBeInTheDocument();
  });
});
