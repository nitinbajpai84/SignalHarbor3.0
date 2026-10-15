import { render, screen } from "@testing-library/react";

import { ModelTrouble } from "./SettingsPage";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());

// Billing message: the shape of e6_trace.model_trouble (GET /api/v1/agent-runs/model-trouble) after a replayed 402 on both providers.
test("the Settings banner names the provider that is out of credit", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(200, { trouble: { code: "no_credit", providers: ["Google", "OpenRouter"],
    words: "The model account is out of credit (Google / OpenRouter); ask the administrator to top it up.", at: "2026-10-10T03:37:20+0800" } })));
  render(<ModelTrouble />);
  expect(await screen.findByRole("alert")).toHaveTextContent("out of credit (Google / OpenRouter)");
});

test("no banner when every provider answers, or when the route refuses", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(200, { trouble: null })));
  const { container, unmount } = render(<ModelTrouble />);
  await new Promise((r) => setTimeout(r, 20));
  expect(container).toBeEmptyDOMElement();
  unmount();
  vi.stubGlobal("fetch", vi.fn(async () => json(403, { error: "not_allowed", message: "Only the company administrator can see agent runs." })));
  const second = render(<ModelTrouble />);
  await new Promise((r) => setTimeout(r, 20));
  expect(second.container).toBeEmptyDOMElement();
});
