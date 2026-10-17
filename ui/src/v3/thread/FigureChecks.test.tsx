import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import FigureChecks from "./FigureChecks";

const getFigure = vi.fn();
vi.mock("../api", () => ({ getFigure: (...a: unknown[]) => getFigure(...a) }));

const rec = (over: object) => ({ id: "f", name: "f", definition: "", grain: [], used_by: [], lineage: { files: [], tables: [], figure: {} },
  versions: [{ v: 1, status: "draft", built_from: { kind: "recipe", id: "x" }, reads: [], assumptions: [], runs: [], ...over }] });

test("no rows says why, a failed tie-out is red with its reason, a draft is amber", async () => {
  getFigure.mockResolvedValue(rec({ reason: "No bank file yet", tie_out: { rule: "Sums match", ok: false, at: "" } }));
  render(<FigureChecks figures={[{ figure_id: "f", name: "Cash", v: 1, status: "draft", hold: null }]} />);
  await screen.findByText(/Not available yet/);
  expect(screen.getAllByText(/No bank file yet/).length).toBeGreaterThan(0);
  expect(screen.getByLabelText("Tie-out problem")).toBeInTheDocument();
  expect(screen.getByText("Draft")).toHaveClass("needs");
});

test("an unreachable record still lists the figure", async () => {
  getFigure.mockRejectedValue(new Error("x"));
  render(<FigureChecks figures={[{ figure_id: "f", name: "Cash", v: 1, status: "verified", hold: null }]} />);
  await screen.findByText("Not tied out yet");
  expect(screen.getByText("Verified")).toHaveClass("done");
});
