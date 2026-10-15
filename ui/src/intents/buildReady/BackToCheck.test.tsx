import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import BackToCheck from "./BackToCheck";

const at = (url: string) => render(<MemoryRouter initialEntries={[url]}><BackToCheck intentId="i1" /></MemoryRouter>);

describe("Back to the check", () => {
  it("shows only after a Fix it link and returns to the check with a recheck", () => {
    at("/centre/intent/i1/define?tab=glossary&back=build-ready");
    expect(screen.getByRole("link", { name: "Back to the check" })).toHaveAttribute("href", "/centre/intent/i1/build-ready?recheck=1");
  });
  it("is absent on an ordinary visit", () => {
    at("/centre/intent/i1/define?tab=glossary");
    expect(screen.queryByRole("link", { name: "Back to the check" })).toBeNull();
  });
});
