import { render, screen } from "@testing-library/react";

import { ThemeProvider } from "../../theme";
import Swimlane from "./Swimlane";

// UX-10: the same map is a swim lane with a scroll hint on a wide screen and a numbered list under 760px.
const MAP = {
  steps: [
    { n: 1, name: "Pull administrator file", who: "Operations", does: "", inputs: [], outputs: [], system: "Portal" },
    { n: 2, name: "Reconcile cash in a spreadsheet", who: "Finance", does: "", inputs: [], outputs: [], system: "Excel" },
  ],
  handovers: [],
};
const width = (matches: boolean) => vi.stubGlobal("matchMedia", vi.fn(() => ({ matches, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
afterEach(() => vi.unstubAllGlobals());

test("wide: swim lane with a scroll hint", () => {
  width(false);
  render(<ThemeProvider><Swimlane map={MAP} selected={null} onSelect={() => {}} /></ThemeProvider>);
  expect(screen.getByText("Scroll sideways to see all 2 steps.")).toBeInTheDocument();
  expect(screen.getByRole("group", { name: "Process map" })).toBeInTheDocument();
});

test("narrow: a numbered list with lane, name and the Manual pill", () => {
  width(true);
  render(<ThemeProvider><Swimlane map={MAP} selected={null} onSelect={() => {}} /></ThemeProvider>);
  expect(screen.queryByText(/Scroll sideways/)).toBeNull();
  const items = screen.getAllByRole("listitem");
  expect(items).toHaveLength(2);
  expect(items[1]).toHaveTextContent(/Finance.*Reconcile cash in a spreadsheet.*Manual/);
  expect(items[0]).not.toHaveTextContent("Manual");
});

test("UC9-02, UC9-06: the phone list keeps system, what is done and hand-overs; the legend does not call people's steps automated", () => {
  width(true);
  const [s1, s2] = MAP.steps as [(typeof MAP.steps)[number], (typeof MAP.steps)[number]];
  const map = { ...MAP, steps: [{ ...s1, does: "Downloads the file" }, s2], handovers: [{ from_step: 1, to_step: 2, what: "NAV file" }] };
  render(<ThemeProvider><Swimlane map={map} selected={null} onSelect={() => {}} /></ThemeProvider>);
  const items = screen.getAllByRole("listitem");
  expect(items[0]).toHaveTextContent(/Portal\. Downloads the file/);
  expect(items[0]).toHaveTextContent("To step 2: NAV file");
  expect(items[1]).toHaveTextContent("Excel");
  vi.unstubAllGlobals();
  width(false);
  render(<ThemeProvider><Swimlane map={map} selected={null} onSelect={() => {}} /></ThemeProvider>);
  expect(screen.getByText("Not flagged for automation")).toBeInTheDocument();
  expect(screen.queryByText(/System-automated/)).toBeNull();
});
