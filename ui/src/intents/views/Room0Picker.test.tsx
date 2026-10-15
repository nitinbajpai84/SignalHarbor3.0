import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { GapAnalysisRoom } from "./BuildReadyView";

vi.mock("../../useSession", () => ({ useSession: () => ({ user: { roles: ["company_admin"] } }) }));

// N6: room 0 with no hand-over in the address lists what Build may start from; synthetic rows only.
const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
const ROW = { id: "ini-1", title: "Fund capital calls", organiser: "Janet Shaw", state: "closed", handed_over: false, n_ok: 4, of: 7, assessment_id: null, may_start: true,
  href: "/centre/build/gap-analysis?from=ini-1" };

function mount(list: unknown) {
  const calls: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push(`${init?.method ?? "GET"} ${url}`);
    return json(init?.method === "POST" ? { assessment_id: "a1", href: "/centre/build/gap-analysis?from=ini-1" } : list);
  }));
  render(<MemoryRouter initialEntries={["/centre/build/gap-analysis"]}><Routes>
    <Route path="/centre/build/gap-analysis" element={<GapAnalysisRoom />} /></Routes></MemoryRouter>);
  return calls;
}
afterEach(() => vi.unstubAllGlobals());

describe("room 0 without a hand-over", () => {
  it("lists the Initiatives with organiser and n of 7, and starts the gap analysis", async () => {
    const calls = mount({ initiatives: [ROW], build_ready_href: "/centre/intent?type=initiative" });
    expect(await screen.findByText("Fund capital calls")).toBeInTheDocument();
    expect(screen.getByText(/Organiser Janet Shaw · Build-ready 4 of 7 · Closed, went to Build/)).toBeInTheDocument();
    expect(screen.queryByText(/Start it from the Moment of truth/)).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Start the gap analysis" }));
    expect(calls).toContain("POST /api/company/build/gap-analysis/ini-1/start");
  });

  it("says no Initiative has been handed over, with a link to the list", async () => {
    mount({ initiatives: [], build_ready_href: "/centre/intent?type=initiative" });
    expect(await screen.findByText("No Initiative has been handed to Build yet.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "See the Initiatives and their build-ready checks" })).toHaveAttribute("href", "/centre/intent?type=initiative");
  });
});
