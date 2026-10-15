import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import ArchitecturePage from "./ArchitecturePage";
import ChainPanel from "./ChainPanel";
import ChangeNotePage from "./ChangeNotePage";
import HandOverStrip from "./HandOverStrip";
import type { Change, ChangeSummary } from "./chain";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const NAMES = ["Architect", "Approval", "Data engineer", "Tester", "Ops manager"];
const summary = (step: number, over: Partial<ChangeSummary> = {}): ChangeSummary => ({
  id: "C-0003", intent_id: "ini-1", title: "Valuation chase protocol", state: "with_approver", step,
  steps: NAMES.map((name, i) => ({ n: i + 1, name, person: i === 4 ? null : ["Aaron", "Grace", "Katie", "Mei Ling"][i] ?? null, state: i + 1 < step ? "signed" : i + 1 === step ? "with" : "waiting", days: i + 1 === step ? 2 : null, signed: i + 1 < step ? { by: "x", at: "2026-10-03" } : null })),
  ...over,
});
const change = (over: Partial<Change> = {}): Change => ({
  ...summary(2), sections: { why: [{ text: "Stale valuations hide risk", mark: "stated" }], what_changes: [{ text: "Adds gold.k12", group: "Data" }], decisions: [], build_steps: [], tests: [], run_book: [], risks: [] },
  returns: [], signatures: [], release: null, can_act: true, completeness: { line: "Every measure has a test.", gap: "2 components have no owner." }, ...over,
});
function mock(routes: Record<string, unknown>, posts: string[] = []) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Grace", company_id: "co", roles: ["approver"] });
    if (init?.method === "POST" || init?.method === "PUT") { posts.push(`${init.method} ${url} ${String(init.body)}`); return json(200, {}); }
    const hit = Object.entries(routes).find(([k]) => url.startsWith(k));
    return hit ? json(200, hit[1]) : json(404, { message: "no" });
  }));
}
const wrap = (el: ReactElement, at = "/") => render(<MemoryRouter initialEntries={[at]}><ThemeProvider><SessionProvider>{el}</SessionProvider></ThemeProvider></MemoryRouter>);
afterEach(() => vi.unstubAllGlobals());

vi.setConfig({ testTimeout: 20000 });

