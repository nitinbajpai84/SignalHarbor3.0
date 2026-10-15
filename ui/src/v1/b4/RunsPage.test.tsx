import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { setSessionExpiredHandler } from "../../api/client";
import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import RunsPage from "./RunsPage";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const RUN = {
  id: "r1", source: "v1_custody", title: "Custodian positions", started: "2026-10-07T10:00:00Z", rows: 4, status: "failed", marts_ready: null,
  rules: [{ rule: "market_value:not empty", passed: false, count: 2 }, { rule: "account_id:not empty", passed: true, count: 0 }],
  note: { lines: ["custody failed.", "The cleaned layer loaded fewer than five rows for v1_custody."], text: null, fallback: true, sentence: "Flow could not reach the model." },
};
const DATA = { contracts: [{ source: "v1_custody", title: "Custodian positions", owner: "Leela Raman", schema: [{ field: "a" }], rules: ["x"], marts: ["gold.aum"] }], runs: [RUN] };

let fetchMock: ReturnType<typeof vi.fn>;
function open(roles: string[], runs: () => Response = () => json(DATA)) {
  fetchMock = vi.fn(async (url: string) => {
    if (url === "/api/auth/me") return json({ display_name: "Leela", company_id: "neera", roles });
    if (url === "/api/company") return json({ company_id: "neera", name: "Neera", industry: "family_office" });
    if (url === "/api/v1/build/i1/runs") return runs();
    if (url === "/api/v1/build/i1/load") return json({ runs: [RUN], missing: [{ title: "Fees", reason: "No file has landed for Fees yet." }], rows_left_out: 1 });
    return json({});
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<MemoryRouter initialEntries={["/centre/build/i1/runs"]}><ThemeProvider><SessionProvider>
    <Routes><Route path="/centre/build/:iid/runs" element={<RunsPage />} /></Routes>
  </SessionProvider></ThemeProvider></MemoryRouter>);
}
afterEach(() => { vi.unstubAllGlobals(); setSessionExpiredHandler(null); });

describe("Flow loads", () => {
  test("shows runs, failed checks and Flow's note, and runs the load", async () => {
    open(["analyst"]);
    expect(await screen.findByLabelText("Failed checks for Custodian positions")).toHaveTextContent("not empty (market_value): 2 rows");
    expect(screen.getByLabelText("Span's note on Custodian positions")).toHaveTextContent("custody failed.");
    await userEvent.click(screen.getByRole("button", { name: "Run the load" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Ran 1 source, 1 failed. No file has landed for Fees yet."));
  });

  test("a sponsor reads but has no run button", async () => {
    open(["sponsor"]);
    await screen.findByText("Run log");
    expect(screen.queryByRole("button", { name: "Run the load" })).toBeNull();
  });
});
