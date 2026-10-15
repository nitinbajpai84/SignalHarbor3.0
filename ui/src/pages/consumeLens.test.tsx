import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import ConsumeCentre from "./ConsumeCentre";
import LensPage from "./LensPage";
import { ContextCard } from "./ContextCard";

const LENSES = { lenses: [{ key: "risk", name: "Risk", counts: { measures: 5, outside: 1, briefs: 2, building: 1, proving: 0, consider: 1 } }] };
const DETAIL = { key: "risk", name: "Risk", briefs: [{ id: "b1", title: "Private-market calls", summary: "s", source: "Desk note", measure_moves: [{ code: "K12", name: "Custody lag" }] }],
  feeds: [], building: [{ id: "ini-1", title: "Valuation evidence chase", href: "/centre/intent/ini-1", stage: "Proving", verdict: "Too early" }], consider: [] };

function serve(bodies: Record<string, unknown>) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify(bodies[url.split("?")[0]!] ?? {}), { status: 200, headers: { "Content-Type": "application/json" } })));
}
afterEach(() => vi.unstubAllGlobals());

it("shows four business view tiles with counts and the Tools row", async () => {
  serve({ "/api/company/consume/lenses": LENSES, "/api/company/feeds": { measures: [] }, "/api/company/market": { briefs: [] }, "/api/company/whatif/scenarios": { scenarios: [] } });
  render(<MemoryRouter><ConsumeCentre /></MemoryRouter>);
  expect(await screen.findByText("1 outside their usual range")).toHaveClass("ds-room__count--amber");
  expect(screen.getByRole("link", { name: "Open Risk" })).toHaveAttribute("href", "/centre/consume/lens/risk");
  expect(screen.getByRole("region", { name: "Tools" })).toBeInTheDocument();
  expect(screen.getAllByText(/no measure assigned to this view/).length).toBe(3);
});

it("lens page keeps outside material labelled and shows the building strip with a verdict", async () => {
  serve({ "/api/company/consume/lenses/risk": DETAIL });
  render(<MemoryRouter initialEntries={["/centre/consume/lens/risk"]}><Routes><Route path="/centre/consume/lens/:lens" element={<LensPage />} /></Routes></MemoryRouter>);
  expect(await screen.findByText("Outside material")).toBeInTheDocument();
  expect(screen.getByText("Too early")).toBeInTheDocument();
  expect(screen.getByText("Nothing suggested for this view yet.")).toBeInTheDocument();
});

it("context card: only the person the server names can confirm; others read", () => {
  const card = { table: "gold.k12", state: "draft" as const, lines: { meaning: { text: "Stale means a quarter.", mark: "guessed" as const } }, can: { confirm: false, edit: false, dispute: false } };
  const { unmount } = render(<MemoryRouter><ContextCard card={card} onChanged={() => undefined} /></MemoryRouter>);
  expect(screen.getByText("Draft")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Confirm this card" })).toBeNull();
  unmount();
  render(<MemoryRouter><ContextCard card={{ ...card, can: { confirm: true, edit: true, dispute: true } }} onChanged={() => undefined} /></MemoryRouter>);
  fireEvent.click(screen.getByRole("button", { name: "This is wrong" }));
  expect(screen.getByRole("button", { name: "Send it back to the Architect" })).toBeDisabled();
});
