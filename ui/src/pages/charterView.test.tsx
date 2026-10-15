import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import type { Charter, CharterPage } from "../modules/m1_intent/api";
import CharterView from "./CharterView";

let roles: string[] = ["sponsor"];
vi.mock("../useSession", () => ({ useSession: () => ({ user: { display_name: "Mei Tan", company_id: "co", roles } }) }));

const SID = "a".repeat(32);
const BASE = `/api/modules/m1_intent/sessions/${SID}/charter`;
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const charter = (over: Partial<Charter> = {}): Charter => ({
  version: 1,
  template: { id: "standard", name: "Standard charter", columns: ["problem", "purpose", "priority", "notes"] },
  problems: [{ id: "c1", title: "Capital calls arrive too late", priority: "must", priority_label: "Must", so_that: "funding is planned", so_that_edited: false, so_that_proposal: null, note_count: 6 }],
  later: [{ id: "c4", title: "Reporting is monthly only" }],
  footer: { date: "2026-10-03", participants: 8, notes: 14, later: 1 },
  status: "draft",
  signing: { needed: 2, signed: 0, can_sign: true, i_signed: false, signers: [] },
  approver: { name: "Mei Tan", link: "none", expires_at: null },
  returned: null,
  versions: [],
  editable: false,
  graph: null,
  handed_on: false,
  ...over,
});
const page = (c: Charter): CharterPage => ({ state: "signing", organiser: true, can_draft: false, no_result: false, charter: c });

const calls: { method: string; url: string }[] = [];
function mock(handler: (method: string) => Response) {
  calls.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ method: init?.method ?? "GET", url });
    return handler(init?.method ?? "GET");
  }));
}
afterEach(() => vi.unstubAllGlobals());

const open = () =>
  render(
    <MemoryRouter initialEntries={[`/centre/intent/charter/${SID}`]}>
      <Routes>
        <Route path="/centre/intent/charter/:sessionId" element={<CharterView />} />
      </Routes>
    </MemoryRouter>,
  );

describe("CharterView", () => {
  test("renders problems, so-that line, parked item and the signature block", async () => {
    mock(() => json(200, page(charter())));
    open();
    expect(await screen.findByText("Capital calls arrive too late")).toBeInTheDocument();
    expect(screen.getByText("Must")).toBeInTheDocument();
    expect(screen.getByText("Reporting is monthly only")).toBeInTheDocument();
    expect(screen.getByText("Signers: 0 of 2")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send to an approver" })).toBeInTheDocument();
  });

  test("a sealed card stays sealed", async () => {
    mock(() => json(200, page(charter({ alone: [{ text: "A sealed card", kind: "intent" }] }))));
    open();
    expect(await screen.findByText("A sealed card")).toBeInTheDocument();
  });

  test("the organiser sees the signature state but is not offered the sign button", async () => {
    roles = ["company_admin"];
    mock(() => json(200, page(charter())));
    open();
    expect(await screen.findByText("Waiting for Mei Tan to sign.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Sign now" })).toBeNull();
    roles = ["sponsor"];
  });

  test("sign calls the sign route", async () => {
    mock((m) => json(200, page(charter(m === "POST" ? { status: "signed", signing: { needed: 2, signed: 1, can_sign: false, i_signed: true, signers: [] } } : {}))));
    open();
    await userEvent.setup().click(await screen.findByRole("button", { name: "Sign now" }));
    expect(calls.at(-1)).toMatchObject({ method: "POST", url: `${BASE}/sign` });
  });

  test("the sponsor signs from the pulse link and the signature block shows the signature", async () => {
    const sponsor = (c: Charter): CharterPage => ({ ...page(c), organiser: false });
    const signed = { status: "signed" as const, signing: { needed: 1, signed: 1, can_sign: false, i_signed: true, signers: [{ name: "Mei Tan", at: "2026-10-07T09:00:00Z", how: "room" as const }] } };
    mock((m) => json(200, sponsor(charter(m === "POST" ? signed : { signing: { needed: 1, signed: 0, can_sign: true, i_signed: false, signers: [] } }))));
    open();
    expect(screen.queryByRole("button", { name: "Send to an approver" })).toBeNull();
    await userEvent.setup().click(await screen.findByRole("button", { name: "Sign now" }));
    expect(calls.find((c) => c.method === "POST")).toMatchObject({ url: `${BASE}/sign` });
    expect(await screen.findByText(/Signed by Mei Tan/)).toBeInTheDocument();
    expect(screen.getByText("Signers: 1 of 1")).toBeInTheDocument();
  });

  test("Who does what shows each role with its mark: guessed or stated", async () => {
    calls.length = 0;
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.endsWith("/roles")) return json(200, {
        roles: { architect: "Dan Data", developer: null, tester: null, sponsor: "Mei Tan", ops: null, informed: [] },
        provenance: { architect: { mark: "guessed", by: "Lens", from: "From the people list" }, sponsor: { mark: "stated", by: "Ann Example", from: "Set by the organiser" } },
        can_edit: false,
      });
      return json(200, page(charter()));
    }));
    open();
    expect(await screen.findByText("Who does what")).toBeInTheDocument();
    expect(await screen.findByText("Dan Data")).toBeInTheDocument();
    expect(document.querySelector("[data-role=architect] [data-mark]")).toHaveAttribute("data-mark", "guessed");
    expect(document.querySelector("[data-role=sponsor] [data-mark]")).toHaveAttribute("data-mark", "stated");
    expect(screen.getByText("Named by Ann Example, the organiser.")).toBeInTheDocument();
  });

  test("a signed charter says what goes to the baseline in plain words", async () => {
    mock(() => json(200, page(charter({ status: "signed", signing: { needed: 1, signed: 1, can_sign: false, i_signed: false, signers: [{ name: "Daniel Kerr", at: "2026-04-18T01:22:00Z", how: "room" }] } } as Partial<Charter>))));
    open();
    expect(await screen.findByText(/^Handed on: 1 problem to baseline/)).toBeInTheDocument();
    expect(screen.queryByText(/module 2/)).toBeNull();
  });

  test("signed, as the sponsor reads it: capitalised pill, cards not notes, the signer on the version, one read-only line", async () => {
    roles = [];
    const signers = [{ name: "Daniel Kerr", at: "2026-04-18T01:22:00Z", how: "room" }];
    const signed = charter({ status: "signed", signing: { needed: 1, signed: 1, can_sign: false, i_signed: false, signers },
      versions: [{ version: 1, status: "signed", created_at: "2026-04-17T17:22:07Z", created_by: "Janet Shaw", comment: null }] } as unknown as Partial<Charter>);
    mock(() => json(200, { ...page(signed), organiser: false }));
    open();
    expect(await screen.findByText("Raised in 6 cards.")).toBeInTheDocument();
    expect(screen.getAllByText("Signed").length).toBeGreaterThan(0);
    expect(screen.queryByText("signed")).toBeNull();
    expect(screen.getAllByText(/Daniel Kerr/).length).toBeGreaterThan(1); // the signature and the version row
    expect(screen.queryByText(/Janet Shaw/)).toBeNull();
    expect(screen.queryByText(/only the people who sign can change it/)).toBeNull();
    roles = ["sponsor"];
  });
});
