import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { setSessionExpiredHandler } from "../api/client";
import { ThemeProvider } from "../theme";
import { SessionProvider } from "../useSession";
import BlueprintPage from "./BlueprintPage";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const BP = {
  version: 1, state: "draft", signed_by: [], band: "now",
  model: { facts: [{ name: "fact_claims", grain: "one row per claim", keys: ["claim_id"], measures: ["LOSS_RATIO"] }], dimensions: [{ name: "dim_branch", keys: ["branch_id"], attributes: ["name"], scd: 2 }] },
  lineage: [{ measure: "LOSS_RATIO", source: "claims", fields: ["paid", "premium"], transform: "paid / premium", mart: "gold.loss_ratio.value" }],
  rules: [{ measure: "LOSS_RATIO", rule: "premium above zero", severity: "block", from: "scan" }],
  access: [{ mart: "gold.loss_ratio", may_see: ["Ann"] }],
  schedule: [{ source: "claims", expected: "D+2 09:00", sla: "WD8", depends_on: [] }],
  infra: { warehouse: "plane", runner: "builtin" },
  provenance: { "lineage.0": { mark: "guessed", from: "Scan of the claims file" }, "model.facts.0": { mark: "stated", from: "Baseline signed by Ann" } },
};

function mock(roles: string[], doc: unknown = BP) {
  const calls: { url: string; method: string; body?: string }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Ann", company_id: "co-a", roles });
    if (init?.method === "POST") {
      calls.push({ url, method: "POST" });
      return json(200, { ...BP, state: "signed", signed_by: [{ name: "Ann", role: "company_admin", at: "2026-10-07T09:00:00Z" }] });
    }
    if (init?.method === "PUT") {
      calls.push({ url, method: "PUT", body: String(init.body) });
      return json(200, { ...BP, model: { ...BP.model, facts: [{ ...BP.model.facts[0], grain: "one row per claim per month" }] } });
    }
    return json(200, doc);
  }));
  return calls;
}
const wrap = () => render(<MemoryRouter><ThemeProvider><SessionProvider><BlueprintPage /></SessionProvider></ThemeProvider></MemoryRouter>);

afterEach(() => { vi.unstubAllGlobals(); setSessionExpiredHandler(null); });

describe("Blueprint page", () => {
  test("shows model and lineage with marks and the diagram link", async () => {
    mock(["company_admin"]);
    wrap();
    expect(await screen.findByText("Fact: fact_claims")).toBeInTheDocument();
    expect(screen.getAllByText("gold.loss_ratio.value").length).toBeGreaterThan(0); // table and diagram
    expect(screen.getAllByText(/Guessed · Scan of the claims file/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Stated · Baseline signed by Ann/).length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "Draw the diagram" })).toHaveAttribute("href", "/centre/build/architecture");
  });

  test("two sources into one mart: both lineage lines show, the diagram draws one arrow per pair", async () => {
    const err = vi.spyOn(console, "error").mockImplementation(() => {});
    const two = [BP.lineage[0], { ...BP.lineage[0], source: "policies", fields: ["premium"] }];
    mock(["company_admin"], { ...BP, lineage: two, provenance: { ...BP.provenance, "lineage.1": { mark: "guessed", from: "Scan" } } });
    wrap();
    expect(await screen.findByText("Fact: fact_claims")).toBeInTheDocument();
    expect(screen.getAllByText("policies")).toHaveLength(2); // the lineage line and the diagram box
    expect(err.mock.calls.some((c) => String(c[0]).includes("same key"))).toBe(false);
    err.mockRestore();
  });

  test("sign calls the route, shows who and when, and locks editing", async () => {
    const calls = mock(["company_admin"]);
    wrap();
    await userEvent.click(await screen.findByRole("button", { name: "Sign" }));
    expect(await screen.findByText(/Signed by Ann \(company_admin\) · 7 October 2026/)).toBeInTheDocument();
    expect(screen.getAllByText(/Stated at signing · drafted from Scan of the claims file/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/Guessed · /)).toBeNull();
    expect(calls.map((c) => c.url)).toEqual(["/api/company/build/blueprint/sign"]);
    expect(screen.queryByRole("button", { name: /^Edit/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Sign" })).toBeNull();
  });

  test("sign locks the blueprint: read-only, Signed, and the way to room 2", async () => {
    mock(["company_admin"]);
    wrap();
    expect(await screen.findAllByRole("button", { name: /^Edit/ })).not.toHaveLength(0);
    await userEvent.click(screen.getByRole("button", { name: "Sign" }));
    await screen.findByText(/Signed by Ann/);
    expect(screen.queryAllByRole("textbox")).toHaveLength(0);
    expect(screen.queryAllByRole("button", { name: /^Edit/ })).toHaveLength(0);
    expect(screen.getByRole("link", { name: "Go to Build the data" })).toHaveAttribute("href", "/centre/build");
  });

  test("an edit sends one path and its value, as the route expects", async () => {
    const calls = mock(["company_admin"]);
    wrap();
    await userEvent.click(await screen.findByRole("button", { name: "Edit grain of fact_claims" }));
    const box = screen.getByRole("textbox", { name: "grain of fact_claims" });
    await userEvent.clear(box);
    await userEvent.type(box, "one row per claim per month");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText(/one row per claim per month/)).toBeInTheDocument();
    expect(calls).toHaveLength(1);
    expect(JSON.parse(calls[0]?.body ?? "")).toEqual({ path: "model.facts.0.grain", value: "one row per claim per month" });
  });

  test("a non-admin sees no Edit and no Sign, and a hidden row reads Restricted", async () => {
    mock(["analyst"], { ...BP, lineage: [{ hidden: true }], rules: [{ hidden: true }], access: [{ hidden: true }] });
    wrap();
    await screen.findByText("Fact: fact_claims");
    expect(screen.queryByRole("button", { name: /^Edit/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Sign" })).toBeNull();
    expect(screen.getAllByText("Restricted").length).toBe(3);
  });

  test("the diagram has a box per fact and shows the draft basis line", async () => {
    mock(["analyst"], { ...BP, basis: "draft baseline" });
    wrap();
    await screen.findByText("Fact: fact_claims");
    expect(document.querySelectorAll('svg [data-box="fact"]')).toHaveLength(BP.model.facts.length);
    expect(document.querySelectorAll('svg [data-box="dimension"]')).toHaveLength(BP.model.dimensions.length);
    expect(screen.getByText(/Drafted from a draft baseline/)).toBeInTheDocument();
  });

  test("no blueprint yet shows the reason", async () => {
    mock(["company_admin"], { state: "none", message: "There is nothing to draft from yet." });
    wrap();
    expect((await screen.findAllByText("There is nothing to draft from yet."))[0]).toBeInTheDocument();
  });
});
