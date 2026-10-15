import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import type { Charter, CharterPage } from "../api";
import { m1Charter as T } from "../copy";
import CharterScreen from "./CharterScreen";

// Download and "email the people who took part": shown only on a signed charter; the email only to the organiser.

const SID = "c".repeat(32);
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const signed: Charter = {
  version: 1,
  template: { id: "standard", name: "Standard charter", columns: ["problem", "purpose", "priority", "notes"] },
  problems: [{ id: "c1", title: "Capital calls arrive too late", priority: "must", priority_label: "Must", so_that: "So that funding is planned.", so_that_edited: true, so_that_proposal: null, note_count: 2, tie: null, tied_options: [] }],
  later: [],
  footer: { date: "2026-10-04", participants: 3, notes: 2, later: 0 },
  status: "signed",
  signing: { needed: 2, signed: 2, can_sign: false, i_signed: true, signers: [{ name: "Pat Lee", at: "2026-10-04T09:00:00+00:00", how: "room" }] },
  approver: { name: "", link: "none", expires_at: null },
  returned: null,
  versions: [{ version: 1, status: "signed", created_at: "2026-10-04T08:00:00+00:00", created_by: "Ann", edited_at: null, edited_by: null, comment: null }],
  editable: false,
  graph: null,
  handed_on: true,
};
const page = (c: Charter, organiser: boolean): CharterPage => ({ state: "closed", organiser, can_draft: false, no_result: false, charter: c });
const EMAIL = { subject: "The signed charter: Plan", body: "Hello\nhttps://harbor.example.test/modules/m1_intent/sessions/x/charter\n", link_path: "/modules/m1_intent/sessions/x/charter", link: "https://harbor.example.test/modules/m1_intent/sessions/x/charter", no_address: ["Sara Guest"], people: [{ name: "Ann Example", email: "ann@example.test" }, { name: "Sara Guest", email: null }] };

function show(body: unknown, extra: (url: string) => Response | null = () => null) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => extra(url) ?? json(200, body)));
  render(
    <MemoryRouter initialEntries={[`/modules/m1_intent/sessions/${SID}/charter`]}>
      <Routes>
        <Route path="/modules/m1_intent/sessions/:sessionId/charter" element={<CharterScreen />} />
      </Routes>
    </MemoryRouter>,
  );
}
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

test("the organiser of a signed charter sees both buttons and gets the email with a blind-copy link and a typed address", async () => {
  show(page(signed, true), (u) => (u.endsWith("/charter/email") ? json(200, EMAIL) : null));
  expect(await screen.findByRole("button", { name: T.download })).toBeInTheDocument();
  await userEvent.setup().click(screen.getByRole("button", { name: T.emailPeople }));
  expect(await screen.findByText(new RegExp(T.emailNoAddress))).toBeInTheDocument();
  expect(screen.getByText(T.emailMissing(["Sara Guest"]))).toBeInTheDocument();
  expect(screen.getByRole("textbox", { name: T.emailBody }).textContent).toContain("https://harbor.example.test/modules/m1_intent/sessions/x/charter");
  await userEvent.setup().type(screen.getByLabelText(T.emailTypeAddress("Sara Guest")), "sara@example.test");
  const href = screen.getByRole("link", { name: T.emailOpen }).getAttribute("href") ?? "";
  expect(href.startsWith("mailto:?bcc=ann%40example.test,sara%40example.test&subject=")).toBe(true);
  expect(screen.getByRole("button", { name: T.emailCopy })).toBeInTheDocument();
});

test("a seated guest sees the download but not the email button", async () => {
  show(page(signed, false));
  expect(await screen.findByRole("button", { name: T.download })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: T.emailPeople })).not.toBeInTheDocument();
});

test("a charter not yet signed shows neither button", async () => {
  show(page({ ...signed, status: "draft", handed_on: false, signing: { ...signed.signing, signed: 0, can_sign: true, i_signed: false, signers: [] } }, true));
  expect(await screen.findByText(T.signNow)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: T.download })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: T.emailPeople })).not.toBeInTheDocument();
});

test("a refused email shows the plain words and no email", async () => {
  show(page(signed, true), (u) => (u.endsWith("/charter/email") ? json(409, { error: "wrong_state", message: "The charter can be downloaded once it is signed." }) : null));
  await userEvent.setup().click(await screen.findByRole("button", { name: T.emailPeople }));
  expect(await screen.findByRole("alert")).toHaveTextContent("once it is signed");
  expect(screen.queryByRole("button", { name: T.emailCopy })).not.toBeInTheDocument();
});
