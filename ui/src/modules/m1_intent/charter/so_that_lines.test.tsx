import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import type { Charter, CharterPage } from "../api";
import { m1Charter as T } from "../copy";
import { soThatSentence } from "../CharterPaper";
import CharterScreen from "./CharterScreen";

// FIX-J: "So that" lines are full sentences; a North draft must be used as it is (or edited) before signing; notes left
// on their own show as "Left for later". fetch is stubbed.

const SID = "a".repeat(32);
const BASE = `/api/modules/m1_intent/sessions/${SID}/charter`;
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const problem = (id: string, title: string, so_that: string | null, draft: boolean) => ({
  id, title, priority: "must", priority_label: "Must", so_that, so_that_edited: !draft && so_that !== null, so_that_proposal: null, so_that_draft: draft,
  so_that_note: draft ? "Draft from North. Please check it and edit it before you sign." : null, note_count: 3,
});
const charter = (over: Partial<Charter> = {}): Charter => ({
  version: 1,
  template: { id: "standard", name: "Standard charter", columns: ["problem", "purpose", "priority", "notes"] },
  problems: [problem("c1", "Capital calls arrive too late", "So that funding is planned, not found.", true), problem("c2", "No single exposure view", "So that we see concentration early.", true)],
  later: [],
  footer: { date: "2026-10-03", participants: 3, notes: 6, later: 0 },
  status: "draft",
  signing: { needed: 2, signed: 0, can_sign: true, i_signed: false, signers: [] },
  approver: { name: "Mei Tan", link: "none", expires_at: null },
  returned: null,
  versions: [{ version: 1, status: "draft", created_at: "2026-10-03T10:00:00+00:00", created_by: "Ann", edited_at: null, edited_by: null, comment: null }],
  editable: true,
  graph: null,
  handed_on: false,
  ...over,
} as Charter);
const page = (c: Charter): CharterPage => ({ state: "signing", organiser: true, can_draft: false, no_result: false, charter: c });
const calls: { method: string; url: string; body: unknown }[] = [];

function mock(first: Charter, answer: (body: unknown) => Charter) {
  calls.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method: init?.method ?? "GET", url, body });
    if (url === BASE && (init?.method ?? "GET") === "GET") return json(200, page(first));
    if (url.startsWith(BASE)) return json(200, page(answer(body)));
    return json(404, {});
  }));
}
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
const open = () =>
  render(
    <MemoryRouter initialEntries={[`/modules/m1_intent/sessions/${SID}/charter`]}>
      <Routes>
        <Route path="/modules/m1_intent/sessions/:sessionId/charter" element={<CharterScreen />} />
      </Routes>
    </MemoryRouter>,
  );

describe("the purpose line is a full 'So that' sentence", () => {
  test("a line that already starts with the words is not given them twice; an older line gets them", () => {
    expect(soThatSentence("So that funding is planned, not found.")).toBe("So that funding is planned, not found.");
    expect(soThatSentence("funding is planned, not found")).toBe("So that funding is planned, not found.");
  });
});

describe("checking North's drafted lines before signing", () => {
  test("while a draft is unchecked the sign button is off and says why; Use this line confirms it as it is", async () => {
    const user = userEvent.setup();
    const confirmed = charter({ problems: [problem("c1", "Capital calls arrive too late", "So that funding is planned, not found.", false), problem("c2", "No single exposure view", "So that we see concentration early.", true)] });
    mock(charter(), () => confirmed);
    open();
    expect(await screen.findByRole("button", { name: T.signNow })).toBeDisabled();
    expect(screen.getByText(T.checkLinesFirst)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: T.useThisLineLabel("Capital calls arrive too late") }));
    await waitFor(() => expect(calls.some((c) => c.method === "PUT")).toBe(true));
    expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ confirm_so_that: ["c1"] });
    await waitFor(() => expect(screen.queryByRole("button", { name: T.useThisLineLabel("Capital calls arrive too late") })).not.toBeInTheDocument());
    expect(screen.getByRole("button", { name: T.useThisLineLabel("No single exposure view") })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: T.signNow })).toBeDisabled(); // one draft is still unchecked
  });

  test("once every line is a person's own the sign button works", async () => {
    mock(charter({ problems: [problem("c1", "Capital calls arrive too late", "So that funding is planned, not found.", false)] }), () => charter());
    open();
    expect(await screen.findByRole("button", { name: T.signNow })).toBeEnabled();
    expect(screen.queryByText(T.checkLinesFirst)).not.toBeInTheDocument();
  });
});

describe("notes left on their own", () => {
  test("show as 'Left for later: N notes' with their words, or a plain line when anonymous", async () => {
    mock(charter({ alone: [{ text: "Prep takes 38 hours a quarter" }, { text: null }] }), () => charter());
    open();
    expect(await screen.findByRole("heading", { name: T.leftForLater(2) })).toBeInTheDocument();
    expect(screen.getByText("Prep takes 38 hours a quarter")).toBeInTheDocument();
    expect(screen.getByText(T.leftAnonymous)).toBeInTheDocument();
  });

  test("nothing is shown when no note is left on its own", async () => {
    mock(charter({ alone: [] }), () => charter());
    open();
    await screen.findByRole("button", { name: T.signNow });
    expect(screen.queryByText(/Left for later/)).not.toBeInTheDocument();
  });
});
