import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import QuestionBlock from "./QuestionBlock";

test("a disagreement offers both answers and Something else, which opens the composer", () => {
  const pick = vi.fn(), els = vi.fn();
  render(<QuestionBlock q={{ id: "judge:k", text: "Which?", options: ["in (A)", "out (B)", "Something else, I will say"] }} onPick={pick} onElse={els} />);
  expect(screen.getByText("I am not sure, two checks disagree")).toBeInTheDocument();
  fireEvent.click(screen.getByText("out (B)"));
  expect(pick).toHaveBeenCalledWith("out (B)");
  fireEvent.click(screen.getByText("Something else, I will say"));
  expect(els).toHaveBeenCalled();
});

test("a document line shows the quote and where it is", () => {
  const pick = vi.fn();
  render(<QuestionBlock q={{ id: "doc:x.pdf", text: "Which line?", options: ['"NAV: USD 5" (page 3)', "Keep it as context only"] }} onPick={pick} />);
  expect(screen.getByText("NAV: USD 5")).toBeInTheDocument();
  expect(screen.getByText("page 3")).toBeInTheDocument();
  fireEvent.click(screen.getByText("Use this line"));
  expect(pick).toHaveBeenCalledWith('"NAV: USD 5" (page 3)');
  fireEvent.click(screen.getByText("Keep as context only"));
  expect(pick).toHaveBeenCalledWith("Keep it as context only");
});

test("a plain question is unchanged", () => {
  render(<QuestionBlock q={{ id: "q1", text: "Which?", options: ["Yes", "No"], assumed: "Yes" }} value="Yes" onPick={() => undefined} />);
  expect(screen.getByText("Yes", { selector: "button" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByText("I have assumed Yes; change it if I am wrong.")).toBeInTheDocument();
});
