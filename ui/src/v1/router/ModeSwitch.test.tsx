import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import ModeLine from "./ModeLine";
import ModeSwitch, { MODE_WORDS } from "./ModeSwitch";

const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });

function mock(canFlip: boolean) {
  document.cookie = "sh_csrf=tok";
  const posts: unknown[] = [];
  vi.stubGlobal("fetch", vi.fn(async (_url: string, init?: RequestInit) => {
    if (init?.method === "POST") { posts.push(JSON.parse(String(init.body))); return json({ mode: "real", can_flip: true }); }
    return json({ mode: "testing", can_flip: canFlip });
  }));
  return posts;
}
afterEach(() => vi.unstubAllGlobals());

it("the decision maker flips to Real use by keyboard and the line under the agent follows", async () => {
  const posts = mock(true);
  render(<><ModeSwitch /><ModeLine /></>);
  const sw = await screen.findByRole("switch");
  expect(sw).toHaveAttribute("aria-checked", "false");
  expect(await screen.findByText("Testing models (free tier)")).toBeInTheDocument();
  sw.focus();
  await userEvent.keyboard(" ");
  expect(await screen.findByText("Real-use models")).toBeInTheDocument();
  expect(sw).toHaveAttribute("aria-checked", "true");
  expect(posts).toEqual([{ mode: "real" }]);
});

it("a reader sees the state but cannot flip", async () => {
  mock(false);
  render(<ModeSwitch />);
  const sw = await screen.findByRole("switch");
  expect(sw).toBeDisabled();
  expect(sw).toHaveAccessibleName(/Testing\. Only the decision maker/);
});

it("says what each mode means and that it applies to the whole company, with no made-up answers", async () => {
  mock(true);
  render(<ModeSwitch />);
  const sw = await screen.findByRole("switch");
  expect(sw.closest(".ms-wrap")).toHaveAttribute("title", MODE_WORDS);
  expect(sw).toHaveAttribute("aria-description", MODE_WORDS);
  expect(MODE_WORDS).toBe("Testing: free model tier, for trying things. Real use: the company's chosen models. This switch applies to everyone in the company.");
  expect(MODE_WORDS).not.toMatch(/made-up/);
});
