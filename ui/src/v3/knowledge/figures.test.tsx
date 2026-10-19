import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";

import type { FigureRecord, FigureRow } from "../api";
import FigurePage from "./FigurePage";
import FiguresPage from "./FiguresPage";

const listFigures = vi.fn();
const getFigure = vi.fn();
const rollbackFigure = vi.fn();
vi.mock("../api", () => ({ listFigures: () => listFigures(), getFigure: (i: string) => getFigure(i), rollbackFigure: (...a: unknown[]) => rollbackFigure(...a) }));
vi.mock("../Frame", () => ({ default: ({ children }: { children: ReactNode }) => <div>{children}</div> }));

const row: FigureRow = { id: "fig-cash", name: "Cash by entity", current_v: 2, status: "verified", built_from: { kind: "recipe", id: "cash_break" }, used_by_count: 3, last_run_at: "2026-10-14T08:00:00Z" };
const v = (n: number, status: "verified" | "held" | "draft") => ({
  v: n, built_from: { kind: "recipe", id: "cash_break" }, reads: ["cash_movements"], status, approved_by: "Daniel Foo", approved_at: "2026-10-10T08:00:00Z",
  assumptions: [{ text: "Money in is positive", source: "ASSUMPTIONS A5", at: "2026-10-10" }], runs: [{ run_id: `r${n}`, at: `2026-10-1${n}T08:00:00Z`, ok: status === "verified", rows: 3 }],
});
const rec = (cur: number): FigureRecord => ({
  id: "fig-cash", name: "Cash by entity", definition: "Cash held.", grain: ["entity"], current_v: cur, versions: [v(1, "verified"), v(2, "verified"), v(3, "held")],
  used_by: [{ thread: "t9", brief: "Liquidity brief", person: "Grace Ong" }],
  lineage: { files: [{ name: "bank.csv", rows: 40 }], tables: [{ name: "cash_movements", rows: 40 }], figure: { name: "Cash by entity" } },
});
const page = () => render(<MemoryRouter initialEntries={["/v3/knowledge/figures/fig-cash"]}><Routes><Route path="/v3/knowledge/figures/:id" element={<FigurePage />} /></Routes></MemoryRouter>);

beforeEach(() => vi.clearAllMocks());

test("the list shows name, status, built from, used by and last run", async () => {
  listFigures.mockResolvedValue([row, { ...row, id: "f2", name: "Held one", status: "held" }]);
  render(<MemoryRouter><FiguresPage /></MemoryRouter>);
  expect(await screen.findByRole("link", { name: "Cash by entity" })).toHaveAttribute("href", "/v3/knowledge/figures/fig-cash");
  expect(screen.getByText("Verified")).toHaveClass("done");
  expect(screen.getByText("Held")).toHaveClass("problem");
  expect(screen.getAllByText("recipe cash_break")).toHaveLength(2);
});

test("the figure page shows its five sections", async () => {
  getFigure.mockResolvedValue(rec(2));
  page();
  for (const h of ["Where this number comes from", "What I assumed", "Runs", "Versions", "Also used by"]) expect(await screen.findByRole("heading", { name: h })).toBeInTheDocument();
  expect(screen.getByText("bank.csv")).toBeInTheDocument();
  expect(screen.getByText("Money in is positive")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Liquidity brief" })).toHaveAttribute("href", "/v3/thread/t9");
});

test("roll back asks first, then calls the API and shows the new current version", async () => {
  getFigure.mockResolvedValue(rec(2));
  rollbackFigure.mockResolvedValue(rec(1));
  page();
  fireEvent.click(await screen.findByRole("button", { name: "Roll back" }));
  expect(rollbackFigure).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(screen.queryByRole("alertdialog")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Roll back" }));
  fireEvent.click(screen.getByRole("button", { name: "Yes, roll back" }));
  await waitFor(() => expect(rollbackFigure).toHaveBeenCalledWith("fig-cash", 1));
  expect(await screen.findByText("v1 (current)")).toBeInTheDocument();
});

test("a refused roll back shows the reason", async () => {
  getFigure.mockResolvedValue(rec(2));
  rollbackFigure.mockRejectedValue(new Error("Only an admin can do that."));
  page();
  fireEvent.click(await screen.findByRole("button", { name: "Roll back" }));
  fireEvent.click(screen.getByRole("button", { name: "Yes, roll back" }));
  expect(await screen.findByText("Only an admin can do that.")).toBeInTheDocument();
});

test("the figure page links to its recipe and its place on the knowledge map", async () => {
  getFigure.mockResolvedValue(rec(2));
  page();
  expect(await screen.findByRole("link", { name: "The recipe it follows" })).toHaveAttribute("href", "/v3/knowledge/thing/recipe:cash_break");
  expect(screen.getByRole("link", { name: "See it on the knowledge map" })).toHaveAttribute("href", "/v3/knowledge/thing/figure:cash");
});
