import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import DeskPage from "./DeskPage";

vi.mock("../../useSession", () => ({ useSession: () => ({ user: { display_name: "Anita" } }) }));

const desk = {
  needs: [{ kind: "decision", thread: "t1", title: "Liquidity", text: "Go live?", actions: [{ label: "Go live", answer: "go_live" }] }],
  note: null, threads: [{ id: "t1", title: "Liquidity", stage: "decision3", needs: 1 }], files: { arrived: 2, recognised: 2, waiting: 0 },
};
afterEach(() => vi.unstubAllGlobals());
const json = (b: unknown, ok = true) => new Response(JSON.stringify(b), { status: ok ? 200 : 500, headers: { "Content-Type": "application/json" } });
const page = () => render(<MemoryRouter><DeskPage /></MemoryRouter>);

test("a card action posts the decision", async () => {
  const f = vi.fn(async (_u: string, init?: RequestInit) => json(init?.method === "POST" ? {} : desk));
  vi.stubGlobal("fetch", f);
  page();
  await userEvent.click(await screen.findByRole("button", { name: "Go live" }));
  await waitFor(() => expect(f.mock.calls.some((c) => String(c[0]).endsWith("/threads/t1/decide"))).toBe(true));
});

test("a new office points at the welcome page", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json({ needs: [], note: null, threads: [], files: { arrived: 0, recognised: 0, waiting: 0 } })));
  page();
  expect(await screen.findByRole("link", { name: "Set up the office" })).toHaveAttribute("href", "/v3/welcome");
});

test("the desk shows three columns", async () => {
  const d = { ...desk, note: { text: "Cash is steady. More detail.", figures: [{ label: "Cash", value: "1.2m", change: "+1%" }] }, threads: [{ id: "t1", title: "Liquidity", stage: "decision3", needs: 1 }, { id: "t2", title: "Fees", stage: "live", needs: 0 }] };
  vi.stubGlobal("fetch", vi.fn(async () => json(d)));
  page();
  expect(await screen.findByRole("heading", { name: "Good morning, Anita" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Act now" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Liquidity/ })).toHaveAttribute("href", "/v3/build/t1");
  expect(screen.getByRole("heading", { name: "Ready to use" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Go to Consume" })).toHaveAttribute("href", "/v3/consume");
  expect(screen.getByRole("heading", { name: "Overnight" })).toBeInTheDocument();
});

test("an error offers a retry", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json({}, false)));
  page();
  expect(await screen.findByRole("button", { name: "Try again" })).toBeInTheDocument();
});
