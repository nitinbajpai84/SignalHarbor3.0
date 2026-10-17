import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { fmtNum, hasThread, looksLikeId, plainName, runLabel, skillLabel } from "./plain";
import OntologyPage from "./trust/OntologyPage";
import PeoplePage from "./trust/PeoplePage";
import ProofPage from "./trust/ProofPage";
import { model } from "./trust/a/fixtures";

vi.mock("../useSession", () => ({ useSession: () => ({ user: { display_name: "Anita" } }) }));
afterEach(() => vi.unstubAllGlobals());
const reply = (b: unknown) => new Response(JSON.stringify(b), { status: 200, headers: { "Content-Type": "application/json" } });
const serve = (routes: Record<string, unknown>) => vi.stubGlobal("fetch", vi.fn(async (u: string) => reply(Object.entries(routes).find(([k]) => String(u).includes(k))?.[1] ?? {})));
const at = (ui: React.ReactElement) => render(<MemoryRouter>{ui}</MemoryRouter>);

test("fmtNum groups thousands and leaves dates, short numbers and text alone", () => {
  expect(fmtNum("880400.00")).toBe("880,400.00");
  expect(fmtNum(1250000)).toBe("1,250,000");
  expect(fmtNum("-12345.5")).toBe("-12,345.5");
  expect(fmtNum("2026-10-17")).toBe("2026-10-17");
  expect(fmtNum("1,200.00")).toBe("1,200.00");
  expect(fmtNum("up 2%")).toBe("up 2%");
  expect(fmtNum("999")).toBe("999");
});

test("the label map names tables and columns; the fallback is Title Case; the skill label leaves the id alone", () => {
  expect(plainName("legal_entities")).toBe("Legal entities");
  expect(plainName("source_system")).toBe("Where it came from");
  expect(plainName("commitments.hedge_flag")).toBe("Hedge flag");
  expect(plainName("net_asset_value")).toBe("Net asset value");
  expect(skillLabel("Propose ontology addition")).toBe("Suggest a new kind of record");
  expect(skillLabel("Read a bank file")).toBe("Read a bank file");
});

test("run labels are dates, never ids; ids are recognised", () => {
  expect(runLabel("2026-10-09T06:11:00")).toBe("Run on 9 Oct, 06:11");
  expect(runLabel("run-20261016-225642-9d02")).toBe("Run");
  expect(looksLikeId("t-f15adc6b8f")).toBe(true);
  expect(looksLikeId("Liquidity and capital calls")).toBe(false);
});

test("proof and people show no run id or thread id, and no link when the run has no thread", async () => {
  const run = { run_id: "run-20261016-225642-9d02", kind: "copy", started: "2026-10-09T06:11:00", files: 3, checks_passed: 4, checks_total: 4, result: "Matched", signed_by: "Grace" };
  serve({ "/api/v3/runs": { runs: [{ ...run, thread: "t-f15adc6b8f" }, { ...run, run_id: "run-2", thread: null }, { ...run, run_id: "run-3", thread: "null" }] }, "/api/v3/threads": { threads: [{ id: "t-f15adc6b8f", title: "Liquidity", stage: "live", needs: 0 }] } });
  const { container, unmount } = at(<ProofPage />);
  expect(await screen.findByText("Liquidity")).toBeInTheDocument();
  expect(container.textContent).not.toMatch(/run-2026|t-f15adc/);
  expect(container.querySelectorAll('a[href="/v3/thread/null"]')).toHaveLength(0);
  expect(container.querySelectorAll('a[href^="/v3/thread/"]')).toHaveLength(1);
  expect(screen.getAllByText("No use case")).toHaveLength(2);
  unmount();
  serve({ "/api/v3/people": { people: [], second_signer: false, autonomy: [{ thread: "t-f15adc6b8f", level: "assist" }], ask_rules: [], usage: { questions: 0, builds: 0, mode: "testing" } }, "/api/v3/threads": { threads: [{ id: "t-f15adc6b8f", title: "Liquidity", stage: "live", needs: 0 }] } });
  const p = at(<PeoplePage />);
  expect(await p.findByText("Liquidity")).toBeInTheDocument();
  expect(p.container.textContent).not.toMatch(/t-f15adc/);
});

test("the ontology page shows plain words, no table or column names", async () => {
  serve({ "/api/v3/model": model });
  const { container } = at(<OntologyPage />);
  expect(await screen.findByText("What Harbor knows about your data")).toBeInTheDocument();
  expect(container.textContent).not.toMatch(/[a-z]+_[a-z]+|ontology|not mapped yet/i);
});
