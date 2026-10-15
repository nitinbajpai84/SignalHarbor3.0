import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import CloseView from "./views/CloseView";

// The closure screen (spec 09) and the rating panel (spec 10): organiser, signer and participant views, and the empty states.

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const YOU = { organiser: false, can_start: false, can_back: false, can_edit: false, can_draft: false, can_sign: false, sign_label: "", can_send: false,
  has_link: false, can_close: false, blocked_by: null, can_close_incomplete: false, can_cancel: false };
const BASE = {
  id: "i1", type: "problem", title: "Late sweeps", state: "closing", version: 3, tier: "content", purpose: "Cash sweeps run late", time_zone: "UTC", ends: "9 Oct", late: false,
  opened_by: "Janet", opened_on: "1 Oct", outcome: { lines: [{ label: "Root cause", value: "A late file" }], missing: [] }, strip: null, cancelled: false, cancel: null, closed_on: null,
  why_it_happened: "", send_back: null, next: [{ kind: "nothing", title: "", ref: null, reason: "Fixed" }], links: { from: null, to: [] }, rated: true, you: YOU,
  signature: [{ role: "owner", name: "Harvey", state: "waiting", at: "", how: null }], link_out: null,
  sentences: [{ slot: "purpose", text: "This was opened to fix late sweeps.", sources: [{ label: "Intent record", ref: "intent" }], by: "north", edited_at: null }],
  drafted: true, people: [{ name: "Aaron", role: "participant", label: "Fewer than five", count: null }], anonymous_count: 2,
  panels: { intent: [{ label: "Purpose", value: "Cash sweeps run late" }] }, rating: null,
};

function show(view: object, calls: string[] = []) {
  const f = vi.fn(async (url: string, init?: RequestInit) => {
    calls.push(`${init?.method ?? "GET"} ${url} ${init?.body ?? ""}`);
    return json(200, view);
  });
  vi.stubGlobal("fetch", f);
  render(<MemoryRouter initialEntries={["/centre/intent/i1/close"]}><Routes><Route path="/centre/intent/:intentId/close" element={<CloseView />} /></Routes></MemoryRouter>);
  return calls;
}

