import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";

import type { SignalNeed, SignalRow } from "../api";
import SignalsPage from "../knowledge/SignalsPage";
import DraftCard from "./DraftCard";
import SignalCard from "./SignalCard";

const actSignal = vi.fn();
const listSignals = vi.fn();
const listFired = vi.fn();
const listDrafts = vi.fn();
const admitDraft = vi.fn();
const rejectDraft = vi.fn();
const editDraft = vi.fn();
vi.mock("../api", () => ({
  actSignal: (...a: unknown[]) => actSignal(...a), listSignals: () => listSignals(), listFired: () => listFired(), listDrafts: () => listDrafts(),
  admitDraft: (...a: unknown[]) => admitDraft(...a), rejectDraft: (...a: unknown[]) => rejectDraft(...a), editDraft: (...a: unknown[]) => editDraft(...a),
}));
vi.mock("../Frame", () => ({ default: ({ children }: { children: ReactNode }) => <div>{children}</div> }));
beforeEach(() => { vi.clearAllMocks(); listDrafts.mockResolvedValue([]); });

const held: SignalNeed = {
  kind: "signal", id: "sg-1", signal: "uc01-bank-changed", title: "Bank details changed", text: "The account for Cedarpoint changed from 2209 to 4471.", severity: "problem",
  role: "ops_lead", person: "grace@x.test", hold: { blocks: "prepare_payment", scope: "Cedarpoint", until: "you confirm the call-back" },
  evidence: [
    { kind: "document", field: "bank_account", value: "4471", file: "call7.pdf", page: 2, quote: "Wire to account 4471" },
    { kind: "figure", id: "standing_instructions", value: { account: "2209" }, v: 3 },
    { kind: "rule", id: "changed_bank_details", value: {}, text: "Call back before paying a new account" },
  ],
  actions: [{ label: "Record call-back", answer: "Record call-back" }, { label: "Not right", answer: "dismiss" }],
};
const card = (n: SignalNeed = held) => render(<MemoryRouter><SignalCard card={n} onDone={onDone} /></MemoryRouter>);
const onDone = vi.fn();

