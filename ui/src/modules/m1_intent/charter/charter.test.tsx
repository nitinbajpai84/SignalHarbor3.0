import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import ApproverPage from "../../../pages/ApproverPage";
import { ThemeProvider } from "../../../theme";
import type { ApproverDraft, Charter, CharterPage } from "../api";
import { m1Charter as T, m1Nira } from "../copy";
import CharterScreen from "./CharterScreen";

// M1-P09: the charter screen in its five states, signing, sending up, the picture, and the approver's page. fetch is stubbed.

const SID = "a".repeat(32);
const BASE = `/api/modules/m1_intent/sessions/${SID}/charter`;
const TOKEN = `ap-${SID}-${"s".repeat(43)}`;
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const charter = (over: Partial<Charter> = {}): Charter => ({
  version: 1,
  template: { id: "standard", name: "Standard charter", columns: ["problem", "purpose", "priority", "notes"] },
  problems: [
    { id: "c1", title: "Capital calls arrive too late", priority: "must", priority_label: "Must", so_that: "funding is planned, not found", so_that_edited: false, so_that_proposal: null, note_count: 6 },
    { id: "c2", title: "No single exposure view", priority: "should", priority_label: "Should", so_that: null, so_that_edited: false, so_that_proposal: null, note_count: 5 },
    { id: "c3", title: "Nobody owns the manager fee list", priority: null, priority_label: null, so_that: null, so_that_edited: false, so_that_proposal: null, note_count: 2 },
  ],
  later: [{ id: "c4", title: "Reporting is monthly only" }],
  footer: { date: "2026-10-03", participants: 8, notes: 14, later: 1 },
  status: "draft",
  signing: { needed: 2, signed: 0, can_sign: true, i_signed: false, signers: [] },
  approver: { name: "Mei Tan", link: "none", expires_at: null },
  returned: null,
  versions: [{ version: 1, status: "draft", created_at: "2026-10-03T10:00:00+00:00", created_by: "Ann Example", edited_at: null, edited_by: null, comment: null }],
  editable: true,
  graph: null,
  handed_on: false,
  ...over,
});
const page = (c: Charter | null, over: Partial<CharterPage> = {}): CharterPage => ({ state: "signing", organiser: true, can_draft: false, no_result: false, charter: c, ...over });

interface Call { method: string; url: string; headers: Record<string, string>; body: unknown }
const calls: Call[] = [];

function mock(handler: (call: Call) => Response | Promise<Response>) {
  calls.length = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const call = { method: init?.method ?? "GET", url, headers: (init?.headers ?? {}) as Record<string, string>, body: init?.body ? JSON.parse(String(init.body)) : undefined };
      calls.push(call);
      return handler(call);
    }),
  );
}
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function openCharter() {
  return render(
    <MemoryRouter initialEntries={[`/modules/m1_intent/sessions/${SID}/charter`]}>
      <Routes>
        <Route path="/modules/m1_intent/sessions/:sessionId/charter" element={<CharterScreen />} />
      </Routes>
    </MemoryRouter>,
  );
}
function openApprover(token = TOKEN) {
  return render(
    <MemoryRouter initialEntries={[`/approve/${token}`]}>
      <ThemeProvider>
        <Routes>
          <Route path="/approve/:token" element={<ApproverPage />} />
        </Routes>
      </ThemeProvider>
    </MemoryRouter>,
  );
}

