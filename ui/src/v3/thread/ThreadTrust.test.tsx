import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";

import type { Stage, Thread } from "../api";
import ThreadPage from "./ThreadPage";

const getThread = vi.fn();
const decide = vi.fn();
const getFigure = vi.fn();
vi.mock("../api", () => ({
  editBrief: vi.fn(), say: vi.fn(), sendForSignature: vi.fn(),
  getThread: (i: string) => getThread(i),
  decide: (...a: unknown[]) => decide(...a),
  getFigure: (...a: unknown[]) => getFigure(...a),
}));
vi.mock("../Frame", () => ({ default: ({ children }: { children: ReactNode }) => <div>{children}</div> }));

const base = (stage: Stage, over: Partial<Thread> = {}): Thread => ({
  id: "t1", title: "Liquidity", stage, needs: 0, asked: 0, harbor_steps: 0, decision: null, events: [], ...over,
});
const show = (t: Thread) => {
  getThread.mockResolvedValue(t);
  return render(
    <MemoryRouter initialEntries={["/v3/thread/t1"]}>
      <Routes><Route path="/v3/thread/:id" element={<ThreadPage />} /></Routes>
    </MemoryRouter>,
  );
};

beforeEach(() => { vi.clearAllMocks(); decide.mockResolvedValue(base("working")); });

test("decision2 shows what I assumed, a disagreement and a document line, and sends the picks", async () => {
  show(base("decision2", { decision: { n: 2, title: "", files: [], assumptions: [{ figure: "Cash break", text: "Money in is positive", source: "loader" }],
    questions: [
      { id: "judge:k1", text: "Which side? Two models I asked did not agree.", options: ["in: looks like a credit (A)", "out: looks like a debit (B)", "Something else, I will say"] },
      { id: "doc:letter.pdf", text: "letter.pdf states a value.", options: ['"NAV: USD 1,200,000" (page 2)', "Keep it as context only"] },
    ] } }));
  await screen.findByText("Money in is positive");
  expect(screen.getByText("From your bank files")).toBeInTheDocument();
  expect(screen.getByText("I am not sure, two checks disagree")).toBeInTheDocument();
  fireEvent.click(screen.getByText("Use this line"));
  fireEvent.click(screen.getByText("in: looks like a credit (A)"));
  fireEvent.click(screen.getByText("This is right, carry on"));
  await waitFor(() => expect(decide).toHaveBeenCalledWith("t1", 2, "carry_on", { "judge:k1": "in: looks like a credit (A)", "doc:letter.pdf": '"NAV: USD 1,200,000" (page 2)' }));
});

test("decision3 lists each figure with its tie-out and says a held figure does not stop the rest", async () => {
  const ver = (over: object) => ({ built_from: { kind: "recipe", id: "x" }, reads: [], assumptions: [], runs: [], ...over });
  getFigure.mockImplementation((i: string) => Promise.resolve({ id: i, name: i, definition: "", grain: [], used_by: [], lineage: { files: [], tables: [], figure: {} },
    versions: [i === "a"
      ? ver({ v: 2, status: "verified", runs: [{ run_id: "r", at: "", ok: true, rows: 3 }], tie_out: { rule: "Bank balance equals the sum of movements", ok: true, at: "" } })
      : ver({ v: 3, status: "held", reason: "Opening balance missing", tie_out: { rule: "r", ok: false, at: "" } })] }));
  show(base("decision3", { decision: { n: 3, title: "", checks: [] },
    figures: [{ figure_id: "a", name: "Cash break", v: 2, status: "verified", hold: null }, { figure_id: "b", name: "Exposure", v: 3, status: "held", hold: { v: 3, reason: "Opening balance missing" } }] }));
  await screen.findByText("3 rows");
  expect(screen.getByText("Bank balance equals the sum of movements")).toBeInTheDocument();
  expect(screen.getByText("Verified")).toBeInTheDocument();
  expect(screen.getByText("Held")).toBeInTheDocument();
  expect(screen.getByRole("note")).toHaveTextContent("The rest can still go live");
  expect(screen.getByRole("note")).toHaveTextContent("not shown on the dashboard");
  expect(screen.getByText("Go live")).toBeInTheDocument();
});
