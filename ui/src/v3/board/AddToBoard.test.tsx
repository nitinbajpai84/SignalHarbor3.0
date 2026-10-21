import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import * as api from "../api";
import AddToBoard from "./AddToBoard";

let roles = ["company_admin"];
vi.mock("../../useSession", () => ({ useSession: () => ({ user: { display_name: "Anita", roles } }) }));
vi.mock("../api", async (orig) => ({ ...(await orig<typeof import("../api")>()), getBoards: vi.fn(), addToBoard: vi.fn() }));

const m = vi.mocked(api);
const row = { pid: "P1", dashboard_id: "d1", title: "Liquidity", use_case: "Capital calls", owner: null, refreshed: null, draft: false, status: "published" };
const at = () => render(<MemoryRouter><AddToBoard figureId="fig-cash" label="Cash" value="4.1m" /></MemoryRouter>);
beforeEach(() => { vi.resetAllMocks(); roles = ["company_admin"]; });

test("a maker picks a board and the figure goes to its draft, with a link to the studio for approval", async () => {
  m.getBoards.mockResolvedValue({ can_edit: true, boards: [row] });
  m.addToBoard.mockResolvedValue({ added: "Cash", kind: "figure", status: "draft", dashboard_id: "d1" });
  at();
  fireEvent.click(screen.getByRole("button", { name: "Add to board" }));
  fireEvent.click(await screen.findByRole("button", { name: "Add to this board" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Someone else has to approve it");
  expect(m.addToBoard).toHaveBeenCalledWith({ pid: "P1", dashboard_id: "d1", figure_id: "fig-cash", label: "Cash", value: "4.1m", text: undefined });
  expect(screen.getByRole("link", { name: "Open it in the studio" })).toHaveAttribute("href", "/centre/build/p/P1/studio?d=d1");
});

test("a refusal is shown in words, and a reader is not offered the button", async () => {
  m.getBoards.mockResolvedValue({ can_edit: true, boards: [row] });
  m.addToBoard.mockRejectedValue(new Error("Only the data team can build dashboards."));
  const { unmount } = at();
  fireEvent.click(screen.getByRole("button", { name: "Add to board" }));
  fireEvent.click(await screen.findByRole("button", { name: "Add to this board" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Only the data team");
  unmount();
  roles = ["participant"];
  at();
  expect(screen.queryByRole("button", { name: "Add to board" })).toBeNull();
});
