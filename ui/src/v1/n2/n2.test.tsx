import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import Comments from "./Comments";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
const may = { reply: true, edit: false, delete: false, raise: true };
const base = { parent_id: null, by: "Mei Tan", at: "2026-10-10T08:00:00+00:00", edited: false, edited_at: null, deleted: false, deleted_by: null, history: [], mentions: [], case: null, ticket: null, may };
const wrap = (el: ReactElement) => render(<MemoryRouter><ThemeProvider><SessionProvider>{el}</SessionProvider></ThemeProvider></MemoryRouter>);

test("shows edited, deleted and the case link; opens only when asked", async () => {
  const calls: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url.startsWith("/api/v1/comments")) calls.push(url);
    if (url.startsWith("/api/v1/comments/people")) return json(200, [{ name: "Raj Iyer" }]);
    return json(200, { kind: "office_line", id: "p/x", count: 2, comments: [
      { ...base, id: "a", text: "Why did this move?", edited: true, case: { id: "c1", number: "CASE-0001", link: "/centre/desk/c1" }, may: { ...may, raise: false } },
      { ...base, id: "b", by: "Raj Iyer", text: null, deleted: true, deleted_by: "Raj Iyer" }] });
  }));
  wrap(<Comments target={{ kind: "office_line", id: "p/x" }} />);
  expect(calls).toEqual([]);
  fireEvent.click(screen.getByText("Comments"));
  expect(await screen.findByText("Why did this move?")).toBeTruthy();
  expect(screen.getByText("edited")).toBeTruthy();
  expect(screen.getByText("Deleted by Raj Iyer")).toBeTruthy();
  expect(screen.getByText("Case CASE-0001").getAttribute("href")).toBe("/centre/desk/c1");
});

test("a refusal shows one sentence and no thread", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => url.startsWith("/api/v1/comments?") ? json(403, { error: "not_allowed", message: "You do not have access to this." }) : json(200, [])));
  wrap(<Comments target={{ kind: "case", id: "c9" }} startOpen />);
  expect(await screen.findByText("You do not have access to this.")).toBeTruthy();
  expect(screen.queryByText("No comments yet.")).toBeNull();
});
