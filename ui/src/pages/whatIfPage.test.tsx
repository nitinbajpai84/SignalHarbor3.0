import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { ThemeProvider } from "../theme";
import { SessionProvider } from "../useSession";
import WhatIfPage from "./WhatIfPage";

const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
const GRAPH = { nodes: [{ id: "lever:a", type: "Lever", label: "Rebalance" }, { id: "measure:b", type: "Measure", label: "Concentration" }, { id: "measure:b-again", type: "Measure", label: "Concentration" }, { id: "field:f", type: "Field", label: "Fees Charged" }, { id: "card:1", type: "Lever", label: "A card" }] };
const SAVED = [{ id: "s1", driver: "lever:a", change_pct: 10, note: "", saved_at: "2026-10-06T00:00:00+00:00", result: { driver: "lever:a", basis: "x", moved: [{ code: "measure:b", label: "Concentration", path: [], change_pct: 5, latest: null, assumed_direction: true }] } }];
const kept: unknown[] = [];
const bodies: { driver: string; change_pct: number }[] = [];

beforeEach(() => {
  bodies.length = 0; kept.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json({ display_name: "Ann", company_id: "co-a", roles: ["company_admin"] });
    if (url === "/api/company") return json({ company_id: "co-a", name: "T", industry: "family_office" });
    if (url === "/api/company/graph") return json(GRAPH);
    if (url === "/api/company/whatif/kept") return json({ scenarios: kept.length ? SAVED : [] });
    if (url === "/api/company/whatif/keep") { kept.push(JSON.parse(String(init?.body))); return json(SAVED[0]); }
    if (url === "/api/company/whatif") {
      const b = JSON.parse(String(init?.body)); bodies.push(b);
      return json({ driver: b.driver, basis: "linear", moved: [{ code: "measure:b", label: "Concentration", path: ["lever:a", "measure:b"], change_pct: b.change_pct / 2, latest: null, assumed_direction: true, text: "Concentration: Not available yet (assumed same way)" }] });
    }
    return json({});
  }));
});
afterEach(() => vi.unstubAllGlobals());
const open = () => render(<MemoryRouter><ThemeProvider><SessionProvider><WhatIfPage /></SessionProvider></ThemeProvider></MemoryRouter>);

describe("What-if page", () => {
  test("a field is a driver, a label is offered once, an unnamed card is not offered", async () => {
    open();
    await screen.findByRole("option", { name: /Fees Charged/ });
    expect(screen.getAllByRole("option", { name: /Concentration/ })).toHaveLength(1);
    expect(screen.queryByRole("option", { name: /A card/ })).toBeNull();
  });
  test("the slider changes the request", async () => {
    open();
    await screen.findByRole("option", { name: /Rebalance/ });
    fireEvent.change(screen.getByLabelText("Driver"), { target: { value: "lever:a" } });
    await screen.findByText("What moves");
    fireEvent.change(screen.getByLabelText("Change in percent"), { target: { value: "-20" } });
    await screen.findByText(/-10%/);
    expect(bodies.at(-1)).toEqual({ driver: "lever:a", change_pct: -20 });
  });
  test("results render with paths and Not available yet", async () => {
    open();
    await screen.findByRole("option", { name: /Rebalance/ });
    fireEvent.change(screen.getByLabelText("Driver"), { target: { value: "lever:a" } });
    expect(await screen.findByText("Not available yet")).toBeInTheDocument();
    expect(screen.getByText("Rebalance", { selector: "span" })).toBeInTheDocument();
  });
  test("Keep posts the scenario and the list shows it", async () => {
    open();
    await screen.findByRole("option", { name: /Rebalance/ });
    fireEvent.change(screen.getByLabelText("Driver"), { target: { value: "lever:a" } });
    fireEvent.change(await screen.findByLabelText("Note"), { target: { value: "hold" } });
    fireEvent.click(screen.getByRole("button", { name: "Keep this scenario" }));
    expect(await screen.findByRole("button", { name: /Re-run Rebalance/ })).toBeInTheDocument();
    expect(kept[0]).toEqual({ driver: "lever:a", change_pct: 10, note: "hold" });
    expect(screen.getAllByText("assumed same way").length).toBeGreaterThan(0);
  });
});

test("keep posts the note and the list renders with re-run and delete", async () => {
  kept.push({ seed: true });
  open();
  expect(await screen.findByRole("button", { name: "Delete Rebalance" })).toBeInTheDocument();
  expect(screen.getByText("Rebalance +10%")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Re-run Rebalance" }));
  expect(await screen.findByText("What moves")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Keep this scenario" }));
  await vi.waitFor(() => expect(kept.at(-1)).toEqual({ driver: "lever:a", change_pct: 10, note: "" }));
});
