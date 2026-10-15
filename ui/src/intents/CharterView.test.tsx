import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import CharterView from "./views/CharterView";

// Files 32 and 34: ten pages, the sponsor's signature behind "Are you the sponsor?", read-only once signed, a new version, and the six roles.
// fetch is stubbed with synthetic records.

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const KEYS = ["intent", "wall", "problems", "measures", "processes", "sources", "roles", "build", "parked", "risks"];
const TITLES = ["The intent", "The frozen wall", "Problems", "Measures", "Processes involved", "Data sources", "Who does what", "Build needed", "Parked for later", "Known risks"];
const problem = (over: object = {}) => ({ id: "a1", title: "Call notices arrive late", priority_label: "Must", so_that: "So that calls are funded in time.", so_that_draft: false, tie: null, note_count: 3, ...over });
const pages = (draft = false) => KEYS.map((key, i) => {
  const base = { n: i + 1, key, title: TITLES[i], status: "ok", text: null };
  if (key === "intent") return { ...base, purpose: "Fund calls in time", opened_by: { name: "Janet Shaw", role: "organiser", date: "2026-10-05" }, why: null, areas: ["Finance"], time_box: { starts: null, ends: null } };
  if (key === "wall") return { ...base, lanes: [{ lane: "missing", count: 2, cards: [] }], total: 2, took_part: ["Aaron Lyle"], anonymous: 1, sealed: 0, href: "/centre/intent/i1/wall" };
  if (key === "problems") return { ...base, lists: [{ heading: "Problems to solve now", kind: "intent", items: [problem({ so_that_draft: draft })] }] };
  if (key === "processes") return { ...base, status: "missing", text: "Not available yet: the process map has not been drafted. Waits for file 27." };
  if (key === "build") return { ...base, needed: true, reason: null, by: "Daniel Kerr", at: null, lines: [], passing: null, not_answered: null, not_checked: "Not checked yet. North checks when Define has a charter draft.", href: "/centre/intent/i1/build-ready" };
  if (key === "risks") return { ...base, rows: [{ text: "The developer role is not accepted yet.", accepted_by: null }], accept: true };
  if (key === "roles") return { ...base, rows: [{ role: "developer", label: "Developer", person: "Katie Rao", mark: "Stated", answer: { state: "waiting" } }] };
  return { ...base, rows: [] };
});
const charter = (over: object = {}) => ({
  version: 1, of: 1, state: "Draft", status: "draft", editable: false, current: true, session_id: "s".repeat(32), problems: [problem()],
  approver: { name: null, link: "none", expires_at: null }, returned: null, signature: { needed: "Daniel Kerr", signed_by: null, signed_at: null, how: null },
  can_sign: true, sign_block: null, can_new_version: false, can_discard: false, can_download: false, north: null, handoff: null, ...over });
const data = (viewer: object, c: object = {}, extra: object = {}) => ({
  intent: { id: "i1", title: "Capital calls", purpose: "Fund calls in time", state: "open" }, tier: "content", available: true,
  viewer: { organiser: false, closer: false, company_admin: false, name: "Daniel Kerr", ...viewer }, sponsor: "Daniel Kerr", organiser: "Janet Shaw",
  charter: charter(c), pages: pages(), versions: [{ version: 1, state: "Draft", created_by: "North", created_at: "2026-10-05T09:00:00+00:00", signed_by: null, signed_at: null, comment: null, discarded: null, current: true }],
  roles: { can_edit: false }, role_request: null, ...extra });
const ROLES = { rows: [], footer: "", people: [] };
const CHECK = { id: "i1", title: "Capital calls", type: "initiative", state: "open", level: "full", time_zone: "UTC", n_ok: 0, of: 7, verdict: "not_checked", lines: [], todo: [], message: "Not checked yet." };

const calls: string[] = [];
function mount(body: unknown, path = "/centre/intent/i1/charter") {
  calls.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const m = init?.method ?? "GET";
    calls.push(`${m} ${url}`);
    if (url.endsWith("/roles") || url.includes("/roles/")) return json(200, ROLES);
    if (url.endsWith("/charter/download")) return json(403, { error: "forbidden", message: "You do not have access to this." });
    if (url.endsWith("/build-ready")) return json(200, CHECK);
    return json(200, body);
  }));
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes><Route path="/centre/intent/:intentId/charter" element={<CharterView />} /></Routes>
    </MemoryRouter>,
  );
}
afterEach(() => vi.unstubAllGlobals());

