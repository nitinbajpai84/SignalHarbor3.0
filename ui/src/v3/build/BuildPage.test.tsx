import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, test, vi } from "vitest";

import type { BriefGroup, BriefLine, Stage, Thread } from "../api";
import BuildPage, { stepClass } from "./BuildPage";
import IntentGraph, { buildNodes, NW, NH, W } from "./IntentGraph";

const getThread = vi.fn();
const listThreads = vi.fn();
const listFiles = vi.fn();
const startThread = vi.fn();
const say = vi.fn();
const decide = vi.fn();
const editBrief = vi.fn();
const sendForSignature = vi.fn();
vi.mock("../api", () => ({
  getThread: (i: string) => getThread(i),
  listThreads: () => listThreads(),
  listFiles: () => listFiles(),
  startThread: (...a: unknown[]) => startThread(...a),
  say: (...a: unknown[]) => say(...a),
  decide: (...a: unknown[]) => decide(...a),
  sendForSignature: (...a: unknown[]) => sendForSignature(...a),
  editBrief: (...a: unknown[]) => editBrief(...a),
}));
vi.mock("../Frame", () => ({ default: ({ children }: { children: ReactNode }) => <div>{children}</div> }));

const line = (section: string, index: number | null, field: string, label: string, value: string, changed = false): BriefLine =>
  ({ section, index, field, label, value, suggested: false, changed });
const doc: BriefGroup[] = [
  { title: "What you want", lines: [line("goal", null, "line", "The question", "Can each entity meet its calls?"), line("goal", null, "readers", "Read by", "Mei", true), line("goal", null, "needed_by", "When it is needed", "Every morning")] },
  { title: "Figure: Calls due", lines: [line("kpis", 0, "name", "Name", "Calls due"), line("kpis", 0, "definition", "What it means", "Due in 30 days")] },
  { title: "Where the data comes from", lines: [line("sources", 0, "holds", "Bank statements", "Bank"), line("sources", 1, "holds", "Call notices", "Admin")] },
];
const thread = (stage: Stage, over: Partial<Thread> = {}): Thread => ({
  id: "t1", title: "Liquidity", stage, needs: 0, asked: 0, harbor_steps: 0,
  decision: { n: 1, title: "", brief: { question: "Q", files: [], read_by: "", refresh: "", cases_when: "", doc } },
  events: [{ at: "1 Oct", kind: "person", text: "Hello there", by: "Anita" }], ...over,
});
const at = (path: string) => render(
  <MemoryRouter initialEntries={[path]}>
    <Routes><Route path="/v3/build" element={<BuildPage />} /><Route path="/v3/build/:id" element={<BuildPage />} /></Routes>
  </MemoryRouter>,
);

beforeEach(() => {
  vi.clearAllMocks();
  listFiles.mockResolvedValue({ files: [{ name: "bank.pdf", arrived_at: "x", status: "recognised", source: "Bank statements", thread: "t1" }, { name: "other.pdf", arrived_at: "x", status: "recognised", source: "Call notices", thread: "t2" }] });
  decide.mockResolvedValue(thread("working"));
});

test("board groups threads by stage and links to the thread", async () => {
  listThreads.mockResolvedValue({ threads: [
    { id: "a", title: "Fees", stage: "decision1", needs: 1 },
    { id: "b", title: "Net worth", stage: "live", needs: 0 },
  ] });
  at("/v3/build");
  await screen.findByText("Fees");
  expect(screen.getByLabelText("Brief")).toHaveTextContent("Fees");
  expect(screen.getByLabelText("Live")).toHaveTextContent("Net worth");
  expect(screen.getAllByText(/Open thread/)[0]?.closest("a")).toHaveAttribute("href", "/v3/build/a");
  startThread.mockResolvedValue(thread("drafting"));
  getThread.mockResolvedValue(thread("drafting"));
  fireEvent.change(screen.getByLabelText("Say what you want to know"), { target: { value: "Liquidity" } });
  fireEvent.click(screen.getByText("Start"));
  await waitFor(() => expect(startThread).toHaveBeenCalledWith("Liquidity"));
});

test("board shows an error with retry", async () => {
  listThreads.mockRejectedValue(new Error("down"));
  at("/v3/build");
  expect(await screen.findByText(/down/)).toBeInTheDocument();
  expect(screen.getByText("Try again")).toBeInTheDocument();
});

test("thread view shows the now-line, graph, decision action and expected files", async () => {
  getThread.mockResolvedValue({ ...thread("decision1"), now: { skill: "s", name: "S", text: "Defining the figure: Calls due" } });
  at("/v3/build/t1");
  await screen.findByText("Hello there");
  expect(screen.getByText(/Defining the figure/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Calls due" })).toBeInTheDocument();
  fireEvent.click(screen.getByText("Confirm the brief"));
  expect(decide).toHaveBeenCalledWith("t1", 1, "confirm");
  expect(await screen.findByText(/Bank statements · arrived, 1 file/)).toBeInTheDocument();
  expect(screen.getByText(/Call notices · waiting/)).toBeInTheDocument();
});

test("thread view reports a missing thread", async () => {
  getThread.mockRejectedValue(new Error("boom"));
  at("/v3/build/zz");
  expect(await screen.findByText("boom")).toBeInTheDocument();
});

test("graph builds nodes from the doc and marks changed ones", () => {
  const ids = buildNodes(doc).map((n) => n.id);
  expect(ids).toEqual(["question", "readers", "when", "figure:Figure: Calls due", "source:0", "source:1"]);
  expect(buildNodes(doc).find((n) => n.id === "readers")?.changed).toBe(true);
  render(<IntentGraph doc={doc} busy={false} onSave={vi.fn()} />);
  expect(screen.getByRole("button", { name: "Who reads and decides" })).toHaveClass("glow");
  expect(screen.getByText("just added")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "When" })).not.toHaveClass("glow");
});

