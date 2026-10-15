import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../theme";
import VisitorView from "./VisitorView";
import ShareView from "./views/ShareView";

// Spec 11: the share panel and the visitor view. fetch is stubbed with synthetic data.

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const PANEL = {
  intent: { id: "ini-1", title: "Quarterly valuation review", state: "closed" }, guard: null, company: "Ardmore Family Office",
  never: ["Sealed cards (a count only)"], areas: [{ area: "Operations", head_count: 2 }],
  people: [{ id: "harvey", name: "Harvey Rowley", role: "Owner", department: "Operations", status: "pickable" },
    { id: "pat", name: "Pat Tan", role: "Analyst", department: "Finance", status: "in_intent" }],
  entries: [], counts: { people: 0, areas: 0, links: 0, opened: 0, of: 0, notes: 0, unread: 0, live: 0 }, opens: [], notes: [],
};
const VISIT = {
  banner: { organiser: "Janet Shaw", ends: "2026-11-01T23:59:59+00:00" },
  intent: { title: "Quarterly valuation review", purpose: "Check the second valuation", type: "initiative", state: "closed", areas: [] },
  people: [{ name: "Janet Shaw", role: "Organiser" }], stages: [], wall: { kind: "wall", lanes: [{ lane: "tracking", cards: [{ text: "A card", author: "Anonymous" }] }] },
  outcome: null, sealed: 2, restricted: 0, closure: null, cancelled: null, note_max: 1000,
};

const calls: { method: string; url: string; body: unknown; headers: Record<string, string> }[] = [];
function mock(visit: Response | null = null) {
  calls.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ method: init?.method ?? "GET", url, body: init?.body ? JSON.parse(String(init.body)) : null, headers: (init?.headers ?? {}) as Record<string, string> });
    if (url.endsWith("/share") && (init?.method ?? "GET") === "GET") return json(200, PANEL);
    if (url.endsWith("/share")) return json(200, { ...PANEL, link: { url: "http://x/centre/shared/t/sh-ini-1-abc", expires_at: "2026-11-01T23:59:59+00:00" } });
    if (url.endsWith("/shared/view")) return visit ?? json(200, VISIT);
    return json(200, { sent: true, to: "Janet Shaw" });
  }));
}
afterEach(() => vi.unstubAllGlobals());

function organiser() {
  return render(<ThemeProvider><MemoryRouter initialEntries={["/centre/intent/ini-1/share"]}>
    <Routes><Route path="/centre/intent/:intentId/share" element={<ShareView />} /></Routes></MemoryRouter></ThemeProvider>);
}
function visitor(path: string) {
  return render(<ThemeProvider><MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/centre/shared/:intentId" element={<VisitorView />} /><Route path="/centre/shared/t/:token" element={<VisitorView />} /></Routes></MemoryRouter></ThemeProvider>);
}

test("Share stays off until a row and an expiry exist; the link is shown once", async () => {
  mock(); organiser();
  const share = await screen.findByRole("button", { name: "Share" });
  expect(share).toBeDisabled();
  expect(screen.getByText("Already in this intent")).toBeInTheDocument();
  expect(screen.getByText("Nothing chosen yet.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Make a link for anyone signed in to the company" }));
  expect(share).toBeDisabled();
  fireEvent.change(document.querySelector("input[type=date]") as HTMLInputElement, { target: { value: "2026-11-01" } });
  expect(share).toBeEnabled();
  fireEvent.click(share);
  expect(await screen.findByText(/We keep only a fingerprint/)).toBeInTheDocument();
  expect(calls.find((c) => c.method === "POST")?.body).toEqual({ targets: [{ kind: "link", target: null }], expires_at: "2026-11-01" });
});

test("a visitor by name sends the id in the body; a link sends the token in the header only", async () => {
  mock(); visitor("/centre/shared/ini-1");
  expect(await screen.findByText(/Read only\. Janet Shaw can see that you opened it/)).toBeInTheDocument();
  expect(screen.getByText("2 sealed cards are not shown.")).toBeInTheDocument();
  expect(calls[0]?.body).toEqual({ intent_id: "ini-1" });
  vi.unstubAllGlobals(); mock(); visitor("/centre/shared/t/sh-ini-1-tok");
  await screen.findByText("Quarterly valuation review");
  expect(calls[0]?.body).toEqual({}) ;
  expect(calls[0]?.url).not.toContain("tok");
  expect(calls[0]?.headers["X-Session-Token"]).toBe("sh-ini-1-tok");
});

test("a note needs words, then says where it went", async () => {
  mock(); visitor("/centre/shared/ini-1");
  const send = await screen.findByRole("button", { name: "Send note" });
  expect(send).toBeDisabled();
  expect(screen.getByText("This goes to Janet Shaw's record. It does not go into the session.")).toBeInTheDocument();
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "Which fund?" } });
  fireEvent.click(send);
  await waitFor(() => expect(screen.getByText("Sent to Janet Shaw.")).toBeInTheDocument());
});

test("an ended share says so in plain words", async () => {
  mock(json(409, { error: "share_ended", message: "This share has ended." })); visitor("/centre/shared/ini-1");
  expect(await screen.findByText("This share has ended.")).toBeInTheDocument();
});
