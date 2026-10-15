import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import type { Charter, CharterPage } from "../api";
import { m1Charter as T } from "../copy";
import CharterScreen from "./CharterScreen";
import ClosedCharter from "./ClosedCharter";

// CRITIC-M1 round 2: a tied vote reads "Tied ... The room decides." and the organiser chooses; a seated guest reads the charter with no buttons.

const SID = "b".repeat(32);
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const TIE = "Tied: must 1 · should 2 · could 2. The room decides.";

const charter = (over: Partial<Charter> = {}): Charter => ({
  version: 1,
  template: { id: "standard", name: "Standard charter", columns: ["problem", "purpose", "priority", "notes"] },
  problems: [
    { id: "c3", title: "Pay depends on trusted performance", priority: null, priority_label: null, so_that: null, so_that_edited: false, so_that_proposal: null, note_count: 2, tie: TIE, tied_options: [{ id: "should", label: "Should" }, { id: "could", label: "Could" }] },
  ],
  later: [],
  footer: { date: "2026-10-03", participants: 5, notes: 2, later: 0 },
  status: "draft",
  signing: { needed: 2, signed: 0, can_sign: true, i_signed: false, signers: [] },
  approver: { name: "", link: "none", expires_at: null },
  returned: null,
  versions: [{ version: 1, status: "draft", created_at: "2026-10-03T10:00:00+00:00", created_by: "Ann", edited_at: null, edited_by: null, comment: null }],
  editable: true,
  graph: null,
  handed_on: false,
  ...over,
});
const page = (c: Charter, over: Partial<CharterPage> = {}): CharterPage => ({ state: "signing", organiser: true, can_draft: false, no_result: false, charter: c, ...over });

const calls: { method: string; body: unknown }[] = [];
function mock(handler: (method: string) => Response) {
  calls.length = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_url: string, init?: RequestInit) => {
      calls.push({ method: init?.method ?? "GET", body: init?.body ? JSON.parse(String(init.body)) : undefined });
      return handler(init?.method ?? "GET");
    }),
  );
}
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

test("a tied vote shows the tie line and the organiser's choice is saved as the priority", async () => {
  const chosen = charter({ problems: [{ ...charter().problems[0]!, priority: "should", priority_label: "Should", tie: null, tied_options: [] }] });
  mock((m) => json(200, m === "PUT" ? page(chosen) : page(charter())));
  render(
    <MemoryRouter initialEntries={[`/modules/m1_intent/sessions/${SID}/charter`]}>
      <Routes>
        <Route path="/modules/m1_intent/sessions/:sessionId/charter" element={<CharterScreen />} />
      </Routes>
    </MemoryRouter>,
  );
  expect(await screen.findByText(TIE)).toBeInTheDocument();
  expect(screen.getByText(T.tiedPill)).toBeInTheDocument();
  await userEvent.setup().selectOptions(screen.getByRole("combobox", { name: T.chooseTied("Pay depends on trusted performance") }), "should");
  expect(await screen.findByText("Should")).toBeInTheDocument();
  expect(calls.at(-1)).toMatchObject({ method: "PUT", body: { priority: { c3: "should" } } });
  expect(screen.queryByText(TIE)).not.toBeInTheDocument();
});

test("a seated guest after the close reads the charter with no sign, edit or choose controls", async () => {
  mock(() => json(200, page(charter({ status: "signed", editable: false, signing: { needed: 2, signed: 2, can_sign: false, i_signed: false, signers: [] }, handed_on: true }), { organiser: false, state: "closed" })));
  render(<ClosedCharter sessionId={SID} />);
  expect(await screen.findByText("Pay depends on trusted performance")).toBeInTheDocument();
  expect(screen.getByText(T.readOnlyGuest)).toBeInTheDocument();
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
  expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
});
