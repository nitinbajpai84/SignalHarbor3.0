import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import ConsumePage from "./ConsumePage";
import * as api from "./consumeApi";

vi.mock("../Frame", () => ({ default: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));
vi.mock("../../useSession", () => ({ useSession: () => ({ user: { display_name: "Mei Tan", roles: ["analyst"] } }) }));
vi.mock("../../v1/voice", () => ({ MicButton: () => <button type="button" aria-label="Speak to Lumen" /> }));
vi.mock("./consumeApi", () => ({ getConsume: vi.fn(), askConsume: vi.fn() }));

const m = vi.mocked(api);
const answer = (over: Partial<api.ConsumeAnswer> = {}): api.ConsumeAnswer => ({
  answer: "Cash by entity.", figure: { label: "Cash · all entities · USD", value: "4,463,398.82", change: "" }, trace: [], used: [], cached: true, ms: 3,
  rows: [{ label: "Evergreen Holdings", value: "2,305,906.48" }, { label: "Entity B", value: "905,000.00" }],
  source: "Bank statements and administrator, as at 31 Jul 2026 · run run-77", ...over,
});
const data = (over: Partial<api.ConsumeData> = {}): api.ConsumeData => ({
  office: "Evergreen Office", as_of: "2026-07-31", figures: [{ label: "Total cash", value: "4,463,398.82", change: "", stale: false }],
  watchlist: [{ label: "Fund A", code: "A", value: "142", change: "+0.8% vs last month", stale: false }, { label: "Fund C", code: "C", value: "1,204", change: "", stale: true, dated: "2026-07-28" }],
  boards: [{ id: "d1", title: "Liquidity" }], note: { headline: "Cash steady" }, reports: [{ name: "Run book (Word)", href: "/x" }],
  golden: [{ q: "What is our cash by entity today?" }, { q: "Which entity has the least cash?" }], answer: { q: "What is our cash by entity today?", ...answer() }, ...over,
});
const open = () => render(<MemoryRouter><ConsumePage /></MemoryRouter>);
beforeEach(() => vi.resetAllMocks());

test("opens on the pre-answered question with figure, rows, source and timing; the watchlist shows stale in amber", async () => {
  m.getConsume.mockResolvedValue(data());
  open();
  expect(await screen.findByText("Evergreen Office")).toBeInTheDocument();
  expect(screen.getByText("4,463,398.82")).toBeInTheDocument();
  expect(screen.getByText("2,305,906.48").closest("details")).not.toHaveAttribute("open");  // the rows sit behind the sentence, folded
  expect(screen.getByText("Show the figures")).toBeInTheDocument();
  expect(screen.getByText(/Source: Bank statements and administrator, as at 31 Jul 2026/)).toBeInTheDocument();
  expect(screen.getByText("Answered in 3 ms (from memory)")).toBeInTheDocument();
  expect(screen.getByLabelText("Fund C")).toHaveClass("stale");
  expect(screen.getByText("Not available yet")).toBeInTheDocument();
  expect(screen.getByText("Cash steady")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Liquidity|Board thumbnail/ })).toHaveAttribute("href", "/v3/board");
  expect(screen.getByRole("button", { name: "Download PDF" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Excel" })).toBeInTheDocument();
  expect(screen.getByRole("navigation", { name: "Consume tabs" })).toHaveTextContent("AskBoardsNoteReports");
});

test("asking runs the question and a follow-up chip asks again", async () => {
  m.getConsume.mockResolvedValue(data());
  m.askConsume.mockResolvedValue(answer({ figure: { label: "Least cash · Entity B · USD", value: "905,000.00", change: "" } }));
  open();
  fireEvent.change(await screen.findByRole("textbox", { name: "Ask anything about the numbers" }), { target: { value: "Which entity has the least cash?" } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
  expect(await screen.findByText("Least cash · Entity B · USD")).toBeInTheDocument();
  expect(m.askConsume).toHaveBeenCalledWith("Which entity has the least cash?");
  expect(screen.getByRole("button", { name: "What is our cash by entity today?" })).toBeInTheDocument();
});

test("an empty company says a use case goes live in Build; a failed read can be retried", async () => {
  m.getConsume.mockResolvedValueOnce(data({ as_of: null, figures: [], watchlist: [], boards: [], note: null, reports: [], golden: [], answer: null }));
  const { unmount } = open();
  expect(await screen.findByText("Nothing to read yet; a use case goes live in Build.")).toBeInTheDocument();
  unmount();
  m.getConsume.mockRejectedValueOnce(new Error("Consume could not be read.")).mockResolvedValueOnce(data());
  open();
  expect(await screen.findByRole("alert")).toHaveTextContent("Consume could not be read.");
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByLabelText("Fund A")).toBeInTheDocument();
});

test("an answer that came from a figure links to where the number comes from", async () => {
  m.getConsume.mockResolvedValue(data({ answer: { q: "q", ...answer({ figure: { label: "Cash", value: "1", change: "", id: "fig-cash", name: "Cash by entity", v: 2 } }) } }));
  open();
  expect(await screen.findByRole("link", { name: "Where this number comes from" })).toHaveAttribute("href", "/v3/knowledge/figures/fig-cash");
});

test("no figure id, no link", async () => {
  m.getConsume.mockResolvedValue(data());
  open();
  await screen.findByText("Evergreen Office");
  expect(screen.queryByRole("link", { name: "Where this number comes from" })).toBeNull();
});

test("a named headline shows what the number is, with the number big", async () => {
  m.getConsume.mockResolvedValue(data({ answer: { q: "q", ...answer({ figure: { label: "Called to date and unfunded · Evergreen Holdings · Cedarpoint Ventures III · USD", value: "Commitment for Cedarpoint Ventures III: 10,000,000", change: "" } }) } }));
  open();
  expect(await screen.findByText("Commitment for Cedarpoint Ventures III:")).toHaveClass("v3c-name");
  expect(screen.getByText("10,000,000")).toHaveClass("v3c-big");
});

test("a maker can add the answer's figure to a board and reach the boards list", async () => {
  m.getConsume.mockResolvedValue(data());
  open();
  expect(await screen.findByRole("button", { name: "Add to board" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "All boards, owners and drafts" })).toHaveAttribute("href", "/v3/consume/boards");
});