describe("Build chain", () => {
  test("panel: one row per open change, a missing person, the live count", async () => {
    mock({ "/api/company/build/changes": { changes: [summary(2, { last_return: { from: 4, to: 3, by: "Mei Ling", reason: "K12 does not match for 2026-08", at: "2026-10-04" } }), summary(5, { id: "C-0001", state: "live" })] } });
    wrap(<ChainPanel />);
    expect(await screen.findByRole("link", { name: "C-0003 Valuation chase protocol" })).toBeInTheDocument();
    expect(screen.getAllByText("Not named yet").length).toBe(1);
    expect(screen.getByText(/Sent back by Mei Ling: K12 does not match/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Live: 1 change" })).toBeInTheDocument();
  });

  test("panel: empty state", async () => {
    mock({ "/api/company/build/changes": { changes: [] } });
    wrap(<ChainPanel />);
    expect(await screen.findByText(/Nothing is being built/)).toBeInTheDocument();
    expect(screen.getByText("No change is live yet.")).toBeInTheDocument();
  });

  test("hand-over strip: step line and hidden when nothing is open", async () => {
    mock({ "/api/company/build/changes": { changes: [summary(3)] } });
    const { unmount } = wrap(<HandOverStrip />);
    expect(await screen.findByText("Step 3 of 5, data engineer: Katie. Building against change note C-0003.")).toBeInTheDocument();
    unmount();
    mock({ "/api/company/build/changes": { changes: [] } });
    const { container } = wrap(<HandOverStrip />);
    await new Promise((r) => setTimeout(r, 20));
    expect(container.querySelector(".bc-strip")).toBeNull();
  });

  test("change note: approval is disabled with North's gap; send back needs a reason", async () => {
    const posts: string[] = [];
    mock({ "/api/company/build/changes/C-0003": change() }, posts);
    wrap(<Routes><Route path="/centre/build/change/:id" element={<ChangeNotePage />} /></Routes>, "/centre/build/change/C-0003");
    expect(await screen.findByRole("button", { name: "Approve the design" })).toBeDisabled();
    expect(screen.getAllByText("2 components have no owner.").length).toBeGreaterThan(0);
    expect(screen.getByText("Not drafted yet.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Send back" }));
    const send = screen.getAllByRole("button", { name: "Send back" }).at(-1) as HTMLElement;
    expect(send).toBeDisabled();
    await userEvent.type(screen.getByRole("textbox"), "Name the owner");
    await userEvent.click(send);
    expect(posts[0]).toContain("POST /api/company/build/changes/C-0003/send-back");
    expect(posts[0]).toContain("Name the owner");
  });

  test("change note: Span's run notes sit under the build steps", async () => {
    mock({ "/api/company/build/changes/C-0003": change({ run_notes: [
      { source: "custodian_file", run_id: "r1", note: { text: "custodian file ran and every check passed.", lines: ["x", "Fewer than five rows set aside for a check, field isin. They stay in the company space."] } },
      { source: "payroll_file", run_id: null, note: null }] } as Partial<Change>) });
    wrap(<Routes><Route path="/centre/build/change/:id" element={<ChangeNotePage />} /></Routes>, "/centre/build/change/C-0003");
    expect(await screen.findByText("What Span saw in the runs")).toBeInTheDocument();
    expect(screen.getByText(/Fewer than five rows set aside/)).toBeInTheDocument();
    expect(screen.getByText("No run yet for payroll file")).toBeInTheDocument();
  });

  test("change note: someone who is not named cannot act", async () => {
    mock({ "/api/company/build/changes/C-0003": change({ can_act: false, completeness: null }) });
    wrap(<Routes><Route path="/centre/build/change/:id" element={<ChangeNotePage />} /></Routes>, "/centre/build/change/C-0003");
    expect(await screen.findByRole("button", { name: "Approve the design" })).toBeDisabled();
    expect(screen.getByText(/Only the named person may act/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Stop this change" })).toBeNull();
  });

  test("architecture: empty record, then a restricted component shows no name", async () => {
    mock({ "/api/company/build/architecture": { version: 0, regenerated: null, counts: { data: 0, infrastructure: 0, enterprise: 0 }, versions: [], components: [], diagram: null } });
    const { unmount } = wrap(<ArchitecturePage />);
    expect((await screen.findAllByText(/The Architect drafts it when the first blueprint is signed/)).length).toBe(2);
    unmount();
    mock({ "/api/company/build/architecture": {
      version: 7, regenerated: { moment: "release_signed", by: "Daniel", at: "2026-10-03" }, counts: { data: 2, infrastructure: 0, enterprise: 0 }, versions: [{ v: 7, moment: "release_signed", at: "2026-10-03" }],
      components: [{ id: "a", label: "gold.k12", kind: "gold", view: "data", owner: null, version: 1, state: "live" }, { id: "b", label: "secret.table", kind: "gold", view: "data", owner: "Harvey", version: 1, state: "live", restricted: true }],
      diagram: null, owners_missing: [{ id: "a", label: "gold.k12" }],
    } });
    wrap(<ArchitecturePage />);
    expect(await screen.findByText(/Version 7, regenerated when the release was signed on 3 October 2026/)).toBeInTheDocument();
    expect(screen.queryByText("secret.table")).toBeNull();
    expect(screen.getAllByText("Restricted").length).toBeGreaterThan(0);
    expect(screen.getByText(/1 component has no owner: gold.k12/)).toBeInTheDocument();
    expect(screen.getByText("Infrastructure: None yet")).toBeInTheDocument();
  });
});
