import { render, screen } from "@testing-library/react";

import AgentChip from "./AgentChip";
import MessageBubble from "./MessageBubble";
import Panel from "./Panel";
import Sticky from "./Sticky";

// M1-UI1: the ported components keep the earlier prototype's class names, so its stylesheets style them.

test("sticky note: n-sticky, tone class, italic question line", () => {
  const { container } = render(<Sticky tone="copper" question="Who feels this?" contested />);
  expect(container.querySelector(".n-sticky.n-sticky-copper.n-sticky-contested > .n-sticky-q")).toHaveTextContent("Who feels this?");
});

test("agent chip: avatar ring with the status, name, role word and status text", () => {
  const { container } = render(<AgentChip name="North" status="thinking" />);
  expect(container.querySelector(".n-avatar-ring.status-thinking .ring")).not.toBeNull();
  expect(screen.getByText("the industry expert")).toBeInTheDocument();
  expect(screen.getByText("Thinking")).toHaveClass("status-text", "thinking");
});

test("panel: eyebrow above a real heading, region named by its title", () => {
  render(<Panel eyebrow="Speak or type" title="Your turn">body</Panel>);
  expect(screen.getByRole("region", { name: "Your turn" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Your turn" })).toBeInTheDocument();
  expect(screen.getByText("Speak or type")).toHaveClass("eyebrow");
});

test("message bubble: North's advisor label becomes a chip, a person's never does", () => {
  const { container, rerender } = render(<MessageBubble from="agent" who="North" text="Industry practice (suggestion): split by region" />);
  expect(container.querySelector(".n-message.from-agent .advisor-line.industry .advisor-chip")).toHaveTextContent("Industry practice (suggestion)");
  rerender(<MessageBubble from="human" who="You" text="Industry practice (suggestion): quoting North" />);
  expect(container.querySelector(".advisor-chip")).toBeNull();
});
