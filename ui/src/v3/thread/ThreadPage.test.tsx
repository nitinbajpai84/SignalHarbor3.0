import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";

import { ApiError } from "../../api/client";
import type { Stage, Thread } from "../api";
import ThreadPage from "./ThreadPage";

const getThread = vi.fn();
const say = vi.fn();
const decide = vi.fn();
const editBrief = vi.fn();
const sendForSignature = vi.fn();
vi.mock("../api", () => ({
  editBrief: (...a: unknown[]) => editBrief(...a),
  getThread: (i: string) => getThread(i),
  say: (...a: unknown[]) => say(...a),
  decide: (...a: unknown[]) => decide(...a),
  sendForSignature: (...a: unknown[]) => sendForSignature(...a),
}));
vi.mock("../Frame", () => ({ default: ({ children }: { children: ReactNode }) => <div>{children}</div> }));

const base = (stage: Stage, over: Partial<Thread> = {}): Thread => ({
  id: "t1", title: "Liquidity", stage, needs: 0, asked: 0, harbor_steps: 0, decision: null,
  events: [
    { at: "1 Oct", kind: "person", text: "Hello there", by: "Anita" },
    { at: "1 Oct", kind: "chips", chips: ["Read 5 files", "Mapped 41 columns"] },
  ],
  ...over,
});
const show = (t: Thread) => {
  getThread.mockResolvedValue(t);
  return render(
    <MemoryRouter initialEntries={["/v3/thread/t1"]}>
      <Routes><Route path="/v3/thread/:id" element={<ThreadPage />} /></Routes>
    </MemoryRouter>,
  );
};

beforeEach(() => {
  vi.clearAllMocks();
  decide.mockResolvedValue(base("working"));
  say.mockResolvedValue(base("decision1"));
});

test("drafting shows the timeline, chips and a spinner message", async () => {
  show(base("drafting"));
  await screen.findByText("Hello there");
  expect(screen.getByText("Read 5 files")).toBeInTheDocument();
  expect(screen.getByRole("status")).toBeInTheDocument();
});

test("decision1 confirms and can say a change", async () => {
  show(base("decision1", { decision: { n: 1, title: "", brief: { question: "Can we meet calls?", files: ["Bank", "Custodian"], read_by: "Mei", refresh: "Monthly", cases_when: "Cash short" } } }));
  await screen.findByText("Can we meet calls?");
  fireEvent.click(screen.getByText("Change something"));
  expect(screen.getByLabelText("Say something to Harbor")).toHaveFocus();
  fireEvent.change(screen.getByLabelText("Say something to Harbor"), { target: { value: "use 90 days" } });
  fireEvent.click(screen.getByText("Send"));
  expect(say).toHaveBeenCalledWith("t1", "use 90 days");
});

test("decision1 confirm sends decide n=1 confirm", async () => {
  show(base("decision1", { decision: { n: 1, title: "", brief: { question: "Q?", files: [], read_by: "Mei", refresh: "Monthly", cases_when: "x" } } }));
  fireEvent.click(await screen.findByText("Confirm"));
  await waitFor(() => expect(decide).toHaveBeenCalledWith("t1", 1, "confirm"));
});

test("working lists steps from chips", async () => {
  show(base("working"));
  await screen.findByText(/Nothing needed from you/);
  expect(screen.getByRole("list", { name: "Working steps" })).toHaveTextContent("Mapped 41 columns");
  expect(screen.getByText("Stop")).toBeInTheDocument();
  expect(screen.getByText("See the technical detail")).toBeInTheDocument();
});

test("decision2 preselects the assumed answer and carries on with answers", async () => {
  show(base("decision2", {
    decision: {
      n: 2, title: "",
      files: [{ name: "bank.csv", read_as: "Bank balances", goes_to: "Cash", state: "reused", confidence: "high" }],
      questions: [{ id: "q1", text: "Booked?", options: ["No", "Yes"], assumed: "No" }],
    },
  }));
  await screen.findByText("bank.csv");
  expect(screen.getByText("high")).toBeInTheDocument();
  expect(screen.getByText("No")).toHaveAttribute("aria-pressed", "true");
  fireEvent.click(screen.getByText("Yes"));
  fireEvent.click(screen.getByText("This is right, carry on"));
  expect(decide).toHaveBeenCalledWith("t1", 2, "carry_on", { q1: "Yes" });
});

test("decision3 shows checks and go live / not yet", async () => {
  show(base("decision3", { decision: { n: 3, title: "", checks: [{ label: "Cash A", value: "100", ok: true, note: "" }] } }));
  await screen.findByText("Cash A");
  fireEvent.click(screen.getByText("Go live"));
  await waitFor(() => expect(decide).toHaveBeenCalledWith("t1", 3, "go_live"));
});

test("decision3 not yet", async () => {
  show(base("decision3", { decision: { n: 3, title: "", checks: [{ label: "Cash A", value: "100", ok: true, note: "" }] } }));
  fireEvent.click(await screen.findByText("Not yet"));
  await waitFor(() => expect(decide).toHaveBeenCalledWith("t1", 3, "not_yet"));
});

