import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import OffersSection from "./OffersSection";

const OFFERS = {
  intent_id: "int_1", line: null, can_answer: true,
  offers: [{ id: "fx_rates", kind: "FX rates", title: "FX rates feed: with it you would also get",
    unlocks: [{ code: "K02", name: "Reported-value evidence coverage", in_sow: true }],
    must_contain: [{ name: "currency", label: "currency", type: "varchar" }, { name: "sgd_per_unit", label: "sgd per unit", type: "double" }] }],
};
const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status, headers: { "Content-Type": "application/json" } });

afterEach(() => vi.unstubAllGlobals());

it("shows the offer and answers We have it", async () => {
  const fetch = vi.fn(async (url: string, init?: RequestInit) => init?.method === "POST" ? json({ intent_id: "int_1", sow: { version: 3 } }) : json(OFFERS));
  vi.stubGlobal("fetch", fetch);
  render(<MemoryRouter><OffersSection /></MemoryRouter>);
  expect(await screen.findByText("FX rates feed: with it you would also get")).toBeInTheDocument();
  expect(screen.getByText("It must contain: currency, sgd per unit.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "We have it" }));
  expect(await screen.findByText(/back to draft at version 3/)).toBeInTheDocument();
  expect(fetch.mock.calls.some(([u]) => u === "/api/v1/consume/offers/fx_rates/have")).toBe(true);
});

it("hides the answer from a reader who is not the decision maker", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json({ ...OFFERS, can_answer: false })));
  render(<MemoryRouter><OffersSection /></MemoryRouter>);
  expect(await screen.findByText("FX rates feed: with it you would also get")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "We have it" })).toBeNull();
});