describe("charter", () => {
  it("shows the ten pages in order, with the empty ones worded as the spec says", async () => {
    mount(data({ closer: true }));
    expect(await screen.findByText("Capital calls")).toBeInTheDocument();
    const heads = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    TITLES.forEach((t, i) => expect(heads).toContain(`Page ${i + 1}. ${t}`));
    expect(screen.getByText(/Waits for file 27/)).toBeInTheDocument();
    expect(screen.getByText("Version 1")).toBeInTheDocument();
    expect(screen.getByText("Needs one signature: the sponsor, Daniel Kerr.")).toBeInTheDocument();
  });

  it("the sponsor signs only after answering Are you the sponsor", async () => {
    mount(data({ closer: true }));
    const [sign] = await screen.findAllByRole("button", { name: "Sign the charter" });
    await userEvent.click(sign!);
    const dlg = screen.getByRole("dialog", { name: "Are you the sponsor?" });
    expect(dlg).toHaveTextContent("You are signing as Daniel Kerr, sponsor of Capital calls. Once signed, this version cannot be changed. A change is a new version.");
    await userEvent.click(within(dlg).getByRole("button", { name: "No, go back" }));
    expect(calls.some((c) => c.includes("/charter/sign"))).toBe(false);
    await userEvent.click((await screen.findAllByRole("button", { name: "Sign the charter" }))[0]!);
    await userEvent.click(screen.getByRole("button", { name: "Yes, I am the sponsor. Sign" }));
    expect(calls).toContain("POST /api/intents/i1/charter/sign");
  });

  it("the organiser does not see the sign button; a blocked sponsor sees the reason", async () => {
    mount(data({ organiser: true, name: "Janet Shaw" }));
    await screen.findByText("Capital calls");
    expect(screen.queryByRole("button", { name: "Sign the charter" })).toBeNull();
  });

  it("a blocked sign button is disabled and says why", async () => {
    mount(data({ closer: true }, { can_sign: false, sign_block: "Check the 'so that' lines first." }));
    const [sign] = await screen.findAllByRole("button", { name: "Sign the charter" });
    expect(sign).toBeDisabled();
    expect(screen.getAllByText("Check the 'so that' lines first.").length).toBeGreaterThan(0);
  });

  it("using a line that is no longer a draft says there is nothing to confirm", async () => {
    mount({ ...data({ organiser: true, name: "Janet Shaw" }, { editable: true }), pages: pages(true) });
    await userEvent.click(await screen.findByRole("button", { name: /Use this line/ }));
    expect(await screen.findByText(/nothing to confirm/i)).toBeInTheDocument();
    expect(calls).not.toContain("PUT /api/intents/i1/charter");
  });

  it("a draft North line is marked, and the organiser can use it", async () => {
    mount({ ...data({ organiser: true, name: "Janet Shaw" }, { editable: true, problems: [problem({ so_that_draft: true })] }), pages: pages(true) });
    expect(await screen.findByText("Draft by North")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Use this line/ }));
    expect(calls).toContain("PUT /api/intents/i1/charter");
    expect(screen.getByRole("button", { name: "Save the 'so that' lines" })).toBeDisabled();
  });

  it("signed is read only: no edit fields, no risk boxes, no sign; the organiser may start a new version", async () => {
    mount(data({ organiser: true, name: "Janet Shaw" }, { status: "signed", state: "Signed", can_new_version: true, can_download: true,
      signature: { needed: "Daniel Kerr", signed_by: "Daniel Kerr", signed_at: "2026-10-06T09:00:00+00:00", how: "in the charter" } }));
    expect(await screen.findByText(/Signed by Daniel Kerr on 6 October 2026. Read only. A change is a new version./)).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.queryByRole("checkbox")).toBeNull();
    expect(screen.queryByRole("button", { name: "Sign the charter" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Start a new version" }));
    expect(calls).toContain("POST /api/intents/i1/charter/versions");
  });

  it("a refused download says so in plain words", async () => {
    mount(data({ closer: true }, { status: "signed", state: "Signed", can_download: true }));
    await userEvent.click(await screen.findByText("Download"));
    await userEvent.click(screen.getByRole("button", { name: /Markdown/i }));
    expect(await screen.findByText(/your role cannot download it/)).toBeInTheDocument();
  });

  it("a draft version 2 offers Discard with a reason", async () => {
    mount(data({ organiser: true, name: "Janet Shaw" }, { version: 2, of: 2, can_discard: true, editable: true }));
    await userEvent.click(await screen.findByRole("button", { name: "Discard this draft" }));
    const go = screen.getByRole("button", { name: "Discard it" });
    expect(go).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Why is this draft discarded?"), "Scope did not grow");
    await userEvent.click(go);
    expect(calls).toContain("POST /api/intents/i1/charter/versions/2/discard");
  });

  it("a named person accepts, or declines only with a reason", async () => {
    const row = (state: string) => ({ role: "developer", label: "Developer", duty: "Build the pipelines.", required: true, person_ids: ["p1"], person: "Katie Rao", mark: "Stated", mark_reason: null, answer: { state, at: null, asked_at: "2026-10-06T09:00:00+00:00" } });
    mount({ intent: { id: "i1", title: "Capital calls", purpose: "Fund calls in time", state: "open" }, tier: "named", available: false, charter: null,
      role_request: { intent: { id: "i1", title: "Capital calls", purpose: "Fund calls in time", ends: "2026-10-16T09:00:00+00:00" }, organiser: "Janet Shaw", mine: [row("waiting")], others: [], handed_over: false } });
    expect(await screen.findByText("Janet Shaw has named you as developer for Capital calls")).toBeInTheDocument();
    expect(screen.getByText("You are the first to be named.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Decline" }));
    const send = screen.getByRole("button", { name: "Send decline" });
    expect(send).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Why can you not take it?"), "On leave until 21 Oct");
    await userEvent.click(send);
    expect(calls).toContain("POST /api/intents/i1/roles/developer/answer");
  });

  it("a card-tier viewer sees that the charter exists and nothing else", async () => {
    mount({ intent: { id: "i1", title: "Capital calls", purpose: "Fund calls in time", state: "open" }, tier: "card", available: false, message: "You can see that the charter exists. You can open it if the organiser adds you.", charter: null });
    expect(await screen.findByText("You can see that the charter exists. You can open it if the organiser adds you.")).toBeInTheDocument();
    expect(screen.queryByText("Page 1. The intent")).toBeNull();
  });

  it("page 4 draws the success measure from the hypothesis; the organiser edits target and review date on a draft", async () => {
    const success = { label: "From the hypothesis", measure: { name: "Days to fund" }, baseline: { value: 12, unit: "days" }, target: null, review_date: null, text: "Not available yet: no target, no review date." };
    const d = data({ organiser: true, name: "Janet Shaw" }, { editable: true });
    d.pages = d.pages.map((p) => (p.key === "measures" ? { ...p, success } : p));
    mount(d);
    expect(await screen.findByText("From the hypothesis")).toBeInTheDocument();
    expect(screen.getByText("Baseline: 12 days")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/^Target/), "8");
    await userEvent.click(screen.getByRole("button", { name: "Save target and review date" }));
    expect(calls).toContain("PUT /api/intents/i1/charter");
  });

  it("the success measure is read only once signed", async () => {
    const success = { label: "From the hypothesis", measure: { name: "Days to fund" }, baseline: { value: 12, unit: "days" }, target: { value: 8, unit: "days" }, review_date: "2026-12-01", text: null };
    const d = data({ organiser: true, name: "Janet Shaw" }, { editable: false });
    d.pages = d.pages.map((p) => (p.key === "measures" ? { ...p, success } : p));
    mount(d);
    expect(await screen.findByText("Target: 8 days")).toBeInTheDocument();
    expect(screen.getByText("Review date: 1 December 2026")).toBeInTheDocument();
    expect(screen.queryByLabelText(/^Target/)).toBeNull();
  });
});

// FIXE1: an intent of work has no charter; the old link lands on its signing page.
it("sends a missing charter (404) to the intent's signing page", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(404, { error: "not_found", message: "We could not find that." })));
  render(
    <MemoryRouter initialEntries={["/centre/intent/i1/charter"]}>
      <Routes>
        <Route path="/centre/intent/:intentId/charter" element={<CharterView />} />
        <Route path="/centre/intent/:intentId/sign" element={<p>signing page</p>} />
      </Routes>
    </MemoryRouter>,
  );
  expect(await screen.findByText("signing page")).toBeInTheDocument();
});