test("live links to board and files", async () => {
  show(base("live", { next_run: "3 Nov" }));
  await screen.findByText("Next run: 3 Nov");
  expect(screen.getByText("Board")).toHaveAttribute("href", "/v3/board");
  expect(screen.getByText("Files")).toHaveAttribute("href", "/v3/files");
});

test("question retries", async () => {
  show(base("question", { events: [{ at: "x", kind: "question", text: "File was empty" }] }));
  await screen.findAllByText("File was empty");
  fireEvent.click(screen.getByText("Retry"));
  await waitFor(() => expect(decide).toHaveBeenCalledWith("t1", 1, "retry"));
});

test("404 and error states", async () => {
  getThread.mockRejectedValue(new ApiError("nope", 404));
  const { unmount } = render(<MemoryRouter><ThreadPage /></MemoryRouter>);
  await screen.findByText(/could not find this thread/);
  unmount();
  getThread.mockRejectedValue(new ApiError("Server down", 500));
  render(<MemoryRouter><ThreadPage /></MemoryRouter>);
  await screen.findByText("Server down");
});

test("decision1 brief: every line has its own edit and saves that line", async () => {
  const line = { section: "goal", index: null, field: "readers", label: "Read by", value: "Mei", suggested: false };
  editBrief.mockResolvedValue(base("decision1", { decision: { n: 1, title: "", brief: { question: "Q", files: [], read_by: "Mei, Daniel", refresh: "", cases_when: "",
    doc: [{ title: "What you want", lines: [{ ...line, value: "Mei, Daniel" }] }] } } }));
  show(base("decision1", { decision: { n: 1, title: "", brief: { question: "Q", files: [], read_by: "Mei", refresh: "", cases_when: "",
    doc: [{ title: "What you want", lines: [line, { ...line, field: "needed_by", label: "When it is needed", value: "" }] }] } } }));
  expect(await screen.findByText("Not said yet")).toBeInTheDocument();
  fireEvent.click(screen.getByLabelText("Edit Read by"));
  fireEvent.change(screen.getByLabelText("Change Read by"), { target: { value: "Mei, Daniel" } });
  fireEvent.click(screen.getByText("Save"));
  await waitFor(() => expect(editBrief).toHaveBeenCalledWith("t1", line, "Mei, Daniel"));
  expect(await screen.findByText("Mei, Daniel")).toBeInTheDocument();
});

const brief = { question: "Q?", files: [], read_by: "Mei", refresh: "Monthly", cases_when: "x" };
const daniel = { id: "d", name: "Daniel Foo" };

test("a person who may not sign gets Send to the signer, not Confirm", async () => {
  sendForSignature.mockResolvedValue(base("decision1"));
  show(base("decision1", { decision: { n: 1, title: "", brief }, signoff: { state: "send", signers: [daniel], signer: daniel } }));
  fireEvent.click(await screen.findByText("Send to Daniel Foo to confirm"));
  await waitFor(() => expect(sendForSignature).toHaveBeenCalledWith("t1"));
  expect(screen.queryByText("Confirm")).toBeNull();
});

test("after sending, the raiser sees waiting for the signer and no Confirm", async () => {
  show(base("decision1", { decision: { n: 1, title: "", brief }, signoff: { state: "waiting", signers: [daniel], signer: daniel, mine: true } }));
  expect(await screen.findByText(/Waiting for Daniel Foo to confirm/)).toBeInTheDocument();
  expect(screen.queryByText("Confirm")).toBeNull();
});

test("decision1 with a reuse offer sends the choice in the reuse map", async () => {
  const brief = { question: "q", files: ["a.csv"], read_by: "x", refresh: "daily", cases_when: "never" };
  show(base("decision1", { decision: { n: 1, title: "t", brief }, reuse: [{ figure_id: "fig-cash", name: "Cash by entity", built_from: { kind: "recipe", id: "c" }, verified_runs: 3, first_used_by: "Daniel Foo", suggest: true }] }));
  fireEvent.click(await screen.findByRole("button", { name: "Use" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
  await waitFor(() => expect(decide).toHaveBeenCalledWith("t1", 1, "confirm", undefined, { "fig-cash": "fig-cash" }));
});

test("Retry on a question asks the server to retry (17 Oct: after a restart it answered 409)", async () => {
  show(base("question", { events: [{ at: "1 Oct", kind: "question", text: "I was interrupted while working (the app restarted)." }] }));
  fireEvent.click(await screen.findByRole("button", { name: "Retry" }));
  expect(decide).toHaveBeenCalledWith("t1", 1, "retry");
});

test("while the brief is updating, the greyed Confirm says why next to it", async () => {
  show(base("drafting", { decision: { n: 1, title: "", gaps: ["When"], brief: { question: "Can we meet calls?", files: [], read_by: "", refresh: "", cases_when: "" } } }));
  expect(await screen.findByRole("button", { name: "Confirm" })).toBeDisabled();
  expect(screen.getByText(/Confirm opens when Harbor has finished updating the brief/)).toBeInTheDocument();
});
