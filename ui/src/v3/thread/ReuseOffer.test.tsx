import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { expect, test, vi } from "vitest";

import type { ReuseOffer as Offer } from "../api";
import ReuseOffer from "./ReuseOffer";

const o: Offer = { figure_id: "fig-cash", name: "Cash by entity", built_from: { kind: "recipe", id: "cash_break" }, verified_runs: 3, first_used_by: "Daniel Foo", suggest: true };

test("reads the offer and records Use and Keep my own", () => {
  const seen = vi.fn();
  const Host = () => { const [v, set] = useState<Record<string, string | null>>({}); seen(v); return <ReuseOffer offers={[o]} value={v} onChange={set} />; };
  render(<Host />);
  expect(screen.getByText("Use Cash by entity (verified, run 3 times, first used by Daniel Foo)?")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Use" }));
  expect(seen).toHaveBeenLastCalledWith({ "fig-cash": "fig-cash" });
  fireEvent.click(screen.getByRole("button", { name: "Keep my own" }));
  expect(seen).toHaveBeenLastCalledWith({ "fig-cash": null });
});

test("nothing renders without offers", () => {
  const { container } = render(<ReuseOffer offers={[]} value={{}} onChange={() => undefined} />);
  expect(container).toBeEmptyDOMElement();
});
