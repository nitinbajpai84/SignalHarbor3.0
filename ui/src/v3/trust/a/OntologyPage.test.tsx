import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import OntologyPage, { layout } from "../OntologyPage";
import { json, model, noPack } from "./fixtures";

vi.mock("../../../useSession", () => ({ useSession: () => ({ user: { display_name: "Anita" } }) }));
afterEach(() => vi.unstubAllGlobals());
const page = () => render(<MemoryRouter><OntologyPage /></MemoryRouter>);

test("graph draws every object and its relation; picking one shows its columns", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(model)));
  page();
  await userEvent.click(await screen.findByRole("button", { name: "Commitment, Added by this office" }));
  expect(screen.getByText("commitments.amount_usd")).toBeInTheDocument();
  expect(screen.getByText("worked out: amount_usd - called_to_date")).toBeInTheDocument();
  expect(screen.getByText("commits to")).toBeInTheDocument();
  expect(screen.getByText("hedge_flag")).toBeInTheDocument();
});

test("admit posts the proposal", async () => {
  const f = vi.fn(async (_u: string, init?: RequestInit) => json(init?.method === "POST" ? { ...model, proposals: [] } : model));
  vi.stubGlobal("fetch", f);
  page();
  await userEvent.click(await screen.findByRole("button", { name: "Admit" }));
  await waitFor(() => expect(f.mock.calls.some((c) => String(c[0]).endsWith("/model/proposals/p1"))).toBe(true));
  expect(await screen.findByText("Nothing waiting.")).toBeInTheDocument();
});

test("no pack gives an honest empty state; an error offers a retry", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(noPack)));
  const { unmount } = page();
  expect(await screen.findByText("No industry model yet")).toBeInTheDocument();
  unmount();
  vi.stubGlobal("fetch", vi.fn(async () => json({}, false)));
  page();
  expect(await screen.findByRole("button", { name: "Try again" })).toBeInTheDocument();
});

test("layout is deterministic and orders industry before office before proposed", () => {
  const objs = [...model.objects].reverse();
  const a = layout(objs), b = layout(objs);
  expect(a.sorted.map((o) => o.from)).toEqual(["industry", "office", "proposed"]);
  expect([...a.at.entries()]).toEqual([...b.at.entries()]);
  expect(a.lines).toHaveLength(1);
});