describe("the charter screen: five states", () => {
  test("loading", async () => {
    mock(() => new Promise<Response>(() => undefined));
    openCharter();
    expect(await screen.findByRole("status")).toHaveTextContent("Loading");
  });

  test("empty: no result from the room yet says so and offers nothing to draft", async () => {
    mock(() => json(200, page(null, { state: "together", no_result: true })));
    openCharter();
    expect(await screen.findByText(T.noResult)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: T.makeDraft })).not.toBeInTheDocument();
  });

  test("empty: a ready room offers the draft, and making it shows the charter", async () => {
    mock((c) => (c.method === "POST" ? json(201, page(charter())) : json(200, page(null, { state: "together", can_draft: true }))));
    openCharter();
    await userEvent.setup().click(await screen.findByRole("button", { name: T.makeDraft }));
    expect(await screen.findByText("Capital calls arrive too late")).toBeInTheDocument();
    expect(calls.at(-1)).toMatchObject({ method: "POST", url: BASE });
  });

  test("error: one sentence and a way to try again", async () => {
    mock(() => json(500, { detail: "boom" }));
    openCharter();
    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  test("refused: a person with no access is told so in plain words", async () => {
    mock(() => json(403, { error: "forbidden", message: "x" }));
    openCharter();
    expect(await screen.findByRole("alert")).toHaveTextContent("You do not have access");
  });

  test("populated: priority, So that, Raised in N notes, the footer and Signers: 0 of 2", async () => {
    mock(() => json(200, page(charter())));
    openCharter();
    expect(await screen.findByText("Capital calls arrive too late")).toBeInTheDocument();
    expect(screen.getByText("Must")).toBeInTheDocument();
    expect(screen.getByDisplayValue("funding is planned, not found")).toBeInTheDocument(); // the organiser's draft is editable
    expect(screen.getAllByText("Raised in 6 notes.").length + screen.getAllByText(/Raised in 6 notes/).length).toBeGreaterThan(0);
    expect(screen.getByText("No votes yet")).toBeInTheDocument();                           // a problem nobody voted on shows no priority
    expect(screen.getByText("Session of 3 October 2026 · 8 participants · 14 notes · 1 problem left for later")).toBeInTheDocument();
    expect(screen.getByText("Signers: 0 of 2")).toBeInTheDocument();
    expect(screen.getByText("Reporting is monthly only")).toBeInTheDocument();             // carried to a later session
    expect(screen.getByRole("button", { name: "Sign now" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send to an approver" })).toBeInTheDocument();
    expect(screen.getByText(/Version 1, draft, Ann Example/)).toBeInTheDocument();
  });
});

describe("signing and sending up", () => {
  test("Sign now posts and the count moves to 1 of 2", async () => {
    const signed = charter({ signing: { needed: 2, signed: 1, can_sign: false, i_signed: true, signers: [{ name: "Ann Example", at: "2026-10-03T10:05:00+00:00", how: "room" }] }, editable: false });
    mock((c) => (c.method === "POST" ? json(200, page(signed)) : json(200, page(charter()))));
    openCharter();
    await userEvent.setup().click(await screen.findByRole("button", { name: "Sign now" }));
    expect(await screen.findByText("Signers: 1 of 2")).toBeInTheDocument();
    expect(calls.at(-1)).toMatchObject({ method: "POST", url: `${BASE}/sign` });
    expect(screen.getByText(T.alreadySigned)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Send to an approver" })).not.toBeInTheDocument();
  });

  test("Send to an approver shows the link once, with the approver's name, and the draft stops being editable", async () => {
    const out = { ...page(charter({ status: "awaiting_approver", editable: false, approver: { name: "Mei Tan", link: "open", expires_at: "2026-10-06T10:00:00+00:00" } })), link_path: `/approve/${TOKEN}`, link_expires_at: "2026-10-06T10:00:00+00:00" };
    mock((c) => (c.method === "POST" ? json(200, out) : json(200, page(charter()))));
    openCharter();
    const user = userEvent.setup();
    expect(await screen.findByText(T.sendUpHelp("Mei Tan"))).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Send to an approver" }));
    expect(await screen.findByDisplayValue(new RegExp(`/approve/${TOKEN}$`))).toBeInTheDocument();
    expect(screen.getByRole("button", { name: T.withdraw })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Sign now" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: T.saveSoThat })).not.toBeInTheDocument();
  });

  test("no named approver: it says so instead of offering to send", async () => {
    mock(() => json(200, page(charter({ approver: { name: "", link: "none", expires_at: null } }))));
    openCharter();
    expect(await screen.findByText(T.noApprover)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Send to an approver" })).not.toBeInTheDocument();
  });

  test("editing a purpose line saves it", async () => {
    mock((c) => (c.method === "PUT" ? json(200, page(charter())) : json(200, page(charter()))));
    openCharter();
    const user = userEvent.setup();
    const field = await screen.findByLabelText(T.soThatLabel("No single exposure view"));
    await user.type(field, "concentration is seen early");
    await user.click(screen.getByRole("button", { name: T.saveSoThat }));
    await waitFor(() => expect(calls.at(-1)).toMatchObject({ method: "PUT", url: BASE, body: { so_that: expect.objectContaining({ c2: "concentration is seen early" }) } }));
  });

  test("North's draft purpose line is labelled a draft, and a blank one asks the organiser", async () => {
    const notes = ["Draft from North. Please check it and edit it before you sign.", "Ask the room what this is for, then write the \"So that ...\" line yourself.", null];
    const problems = charter().problems.map((p, i) => ({ ...p, so_that_draft: i === 0, so_that_note: notes[i] ?? null }));
    mock(() => json(200, page(charter({ problems, editable: false }))));
    openCharter();
    expect(await screen.findByText(/Draft from North/)).toBeInTheDocument();
    expect(screen.getByText(/Ask the room what this is for/)).toBeInTheDocument();
  });

  test("a signed charter is read-only: no field, no sign, no send, and it says what is handed on", async () => {
    mock(() => json(200, page(charter({ status: "signed", editable: false, handed_on: true, signing: { needed: 2, signed: 2, can_sign: false, i_signed: true, signers: [{ name: "Ann Example", at: "2026-10-03T10:05:00+00:00", how: "room" }, { name: "Bo Example", at: "2026-10-03T10:06:00+00:00", how: "room" }] } }))));
    openCharter();
    expect(await screen.findByText(T.readOnly)).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: (n) => n !== m1Nira.question }) /* Nira's own ask box is always there */).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Sign now|Send to an approver|Save/ })).not.toBeInTheDocument();
    expect(screen.getByText("Handed on: 3 problems to baseline, and 1 left for later.")).toBeInTheDocument();
    expect(screen.getByText(/Signed by Bo Example/)).toBeInTheDocument();
  });

  test("the hand-off line counts each list exactly and drops a part that is zero", () => {
    const k = (kind?: "intent" | "pain_point" | "future_signal" | "lever") => ({ kind }) as { kind?: "intent" | "pain_point" | "future_signal" | "lever" };
    expect(T.handedOn([k("intent"), k(), k("intent"), k("pain_point"), k("future_signal"), k("lever")], 0)).toBe(
      "Handed on: 3 problems and 1 pain point to baseline, plus 1 future signal and 1 lever as context.");
    expect(T.handedOn([k("pain_point"), k("pain_point")], 0)).toBe("Handed on: 2 pain points to baseline.");
    expect(T.handedOn([k("lever")], 2)).toBe("Handed on: 1 lever as context, and 2 left for later.");
  });

  test("a returned charter shows the approver's comment and offers a new draft", async () => {
    const back = charter({ status: "returned", editable: false, returned: { comment: "Name the fee list owner", by: "Mei Tan", at: "2026-10-03T11:00:00+00:00" } });
    mock(() => json(200, page(back, { state: "together", can_draft: true })));
    openCharter();
    expect(await screen.findByText(T.returnedBy("Mei Tan", "Name the fee list owner"))).toBeInTheDocument();
    expect(screen.getByRole("button", { name: T.makeNew })).toBeInTheDocument();
  });

  test("the short template shows the problem and its priority only", async () => {
    const short = charter({ template: { id: "short", name: "Short charter", columns: ["problem", "priority"] }, editable: false });
    mock(() => json(200, page(short)));
    openCharter();
    expect(await screen.findByText("Capital calls arrive too late")).toBeInTheDocument();
    expect(screen.queryByText(/So that/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Raised in/)).not.toBeInTheDocument();
    expect(screen.getByText("Must")).toBeInTheDocument();
  });
});

