import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import TalkBox from "./TalkBox";

afterEach(() => vi.unstubAllGlobals());

function stub(sent: string[]) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (String(url).includes("/voice")) return new Response(JSON.stringify({ available: false }), { status: 200, headers: { "Content-Type": "application/json" } });
    sent.push(`${init?.method} ${url} ${String(init?.body ?? "")}`);
    return new Response(JSON.stringify({ reply: `Answer ${sent.length}: the core model has 20 tables.` }), { status: 200, headers: { "Content-Type": "application/json" } });
  }));
}

test("Enter sends, the thread shows both turns, a follow-up adds two more", async () => {
  const sent: string[] = [];
  stub(sent);
  render(<TalkBox agent="Span" path="/api/v1/build/chat" hint="ask" />);
  const box = screen.getByRole("textbox");
  await userEvent.type(box, "what is the data model?{Enter}");
  expect(await screen.findByText(/Answer 1/)).toBeTruthy();
  expect(screen.getByText("what is the data model?")).toBeTruthy();
  await userEvent.type(screen.getByRole("textbox"), "and the silver ones?{Enter}");
  expect(await screen.findByText(/Answer 2/)).toBeTruthy();
  expect(screen.getByText(/Answer 1/)).toBeTruthy();  // the first turn is still there
  expect(sent.filter((s) => s.startsWith("POST /api/v1/build/chat")).length).toBe(2);
});

test("Shift+Enter adds a line and does not send", async () => {
  const sent: string[] = [];
  stub(sent);
  render(<TalkBox agent="Lumen" path="/api/v1/consume/chat" hint="ask" />);
  await userEvent.type(screen.getByRole("textbox"), "one{Shift>}{Enter}{/Shift}two");
  expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("one\ntwo");
  expect(sent.length).toBe(0);
});

test("the button is always active and an empty send says what to do", async () => {
  const sent: string[] = [];
  stub(sent);
  render(<TalkBox agent="Span" path="/api/v1/build/chat" hint="ask" />);
  const btn = screen.getByRole("button", { name: "Send" }) as HTMLButtonElement;
  expect(btn.disabled).toBe(false);
  await userEvent.click(btn);
  expect(await screen.findByText("Type a question first.")).toBeTruthy();
  expect(sent.length).toBe(0);
});