test("clicking a node opens the editor and saves a line", async () => {
  const onSave = vi.fn().mockResolvedValue(undefined);
  render(<IntentGraph doc={doc} busy={false} onSave={onSave} />);
  fireEvent.click(screen.getByRole("button", { name: "Calls due" }));
  fireEvent.click(screen.getByLabelText("Edit What it means"));
  fireEvent.change(screen.getByLabelText("Change What it means"), { target: { value: "Due in 60 days" } });
  fireEvent.click(screen.getByText("Save"));
  await waitFor(() => expect(onSave).toHaveBeenCalledWith(doc[1]?.lines[1], "Due in 60 days"));
});

test("graph shows an empty state without a doc", () => {
  render(<IntentGraph doc={undefined} busy={false} onSave={vi.fn()} />);
  expect(screen.getByRole("status")).toHaveTextContent("Nothing to draw yet");
});

test("stage colours: reached done, current needs or harbor, later info", () => {
  expect([0, 1, 2, 3].map((i) => stepClass({ stage: "decision2" }, i, 1))).toEqual(["done", "needs", "info", "info"]);
  expect(stepClass({ stage: "working" }, 1, 1)).toBe("harbor");
  expect(stepClass({ stage: "live" }, 3, 3)).toBe("done");
});

test("a person who may not sign sees Send to the signer on the brief", async () => {
  const daniel = { id: "d", name: "Daniel Foo" };
  getThread.mockResolvedValue(thread("decision1", { signoff: { state: "send", signers: [daniel], signer: daniel } }));
  sendForSignature.mockResolvedValue(thread("decision1", { signoff: { state: "waiting", signers: [daniel], signer: daniel } }));
  at("/v3/build/t1");
  fireEvent.click(await screen.findByText("Send to Daniel Foo to confirm"));
  await waitFor(() => expect(sendForSignature).toHaveBeenCalledWith("t1"));
  expect(screen.queryByText("Confirm the brief")).toBeNull();
});

// Nitin, 17 Oct: "the 2 buttons to confirm or to change is not working" (Decision 1 card while Harbor filled the gaps).
test("a greyed Confirm says why next to it, and Change something opens the box", async () => {
  getThread.mockResolvedValue({ ...thread("drafting"), decision: { ...thread("drafting").decision!, gaps: ["Who reads the result"] } });
  at("/v3/build/t1");
  await screen.findByText("Hello there");
  expect(screen.getByRole("button", { name: "Confirm the brief" })).toBeDisabled();
  expect(screen.getByText(/Confirm opens when Harbor has finished updating the brief/)).toBeInTheDocument();
  expect(screen.getByText(/Harbor is working on these now: Who reads the result/)).toBeInTheDocument();
  fireEvent.click(screen.getByText("Change something"));
  expect(screen.getByLabelText("Say something to Harbor")).toHaveFocus();
  expect(screen.getByLabelText("Say something to Harbor")).toHaveAttribute("placeholder", expect.stringMatching(/Say what to change/));
});

test("Confirm with open gaps confirms (Harbor fills at signing) and a failed click shows its error next to the buttons", async () => {
  getThread.mockResolvedValue({ ...thread("decision1"), decision: { ...thread("decision1").decision!, gaps: ["When it is needed"] }, signoff: { state: "can_sign", signers: [] } });
  decide.mockRejectedValueOnce(new Error("We could not reach the service."));
  at("/v3/build/t1");
  await screen.findByText(/Still open: When it is needed\. Confirm and Harbor tries the usual practice/);
  fireEvent.click(screen.getByRole("button", { name: "Confirm the brief" }));
  expect(decide).toHaveBeenCalledWith("t1", 1, "confirm");
  const err = await screen.findByRole("alert");
  expect(err).toHaveTextContent("We could not reach the service.");
  expect(screen.getByLabelText("The intent, drawn as you talk")).toContainElement(err);
});

describe("brief map layout", () => {
  const line = (section: string, index: number, field: string, label: string, value: string) => ({ section, index, field, label, value, changed: false, suggested: false }) as never;
  const mk = (n: number) => {
    const nr = Math.ceil(n * 0.25), nf = Math.ceil(n * 0.25), ns = n - nr - nf;
    return [
      { title: "What you want", lines: [line("w", 0, "line", "Line", "Q"), line("w", 1, "readers", "Readers", "R"), line("w", 2, "needed_by", "By", "Friday")] },
      { title: "Rules", lines: Array.from({ length: nr }, (_, i) => line("r", i, "rule", "Rule", `rule ${i}`)) },
      ...Array.from({ length: nf }, (_, i) => ({ title: `Figure: Fig ${i}`, lines: [line("f", i, "definition", "Def", "d")] })),
      { title: "Where the data comes from", lines: Array.from({ length: Math.max(ns, 0) }, (_, i) => line("s", i, "src", `Source ${i}`, "v")) },
    ] as never;
  };
  it.each([12, 20])("no two boxes intersect with %i nodes", (n) => {
    const nodes = buildNodes(mk(n));
    expect(nodes.length).toBeGreaterThan(n - 1);
    for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) {
      const a = nodes[i]!, b = nodes[j]!;
      expect(Math.abs(a.x - b.x) >= NW || Math.abs(a.y - b.y) >= NH, `${a.id} vs ${b.id}`).toBe(true);
    }
    for (const a of nodes) expect(a.x - NW / 2 >= 0 && a.x + NW / 2 <= W).toBe(true);
  });
});
