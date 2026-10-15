import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import McpTokens from "./McpTokens";

// V6 (walk gap 15): the outside-assistants form uses the design system's inputs and buttons, and issuing a token shows it once.
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());

test("the form is styled, Issue token waits for a name, and the token is shown once", async () => {
  const sent: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") { sent.push(String(init.body)); return json(200, { token: "sh_test_token_1" }); }
    return json(200, { tokens: [{ id: "t1", label: "Claude on my laptop", scopes: ["read"], created: "2026-10-11", expires: "2026-11-10T00:00:00", revoked: false, last_used: null, active: true }], scopes: ["read", "propose"] });
  }));
  render(<McpTokens />);
  const issue = await screen.findByRole("button", { name: "Issue token" });
  expect(issue).toHaveClass("ds-btn");
  expect(screen.getByLabelText("Name")).toHaveClass("ds-input");
  expect(issue).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Name"), "Cursor");
  await userEvent.click(issue);
  await waitFor(() => expect(sent).toHaveLength(1));
  expect(JSON.parse(sent[0]!)).toEqual({ label: "Cursor", scopes: ["read"], days: 30 });
  expect(await screen.findByText("sh_test_token_1")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Revoke" })).toHaveClass("ds-btn");
});
