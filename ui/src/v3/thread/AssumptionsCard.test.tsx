import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import AssumptionsCard, { sourceWords } from "./AssumptionsCard";

test("groups by figure, words the source, folds after five", () => {
  const a = Array.from({ length: 7 }, (_, i) => ({ figure: "Cash break", text: `Line ${i}`, source: "ASSUMPTIONS A5" }));
  render(<AssumptionsCard assumptions={[...a, { figure: "Exposure", text: "Harbor line", source: "Harbor (two models agreed)" }]} />);
  expect(screen.getByRole("heading", { name: "Cash break" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Exposure" })).toBeInTheDocument();
  expect(screen.queryByText("Line 5")).toBeNull();
  expect(screen.getByText("Harbor (two checks agreed)")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Show 2 more" }));
  expect(screen.getByText("Line 6")).toBeInTheDocument();
  expect(sourceWords("loader")).toBe("From your bank files");
  expect(sourceWords("ASSUMPTIONS A5")).toBe("Office rule A5");
});

test("nothing without assumptions", () => {
  const { container } = render(<AssumptionsCard assumptions={[]} />);
  expect(container).toBeEmptyDOMElement();
});