describe("Closure screen", () => {
  it("shows the draft with a source chip, the people with a count only, and the signature waiting", async () => {
    show({ ...BASE, you: { ...YOU, organiser: true, can_edit: true, can_draft: true, can_close: false, blocked_by: "Waiting for the owner, Harvey." } });
    expect(await screen.findByText("This was opened to fix late sweeps.")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Intent record" }));
    expect(await screen.findByText("Where this came from")).toBeTruthy();
    expect(screen.queryByText("Fewer than five")).toBeNull(); // W2F2: never beside a named person
    expect(screen.getByText("Participant")).toBeTruthy();
    expect(screen.getByText("Anonymous contributions: 2")).toBeTruthy();
    expect(screen.getByText("Waiting for Harvey")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Close this intent" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText("Waiting for the owner, Harvey.")).toBeTruthy();
  });

  it("sends the sign action for the named signer", async () => {
    const calls = show({ ...BASE, you: { ...YOU, can_sign: true, sign_label: "Confirm the fix" } });
    await userEvent.click(await screen.findByRole("button", { name: "Confirm the fix" }));
    await waitFor(() => expect(calls.some((c) => c.startsWith("PUT /api/intents/i1/closure") && c.includes('"action":"sign"'))).toBe(true));
  });

  it("asks for a reason before it cancels, and the confirm button stays off until there is one", async () => {
    const calls = show({ ...BASE, you: { ...YOU, organiser: true, can_cancel: true } });
    await userEvent.click(await screen.findByRole("button", { name: "Cancel this intent" }));
    const confirm = screen.getByRole("button", { name: "Confirm" }) as HTMLButtonElement;
    expect(confirm.disabled).toBe(true);
    await userEvent.type(screen.getByLabelText("Why is it cancelled? (required)"), "Merged");
    expect(confirm.disabled).toBe(false);
    await userEvent.click(confirm);
    await waitFor(() => expect(calls.some((c) => c.includes('"action":"cancel"') && c.includes('"cancel_reason":"Merged"') && c.includes('"version":3'))).toBe(true));
  });

  it("shows the build-ready strip, and Close without hand-off asks for a reason then sends it", async () => {
    const br = { requirements: [{ key: "build", label: "Say whether Build is needed", done: false, href: "/centre/intent/i1/build-ready" }, { key: "summary", label: "Write the summary", done: true, href: "#close-summary" }], text: "Not build-ready: 3 items missing", n_ok: 4, of: 7, handed: false, href: "/centre/intent/i1/build-ready", can_skip: true, skipped_reason: null };
    const calls = show({ ...BASE, type: "initiative", build_ready: br, you: { ...YOU, organiser: true } });
    expect(await screen.findByText("Not build-ready: 3 items missing")).toBeTruthy();
    expect(screen.getByText("4 of 7 build-ready lines pass")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Close without hand-off" }));
    expect(screen.getByRole("link", { name: "Say whether Build is needed" }).getAttribute("href")).toBe("/centre/intent/i1/build-ready");
    expect(screen.getByText(/Still to do:/)).toBeTruthy();
    expect(screen.getByText(/Done:/)).toBeTruthy();
    const confirm = screen.getByRole("button", { name: "Confirm" }) as HTMLButtonElement;
    expect(confirm.disabled).toBe(true);
    await userEvent.type(screen.getByLabelText("Why is there no hand-off? (required)"), "Charter only");
    await userEvent.click(confirm);
    await waitFor(() => expect(calls.some((c) => c.includes('"no_handoff":true') && c.includes('"reason":"Charter only"'))).toBe(true));
  });

  it("a refusal in the hand-off dialog shows the server's sentence", async () => {
    const br = { requirements: [], text: "Not build-ready", n_ok: 4, of: 7, handed: false, href: "/x", can_skip: true, skipped_reason: null };
    vi.stubGlobal("fetch", vi.fn(async (_u: string, init?: RequestInit) => (init?.method === "PUT"
      ? json(409, { detail: "Waiting for the sponsor, Daniel Kerr.", message: "Waiting for the sponsor, Daniel Kerr." })
      : json(200, { ...BASE, type: "initiative", build_ready: br, you: { ...YOU, organiser: true } }))));
    render(<MemoryRouter initialEntries={["/centre/intent/i1/close"]}><Routes><Route path="/centre/intent/:intentId/close" element={<CloseView />} /></Routes></MemoryRouter>);
    await userEvent.click(await screen.findByRole("button", { name: "Close without hand-off" }));
    await userEvent.type(screen.getByLabelText("Why is there no hand-off? (required)"), "Charter only");
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect((await screen.findAllByText("Waiting for the sponsor, Daniel Kerr.")).length).toBeGreaterThan(0);
  });

  it("a closed intent has no action buttons, and a Weekly check-in has no rating panel", async () => {
    show({ ...BASE, state: "closed", closed_on: "7 Oct", strip: "Closed by Janet on 7 Oct.", type: "pulse", rated: false, signature: [], rating: null, you: YOU });
    expect(await screen.findByText("Closed by Janet on 7 Oct.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Close this intent" })).toBeNull();
    expect(screen.queryByText("Rate it")).toBeNull();
    expect(screen.getByText("This type needs no signature. Closed by Janet.")).toBeTruthy();
  });

  it("the rating prompt is anonymous by default and sends the score", async () => {
    const rating = { window_open: true, drop_at: "2026-10-14", dropped: false, can_rate: true, rated_by_you: false, waived: false, mine: null, summary: null, used: null };
    const calls = show({ ...BASE, state: "closed", closed_on: "7 Oct", strip: "Closed by Janet on 7 Oct.", signature: [], rating });
    expect(await screen.findByText("Anonymous. Nobody else can see who gave this rating.")).toBeTruthy();
    const send = screen.getByRole("button", { name: "Send rating" }) as HTMLButtonElement;
    expect(send.disabled).toBe(true);
    await userEvent.click(screen.getByRole("button", { name: /^4/ }));
    await userEvent.click(send);
    await waitFor(() => expect(calls.some((c) => c.startsWith("POST /api/intents/i1/ratings") && c.includes('"anonymous":true') && c.includes('"score":4'))).toBe(true));
  });

  it("the organiser of a closed brainstorm with a chosen idea starts the Initiative from the next row", async () => {
    const calls: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      calls.push(`${init?.method ?? "GET"} ${url}`);
      if (init?.method === "POST") return json(200, { created: [{ link_id: "l1", target: { kind: "initiative", id: "ini-new" } }] });
      return json(200, { ...BASE, type: "brainstorm", state: "closed", closed_on: "2 Oct", signature: [], outcome: { lines: [{ label: "Chosen idea", value: "Read the mailbox" }], missing: [] },
        next: [{ kind: "initiative", title: "", ref: null, reason: "Nobody has opened the Initiative yet." }], you: { ...YOU, organiser: true } });
    }));
    render(<MemoryRouter initialEntries={["/centre/intent/i1/close"]}><Routes><Route path="/centre/intent/:intentId/close" element={<CloseView />} />
      <Route path="/centre/intent/new" element={<p>start flow</p>} /></Routes></MemoryRouter>);
    await userEvent.click(await screen.findByRole("button", { name: "Start the Initiative" }));
    expect(await screen.findByText("start flow")).toBeTruthy();
    expect(calls).toContain("POST /api/intents/i1/next");
  });

  it("a participant sees no Start the Initiative", async () => {
    show({ ...BASE, type: "brainstorm", state: "closed", closed_on: "2 Oct", signature: [], outcome: { lines: [{ label: "Chosen idea", value: "Read the mailbox" }], missing: [] },
      next: [{ kind: "initiative", title: "", ref: null, reason: "Nobody has opened the Initiative yet." }] });
    expect(await screen.findByText("Nobody has opened the Initiative yet.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Start the Initiative" })).toBeNull();
  });

  it("shows no mean before three ratings", async () => {
    const summary = { asked: 6, rated: 2, count: 2, mean: null, bar: null, signed: [], anonymous_count: 2, empty: null, hidden: "Not shown until three people have rated (2 so far)." };
    show({ ...BASE, state: "closed", closed_on: "7 Oct", signature: [], rating: { window_open: true, drop_at: "2026-10-14", dropped: false, can_rate: false, rated_by_you: false, waived: false, mine: null, summary, used: null } });
    expect(await screen.findByText("Not shown until three people have rated (2 so far).")).toBeTruthy();
    expect(screen.getByText("2 of 6 have rated")).toBeTruthy();
  });
});
