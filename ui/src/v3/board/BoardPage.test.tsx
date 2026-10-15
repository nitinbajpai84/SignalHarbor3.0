import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import * as api from "../api";
import AnswerPage from "./AnswerPage";
import BoardPage from "./BoardPage";
import NotePage from "./NotePage";

vi.mock("../Frame", () => ({ default: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));
vi.mock("../../v1/cxui/TileCard", () => ({ default: ({ tile, pid, did }: { tile: { title: string }; pid: string; did: string }) => <article aria-label={tile.title}>{pid}/{did}</article> }));
vi.mock("../api", () => ({ getBoard: vi.fn(), ask: vi.fn(), getNote: vi.fn(), getLanguage: vi.fn() }));

const m = vi.mocked(api);
const at = (ui: React.ReactElement, path = "/") => render(<MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>);
const board = (over: Partial<api.Board> = {}): api.Board => ({
  title: "Liquidity", as_at: "2026-10-13T06:00:00Z",
  figures: [{ label: "Cash", value: "4.14m", change: "-0.2m", source: "Run run-77 of Capital calls" } as api.Figure],
  tiles: [{ id: "t-1", title: "Cash by entity", spec: {}, project_id: "EV-0003", dashboard_id: "dash-1" }], ...over,
});
beforeEach(() => { vi.resetAllMocks(); m.getLanguage.mockResolvedValue({ words: [], corrections: [], golden: [{ q: "What is our cash?", a: "", by: "Anita" }], taught: [] }); });

test("the board shows its figures with the source on hover, its tiles, and answers a question with its trace and Used line", async () => {
  m.getBoard.mockResolvedValue(board());
  m.ask.mockResolvedValue({ answer: "Cash is 4.14m.", trace: [{ kind: "guard", label: "Checked every number against the data" }], used: ["Used: Span playbook, passage 2"] });
  at(<BoardPage />);
  expect(screen.getByRole("status")).toHaveTextContent("Opening the board");
  expect(await screen.findByRole("heading", { name: "Liquidity" })).toBeInTheDocument();
  expect(screen.getByTitle("Where this is from: Run run-77 of Capital calls")).toHaveTextContent("4.14m");
  expect(screen.getByLabelText("Cash by entity")).toHaveTextContent("EV-0003/dash-1");
  fireEvent.change(screen.getByRole("textbox", { name: "Ask about this board" }), { target: { value: "Why did cash fall?" } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
  expect(await screen.findByText("Cash is 4.14m.")).toBeInTheDocument();
  expect(screen.getByText("Checked every number against the data")).toBeInTheDocument();
  expect(screen.getByText("Used: Span playbook, passage 2")).toBeInTheDocument();
  expect(m.ask).toHaveBeenCalledWith("Why did cash fall?");
});

test("an empty board says what brings one, and a failed read offers another try", async () => {
  m.getBoard.mockResolvedValueOnce(board({ title: "", figures: [], tiles: [] }));
  const { unmount } = at(<BoardPage />);
  expect(await screen.findByText("No board yet")).toBeInTheDocument();
  unmount();
  m.getBoard.mockRejectedValueOnce(new Error("The board could not be read.")).mockResolvedValueOnce(board());
  at(<BoardPage />);
  expect(await screen.findByRole("alert")).toHaveTextContent("The board could not be read.");
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByRole("heading", { name: "Liquidity" })).toBeInTheDocument();
});

test("the ask page asks the question in the address and offers the office's saved questions; an error can be retried", async () => {
  m.ask.mockRejectedValueOnce(new Error("I could not answer that just now.")).mockResolvedValueOnce({ answer: "13.1m is uncalled.", trace: [], used: [] });
  at(<AnswerPage />, "/v3/ask?q=Dry%20powder%3F");
  expect(await screen.findByRole("alert")).toHaveTextContent("I could not answer that just now.");
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByText("13.1m is uncalled.")).toBeInTheDocument();
  await waitFor(() => expect(screen.getByRole("button", { name: "What is our cash?" })).toBeInTheDocument());
});

test("the note lists its figures and past notes, and has an empty state", async () => {
  m.getNote.mockResolvedValueOnce({ text: "Nothing is due in 30 days.", figures: [{ label: "Cash", value: "4.14m", change: "" }], history: [{ at: "2026-10-13", headline: "Cash steady" }] });
  const { unmount } = at(<NotePage />);
  expect(await screen.findByText("Nothing is due in 30 days.")).toBeInTheDocument();
  expect(screen.getByText("Cash steady")).toBeInTheDocument();
  expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
  unmount();
  m.getNote.mockResolvedValueOnce({ text: "", figures: [], history: [] });
  at(<NotePage />);
  expect(await screen.findByText(/There is no note yet/)).toBeInTheDocument();
});