describe("the picture at sign-off", () => {
  test("is plain SVG, labelled as a suggestion, and draws only the measures it was given", async () => {
    const graph = { label: "What others in the industry usually track (a suggestion, not your company's own definition)", problems: [{ id: "c1", title: "Capital calls arrive too late" }], kpis: [{ id: "K1", name: "Six-month funding headroom" }], links: [{ problem: "c1", kpi: "K1" }] };
    mock(() => json(200, page(charter({ graph }))));
    openCharter();
    const svg = await screen.findByRole("img", { name: T.picture.label });
    expect(svg.tagName.toLowerCase()).toBe("svg");
    expect(Array.from(svg.querySelectorAll("text")).map((n) => n.textContent)).toContain("Six-month funding headroom");
    expect(svg.querySelectorAll("path.link")).toHaveLength(1);
    expect(screen.getByText(graph.label)).toBeInTheDocument();
    expect(screen.getByText(T.picture.note)).toBeInTheDocument();
    expect(screen.getByText("Suggestion")).toBeInTheDocument();
  });

  test("no graph: no picture and no empty frame", async () => {
    mock(() => json(200, page(charter({ graph: null }))));
    openCharter();
    await screen.findByText("Capital calls arrive too late");
    expect(screen.queryByRole("img", { name: T.picture.label })).not.toBeInTheDocument();
  });
});

