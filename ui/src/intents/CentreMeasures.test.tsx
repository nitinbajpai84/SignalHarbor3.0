import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { ThemeProvider } from "../theme";
import { CentreMeasures, toCsv, valueText, type Measure, type MeasuresDoc } from "./CentreMeasures";

// The panel "How the centre is doing" (spec 19). fetch is stubbed with synthetic numbers.

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const NAMES: Record<string, string> = { M01: "Intents opened per type per month", M02: "Closed inside the time box", M03: "Days from open to close by type", M13: "Average rating by type" };
const m = (id: string, over: Partial<Measure> = {}): Measure => ({
  id, name: NAMES[id] ?? id, value: null, numerator: null, denominator: null, by_type: {}, by_month: [], ids: [],
  missing: "Not available yet. Nothing has closed.", small_group: false, ...over,
});
const months = [{ month: "2026-09", count: 2 }, { month: "2026-10", count: 1 }];
const DOC: MeasuresDoc = {
  company: "co-a", window: "6m", months: ["2026-09", "2026-10"], scope: "all",
  measures: [
    m("M01", { value: 3, numerator: 3, ids: ["a", "b", "c"], missing: null, by_month: months }),
    m("M02", { value: 6, numerator: 6, denominator: 8, ids: ["a"], missing: null }),
    m("M03", { small_group: true, missing: null, denominator: 2 }),
    m("M13", { small_group: true, missing: null, ratings: 2 }),
    m("M09"),
  ],
};

function mock(doc: MeasuresDoc | "refused") {
  const calls: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    calls.push(url);
    if (doc === "refused") return json(403, { message: "Super admin sees counts only" });
    return json(200, doc);
  }));
  return calls;
}
const view = (onShow?: (ids: string[]) => void) =>
  render(<ThemeProvider><MemoryRouter><CentreMeasures onShowIntents={onShow} /></MemoryRouter></ThemeProvider>);

describe("CentreMeasures", () => {
  it("shows values as n of m, the small-group chip and the footnote", async () => {
    mock(DOC);
    view();
    expect(await screen.findByText("6 of 8")).toBeInTheDocument();
    expect(screen.getByText("3 opened")).toBeInTheDocument();
    expect(screen.getByText("Fewer than five")).toBeInTheDocument();
    expect(screen.getByText(/Numbers come from the intent records of this company/)).toBeInTheDocument();
    expect(screen.queryByText("%", { exact: false })).toBeNull();
  });

  it("expands to all four sections and shows the ratings rule from three", async () => {
    mock(DOC);
    view();
    fireEvent.click(await screen.findByRole("button", { name: "Show all measures" }));
    expect(screen.getByText("Effort")).toBeInTheDocument();
    expect(screen.getByText("Fewer than three ratings")).toBeInTheDocument();
    expect(screen.getAllByText("Not available yet. Nothing has closed.").length).toBeGreaterThan(0);
  });

  it("re-fetches with the window and opens a definition", async () => {
    const calls = mock(DOC);
    view();
    await screen.findByText("6 of 8");
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "12m" } });
    await screen.findByText("6 of 8");
    expect(calls.at(-1)).toBe("/api/intents/measures?window=12m");
    fireEvent.click(screen.getByRole("button", { name: /What this counts: Closed inside the time box/ }));
    expect(screen.getByRole("dialog")).toHaveTextContent("final end of the time box");
  });

  it("Show the intents passes exactly the ids; hidden when there are none", async () => {
    mock(DOC);
    const seen: string[][] = [];
    view((ids) => seen.push(ids));
    fireEvent.click(await screen.findByRole("button", { name: "Show the intents (3)" }));
    expect(seen).toEqual([["a", "b", "c"]]);
    expect(screen.queryByRole("button", { name: "Show the intents (0)" })).toBeNull();
  });

  it("shows the empty panel when no intent has been opened", async () => {
    mock({ ...DOC, measures: [m("M01", { missing: "Not available yet. No intent has been opened." })] });
    view();
    expect(await screen.findByText("Nothing to measure yet. Measures appear after the first intent is opened.")).toBeInTheDocument();
  });

  it("CSV has one row per measure per month, numbers only", () => {
    const csv = toCsv(DOC).trim().split("\n");
    expect(csv[0]).toBe("measure,group,month,numerator,denominator,value");
    expect(csv).toContain("M01,Starting and finishing,2026-09,2,,2");
    expect(csv).toContain("M02,Starting and finishing,current,6,8,6");
    expect(valueText(m("M02", { value: 0, numerator: 0, denominator: 3 }))).toBe("0 of 3");
  });
});