test("a held card shows the hold, asks for a note, then acts with it", async () => {
  actSignal.mockResolvedValue({});
  card();
  expect(screen.getByText(/Held: payment for Cedarpoint until you confirm the call-back/)).toBeInTheDocument();
  expect(screen.getByText(/For you because you are the ops lead/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Record call-back" }));
  const go = screen.getByRole("button", { name: "Record call-back" });
  expect(go).toBeDisabled();
  await userEvent.type(screen.getByLabelText(/Who did you speak to/), "Spoke to Ann at 10:00");
  await userEvent.click(go);
  await waitFor(() => expect(actSignal).toHaveBeenCalledWith("sg-1", { choice: "Record call-back", note: "Spoke to Ann at 10:00" }));
  expect(onDone).toHaveBeenCalled();
});

test("a card without a hold acts at once, and Not right dismisses", async () => {
  actSignal.mockResolvedValue({});
  card({ ...held, hold: null, severity: "needs" });
  expect(screen.queryByText(/Held:/)).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Record call-back" }));
  expect(actSignal).toHaveBeenCalledWith("sg-1", { choice: "Record call-back" });
  await userEvent.click(screen.getByRole("button", { name: "Not right" }));
  expect(actSignal).toHaveBeenLastCalledWith("sg-1", { dismiss: true });
});

test("the evidence starts closed and opens with figures, quotes and the rule", async () => {
  card();
  expect(screen.queryByText("Wire to account 4471")).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Show the evidence" }));
  expect(screen.getByText("Wire to account 4471")).toBeInTheDocument();
  expect(screen.getByText(/page 2/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Standing instructions" })).toHaveAttribute("href", "/v3/knowledge/figures/standing_instructions");
  expect(screen.getByText("Call back before paying a new account")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Hide the evidence" }));
  expect(screen.queryByText("Wire to account 4471")).toBeNull();
});

test("a refused act shows the plain message", async () => {
  actSignal.mockRejectedValue(new Error("Write down who you spoke to and when."));
  card({ ...held, hold: null });
  await userEvent.click(screen.getByRole("button", { name: "Record call-back" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Write down who you spoke to");
});

test("the signals page lists each signal with its record and what fired lately", async () => {
  const row = (o: Partial<SignalRow>): SignalRow => ({
    id: "uc01-bank-changed", title: "Bank details changed", trigger: { on: "file_arrived", kind: "capital_call_notice" }, severity: "problem", route_to: "ops_lead", role_title: "Operations lead",
    action: { verb: "call_back" }, hold: null, suggestion: true, stats: { fired: 4, acted: 3, dismissed: 1, open: 0, hit_rate: 0.75, last_fired: "2026-10-16" }, ...o });
  listSignals.mockResolvedValue([row({}), row({ id: "b", title: "Cash is short", suggestion: false, trigger: { on: "run" } })]);
  listFired.mockResolvedValue([{ id: "sg-1", signal: "a", title: "Bank details changed", subject: "Cedarpoint call 7", severity: "problem", route_to: "ops_lead", status: "acted", at: "2026-10-16T08:00:00", by: "Grace Ong", message: "m", hold: null, evidence: [] }]);
  render(<MemoryRouter><SignalsPage /></MemoryRouter>);
  expect(await screen.findByText("When a capital call notice arrives")).toBeInTheDocument();
  expect(screen.getByText("Suggested")).toBeInTheDocument();
  expect(screen.getByText("Your office")).toBeInTheDocument();
  expect(screen.getAllByText("Fired 4, acted on 3, marked not right 1")).toHaveLength(2);
  expect(screen.getAllByText("Operations lead")).toHaveLength(2);
  expect(await screen.findByText(/^Done.*Grace Ong/)).toBeInTheDocument();
  expect(screen.getByText("Cedarpoint call 7")).toBeInTheDocument();
});

const draft = {
  id: "sd-1", status: "waiting", noticed: "Harbor noticed Grace checks bank details before every payment. Watch for it automatically?", needs: [], repeats: 2, evidence: [],
  signal: { title: "Bank details differ from the standing instructions", message: "Check the bank details first.", route_to: "ops_lead", condition: "x", trigger: { on: "file_arrived" } },
  backtest: { count: 3, checked: 9, examples: [], line: "Would have fired 3 times in 6 months: Cedarpoint call 7." },
};

test("Suggested by Harbor shows each draft with its backtest, and Admit, Edit and Reject work", async () => {
  listSignals.mockResolvedValue([]);
  listFired.mockResolvedValue([]);
  listDrafts.mockResolvedValue([draft]);
  admitDraft.mockResolvedValue({});
  editDraft.mockResolvedValue({});
  rejectDraft.mockResolvedValue({});
  render(<MemoryRouter><SignalsPage /></MemoryRouter>);
  expect(await screen.findByText("Suggested by Harbor")).toBeInTheDocument();
  expect(screen.getByText(/Harbor noticed Grace checks bank details/)).toBeInTheDocument();
  expect(screen.getByText("Would have fired 3 times in 6 months: Cedarpoint call 7.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Admit" }));
  expect(admitDraft).toHaveBeenCalledWith("sd-1");
  await userEvent.click(screen.getByRole("button", { name: "Edit" }));
  await userEvent.clear(screen.getByLabelText("What the card says"));
  await userEvent.type(screen.getByLabelText("What the card says"), "Call the bank first.");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(editDraft).toHaveBeenCalledWith("sd-1", { title: "Bank details differ from the standing instructions", message: "Call the bank first." });
  await userEvent.click(screen.getByRole("button", { name: "Reject" }));
  expect(rejectDraft).toHaveBeenCalledWith("sd-1");
});

test("a draft that still needs a rule says so, and a refused admit shows the plain message", async () => {
  listSignals.mockResolvedValue([]);
  listFired.mockResolvedValue([]);
  listDrafts.mockResolvedValue([{ ...draft, needs: ["I cannot tell what limit you use."] }]);
  admitDraft.mockRejectedValue(new Error("I still need the limit signed as an office rule before I can watch for this."));
  render(<MemoryRouter><SignalsPage /></MemoryRouter>);
  expect(await screen.findByText("I cannot tell what limit you use.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Admit" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("limit signed");
});

test("on the Action list the draft is a card for the decision maker", () => {
  render(<DraftCard id="sd-1" noticed={draft.noticed} title="T" message="M" backtest={draft.backtest.line} needs={[]} onDone={onDone} />);
  expect(screen.getByRole("article", { name: "T" })).toBeInTheDocument();
});