describe("the approver's page", () => {
  const draft: ApproverDraft = { ...charter(), approver_name: "Mei Tan", expires_at: "2026-10-06T10:00:00+00:00" };

  test("shows the draft and the one question, with no sign-in and no module chrome", async () => {
    mock(() => json(200, draft));
    openApprover();
    expect(await screen.findByText(T.question)).toBeInTheDocument();
    expect(screen.getByText("Capital calls arrive too late")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Decline" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Modules|Intent Centre|Sign out/ })).not.toBeInTheDocument();
    expect(calls).toHaveLength(1);
    expect(calls[0]).toMatchObject({ method: "POST", url: "/api/modules/m1_intent/approver/charter" });
    expect(calls[0]?.headers["X-Session-Token"]).toBe(TOKEN);   // the token travels in the header only
    expect(calls[0]?.url).not.toContain(TOKEN);
    expect(document.body.textContent).not.toContain(TOKEN);    // and is never shown
  });

  test("approving posts the decision and thanks the approver", async () => {
    mock((c) => (c.method === "POST" && c.url.endsWith("/decision") ? json(200, { decision: "approve", status: "signed" }) : json(200, draft)));
    openApprover();
    await userEvent.setup().click(await screen.findByRole("button", { name: "Approve" }));
    expect(await screen.findByText(T.approved)).toBeInTheDocument();
    expect(calls.at(-1)).toMatchObject({ url: "/api/modules/m1_intent/approver/decision", body: { decision: "approve", comment: "" } });
    expect(calls.at(-1)?.headers["X-Session-Token"]).toBe(TOKEN);
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
  });

  test("declining needs a comment: none is sent without one, then it goes with it", async () => {
    mock((c) => (c.url.endsWith("/decision") ? json(200, { decision: "decline", status: "returned" }) : json(200, draft)));
    openApprover();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Decline" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(T.commentHelp);
    expect(calls.filter((c) => c.url.endsWith("/decision"))).toHaveLength(0);
    await user.type(screen.getByLabelText(T.commentLabel), "Name the fee list owner");
    await user.click(screen.getByRole("button", { name: "Decline" }));
    expect(await screen.findByText(T.declined)).toBeInTheDocument();
    expect(calls.at(-1)).toMatchObject({ body: { decision: "decline", comment: "Name the fee list owner" } });
  });

  test("a used, expired or unknown link shows the server's plain sentence and nothing of the draft", async () => {
    mock(() => json(409, { error: "link_gone", message: "This link has already been used." }));
    openApprover();
    expect(await screen.findByRole("alert")).toHaveTextContent("This link has already been used.");
    expect(screen.queryByText("Capital calls arrive too late")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
  });

  test("too many tries has its own sentence", async () => {
    mock(() => json(429, { error: "too_many_tries", message: "x" }));
    openApprover();
    expect(await screen.findByRole("alert")).toHaveTextContent(T.tooMany);
  });

  test("a link that went stale between reading and deciding says so and leaves the buttons off", async () => {
    mock((c) => (c.url.endsWith("/decision") ? json(409, { error: "link_gone", message: "This link has expired. Please ask for a new one." }) : json(200, draft)));
    openApprover();
    await userEvent.setup().click(await screen.findByRole("button", { name: "Approve" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("expired");
    expect(screen.queryByText(T.approved)).not.toBeInTheDocument();
  });
});
