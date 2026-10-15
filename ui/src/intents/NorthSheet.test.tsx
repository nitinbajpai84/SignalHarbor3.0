import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, test } from "vitest";

import NorthSheet from "./NorthSheet";

function Host() {
  const [open, setOpen] = useState(false);
  return <NorthSheet open={open} onOpenChange={setOpen}><button type="button">Inside</button></NorthSheet>;
}

describe("North sheet", () => {
  test("is a modal dialog, Close North first, focus trapped, Escape closes and returns focus", async () => {
    render(<Host />);
    const opener = screen.getByRole("button", { name: "Talk to North" });
    await userEvent.click(opener);
    expect(screen.getByRole("dialog", { name: /North/ })).toHaveAttribute("aria-modal", "true");
    const close = screen.getAllByRole("button", { name: "Close North" }).find((b) => b.className.includes("ic-sheet__close"))!;
    expect(close).toHaveFocus();
    await userEvent.tab();
    expect(screen.getByRole("button", { name: "Inside" })).toHaveFocus();
    await userEvent.tab();
    expect(close).toHaveFocus();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByRole("button", { name: "Talk to North" })).toHaveFocus();
  });
});
