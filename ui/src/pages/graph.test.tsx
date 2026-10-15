import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { setSessionExpiredHandler } from "../api/client";
import { ThemeProvider } from "../theme";
import { SessionProvider } from "../useSession";
import GraphPage, { type GraphDoc } from "./GraphPage";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const W1 = "wall:a", W2 = "wall:b";
const MAP: GraphDoc = {
  nodes: [
    { id: "problem:c1", type: "Problem", label: "Late capital-call notices" }, { id: "problem:c2", type: "Problem", label: "Fee leakage" },
    { id: "m1", type: "Measure", label: "Trust NAV" }, { id: "m2", type: "Measure", label: "Fees Charged" }, { id: "m3", type: "Measure", label: "Loose measure" },
    { id: "restricted-1", type: "Source", label: "A restricted source", restricted: true },
    { id: "s1", type: "Source", label: "Custodian" }, { id: "p1", type: "Person", label: "Olga Trustee" },
  ],
  edges: [
    { from: "problem:c1", to: "m1", type: "measured_by" }, { from: "problem:c2", to: "m2", type: "measured_by" }, { from: "problem:c2", to: "m3", type: "measured_by" },
    { from: "m1", to: "s1", type: "fed_by" }, { from: "m2", to: "restricted-1", type: "fed_by" }, { from: "m1", to: "p1", type: "owned_by" },
  ],
  columns: { walls: [{ id: W1, label: "Treasury" }, { id: W2, label: "Performance" }], problems: ["problem:c1", "problem:c2"], measures: ["m1", "m2", "m3"],
    systems: ["restricted-1", "s1"], owners: ["p1"] },
  by_wall: [{ wall: W1, problems: ["problem:c1"], measures: ["m1"] }, { wall: W2, problems: ["problem:c2"], measures: ["m2", "m3"] }],
  new_this_week: ["m2", "m1"],
  new_detail: { m2: [{ what: "Links changed", by: "the record", at: "x" }], m1: [{ what: "Accepted: a thing", by: "Marcus Todd", at: "x" }] }, holes: ["m3"],
  summary: { things: 10, links: 8, walls: 2, charters: 2, baselines: 1 },
};

function mock(phone = false) {
  vi.stubGlobal("matchMedia", (q: string) => ({ matches: phone && q.includes("max-width: 480px"), addEventListener: () => {}, removeEventListener: () => {} }));
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Priya", company_id: "co-a", roles: ["participant"] });
    if (url === "/api/company") return json(200, { company_id: "co-a", name: "Lakeside Test Co", industry: "family_office" });
    return json(200, MAP);
  }));
}
const open = () => render(<MemoryRouter><ThemeProvider><SessionProvider><GraphPage /></SessionProvider></ThemeProvider></MemoryRouter>);

afterEach(() => { vi.unstubAllGlobals(); setSessionExpiredHandler(null); });

describe("How my organisation connects", () => {
  test("five columns with their names, lines from the mock and a silhouette with no label", async () => {
    mock();
    const { container } = open();
    expect(await screen.findByText(/Built from 2 walls, 2 charters and 1 baseline\. 10 things, 8 links\./)).toBeInTheDocument();
    for (const h of ["Walls", "Problems", "Measures", "Systems", "Owners"]) expect(screen.getByText(h)).toBeInTheDocument();
    expect(screen.getByText("Treasury · Performance")).toBeInTheDocument();
    expect(screen.getByText("Trust NAV · Fees Charged · 1 more")).toBeInTheDocument();
    expect(screen.getByText("Custodian · 1 more")).toBeInTheDocument(); // the silhouette is counted, never named
    expect(container.querySelectorAll(".ds-map__lines line")).toHaveLength(8); // six graph edges and two wall lines
    expect(container.querySelector(`line[data-from="${W1}"][data-to="problem:c1"]`)).not.toBeNull();
    expect(container.textContent).not.toContain("A restricted source");
    expect(screen.getByRole("button", { name: "Loose measure, no source yet" })).toHaveClass("ds-node--hole");
  });

  test("clicking a measure selects it and shows its trail with the definition link", async () => {
    mock();
    open();
    fireEvent.click(await screen.findByRole("button", { name: "Trust NAV" }));
    const card = screen.getByText("Selected: Trust NAV").closest(".ds-side") as HTMLElement;
    expect(within(card).getByText("Asked for by the Treasury wall (problem: late capital-call notices). Defined in the baseline. "
      + "Supplied by the Custodian system. Owned by Olga Trustee.")).toBeInTheDocument();
    expect(within(card).getByRole("link", { name: "Open the definition" })).toHaveAttribute("href", "/centre/intent/map/m1");
    expect(screen.getByRole("button", { name: "Trace a measure" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("button", { name: "Fees Charged" })).toBeNull(); // the trace keeps only Trust NAV's line
  });

  test("the Holes chip keeps the holes and what asked for them", async () => {
    mock();
    open();
    fireEvent.click(await screen.findByRole("button", { name: "Gaps: 1" }));
    expect(screen.getByRole("button", { name: "Loose measure, no source yet" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Fee leakage" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Trust NAV" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Treasury" })).toBeNull();
  });

  test("the phone shows one wall card at a time and the tab bar", async () => {
    mock(true);
    open();
    expect(await screen.findByText("Treasury wall")).toBeInTheDocument();
    expect(screen.getByText("1 problem · 1 measure")).toBeInTheDocument();
    expect(screen.queryByText("Performance wall")).toBeNull();
    expect(screen.queryByRole("button", { name: "Fees Charged" })).toBeNull();
    expect(screen.getByText("Tap a measure to trace it")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next wall" }));
    expect(screen.getByText("Performance wall")).toBeInTheDocument();
    const bar = await screen.findByRole("navigation", { name: "Main" });
    expect(within(bar).getByRole("link", { name: "Map" })).toHaveAttribute("aria-current", "page");
    expect(within(bar).queryByRole("link", { name: "Build" })).toBeNull(); // a participant's bar: Pulse and Map
  });

  test("the chip, the filtered columns and the panel tell one story", async () => {
    mock();
    open();
    expect(screen.queryByText("The links around Fees Charged were updated.")).toBeNull(); // chip off: no list
    fireEvent.click(await screen.findByRole("button", { name: "New this week: 2" }));
    expect(screen.getByText("The links around Fees Charged were updated.")).toBeInTheDocument();
    expect(screen.getByText("Trust NAV changed after Marcus Todd accepted a suggestion.")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(2); // the panel's lines equal the chip's count
    expect(screen.getByRole("button", { name: "Fees Charged" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Loose measure, no source yet" })).toBeNull(); // only the two new things stay
    expect(screen.queryByText(/restricted/i)).toBeNull();
  });
});
