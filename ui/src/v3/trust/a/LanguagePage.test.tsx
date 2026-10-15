import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import LanguagePage from "../LanguagePage";
import { json, language } from "./fixtures";

vi.mock("../../../useSession", () => ({ useSession: () => ({ user: { display_name: "Anita" } }) }));
afterEach(() => vi.unstubAllGlobals());
const page = () => render(<MemoryRouter><LanguagePage /></MemoryRouter>);

test("shows words, golden questions and playbooks; adding a word posts it", async () => {
  const added = { ...language, words: [...language.words, { word: "EG-B", means: "Entity B", by: "Anita", used: 0 }] };
  const f = vi.fn(async (_u: string, init?: RequestInit) => json(init?.method === "POST" ? added : language));
  vi.stubGlobal("fetch", f);
  page();
  expect(await screen.findByText("dry powder")).toBeInTheDocument();
  expect(screen.getByText("How much is dry powder?")).toBeInTheDocument();
  expect(screen.getByText("Span modelling playbook")).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Word"), "EG-B");
  await userEvent.type(screen.getByLabelText("Means"), "Entity B");
  await userEvent.click(screen.getByRole("button", { name: "Add" }));
  expect(await screen.findByText("EG-B")).toBeInTheDocument();
  expect(f.mock.calls.some((c) => String(c[0]).endsWith("/language/words"))).toBe(true);
});

test("Not right rejects the correction", async () => {
  const f = vi.fn(async (_u: string, init?: RequestInit) => json(init?.method === "POST" ? { ...language, corrections: [] } : language));
  vi.stubGlobal("fetch", f);
  page();
  await userEvent.click(await screen.findByRole("button", { name: "Not right" }));
  await waitFor(() =>
    expect(f.mock.calls.some((c) => String(c[0]).endsWith("/corrections/c1") && String(c[1]?.body).includes("reject"))).toBe(true));
});

test("empty office and error", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json({ words: [], corrections: [], golden: [], taught: [] })));
  const { unmount } = page();
  expect(await screen.findByText("No words yet. Add the first one below.")).toBeInTheDocument();
  unmount();
  vi.stubGlobal("fetch", vi.fn(async () => json({}, false)));
  page();
  expect(await screen.findByRole("button", { name: "Try again" })).toBeInTheDocument();
});
