import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import Chart from "./Chart";

const used = { tables: [], last_refresh: null };
const draw = (view: string, rows: Record<string, unknown>[], label = "Tile") =>
  render(<Chart label={label} data={{ spec: { mark: "text", usermeta: { view }, encoding: {} }, rows, data_used: used }} />);

test("bullet: a bar against its target, labelled for screen readers", () => {
  draw("bullet", [{ name: "Fund A", value: 30, target: 24 }, { name: "Fund B", value: 5, target: 8 }]);
  expect(screen.getByLabelText("Fund A: 30.0 against 24.0")).toBeInTheDocument();
  expect(screen.getByLabelText("Fund B: 5.0 against 8.0")).toBeInTheDocument();
});

test("waterfall: steps run on from the last and a Total is added", () => {
  draw("waterfall", [{ label: "Equity", value: 10 }, { label: "Bonds", value: -4 }]);
  expect(screen.getByLabelText("Equity: up 10.0")).toBeInTheDocument();
  expect(screen.getByLabelText("Bonds: down 4.0")).toBeInTheDocument();
  expect(screen.getByLabelText("Total: 6.0")).toBeInTheDocument();
});

test("small multiples: one panel per group", () => {
  draw("small_multiples", [{ x: "2026-01", grp: "A", value: 1 }, { x: "2026-02", grp: "A", value: 3 }, { x: "2026-01", grp: "B", value: 2 }]);
  expect(screen.getByLabelText("A: 1.0, 3.0")).toBeInTheDocument();
  expect(screen.getByLabelText("B: 2.0")).toBeInTheDocument();
});

test("calendar: the newest month as a grid, days without an amount say nothing", () => {
  draw("calendar", [{ day: "2026-09-01", value: 10 }, { day: "2026-09-15", value: 20 }]);
  expect(screen.getByLabelText("15 September 2026: 20.0")).toBeInTheDocument();
  expect(screen.getByLabelText("2 September 2026: nothing")).toBeInTheDocument();
});

test("treemap: a box per category with its share; non-positive values are left out", () => {
  draw("treemap", [{ label: "Equity", value: 75 }, { label: "Cash", value: 25 }, { label: "Debt", value: -5 }]);
  expect(screen.getByLabelText("Equity: 75.0 (75.0%)")).toBeInTheDocument();
  expect(screen.queryByLabelText(/Debt/)).toBeNull();
});

test("kpi strip: newest value, change on the one before", () => {
  draw("kpi_strip", [{ period: "2026-08", called: 10, pnl: 1 }, { period: "2026-09", called: 25, pnl: -2 }]);
  expect(screen.getByLabelText("Called: 25.0, up 15.0")).toBeInTheDocument();
  expect(screen.getByLabelText("Pnl: -2.0, down 3.0")).toBeInTheDocument();
});

test("empty rows say so rather than showing zero", () => {
  draw("treemap", []);
  expect(screen.getByText("Not available yet")).toBeInTheDocument();
});
