import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import * as api from "../api";
import BoardsPage from "./BoardsPage";

vi.mock("../Frame", () => ({ default: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));
vi.mock("../api", async (orig) => ({ ...(await orig<typeof import("../api")>()), getBoards: vi.fn() }));

const m = vi.mocked(api);
const open = () => render(<MemoryRouter><BoardsPage /></MemoryRouter>);
beforeEach(() => vi.resetAllMocks());

test("lists each board with use case, owner, last refresh and whether a change waits; editors get an Edit link", async () => {
  m.getBoards.mockResolvedValue({ can_edit: true, boards: [
    { pid: "P1", dashboard_id: "d1", title: "Liquidity", use_case: "Capital calls", owner: "Anita Rao", refreshed: "2026-10-13T06:00:00Z", draft: true, status: "submitted" },
    { pid: "P2", dashboard_id: "d2", title: "Fees", use_case: "Fee check", owner: null, refreshed: null, draft: false, status: "published" }] });
  open();
  expect(await screen.findByRole("link", { name: "Liquidity" })).toHaveAttribute("href", "/v3/board?pid=P1");
  expect(screen.getByText("Anita Rao")).toBeInTheDocument();
  expect(screen.getByText("Waiting for approval")).toBeInTheDocument();
  expect(screen.getAllByRole("link", { name: "Edit" })[0]).toHaveAttribute("href", "/centre/build/p/P1/studio?d=d1");
  expect(screen.getByText("Not named")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "See the data model" })).toHaveAttribute("href", "/v3/trust/model");
});

test("a reader sees no Edit link and an empty office says what brings a board", async () => {
  m.getBoards.mockResolvedValueOnce({ can_edit: false, boards: [{ pid: "P1", dashboard_id: "d1", title: "Liquidity", use_case: "Capital calls", owner: null, refreshed: null, draft: false, status: "published" }] });
  const { unmount } = open();
  await screen.findByRole("link", { name: "Liquidity" });
  expect(screen.queryByRole("link", { name: "Edit" })).toBeNull();
  unmount();
  m.getBoards.mockResolvedValueOnce({ can_edit: false, boards: [] });
  open();
  expect(await screen.findByText(/No board is published yet/)).toBeInTheDocument();
});
