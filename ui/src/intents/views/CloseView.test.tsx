import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, test, vi } from "vitest";

import CloseView from "./CloseView";
import { closeCopy as t } from "./closeCopy";

// FX1: the decider on the closure screen of a Decision. fetch is stubbed; synthetic text only.
const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
const you = { organiser: false, can_start: false, can_back: false, can_edit: false, can_draft: false, can_sign: true, sign_label: "Decide", can_send: false,
  has_link: false, can_close: false, blocked_by: null, can_close_incomplete: false, can_cancel: false };
const view = (reason: string, asked: boolean) => ({
  id: "dec-1", type: "decision", title: "FX1 Which valuation date", state: "closing", version: 4, tier: "content", purpose: "Daniel decides", time_zone: "UTC",
  ends: "9 Oct", late: false, opened_by: "Janet Shaw", opened_on: "7 Oct", strip: null, cancelled: false, cancel: null, closed_on: null, why_it_happened: "",
  outcome: { lines: [{ label: "Decision", value: "Use month-end" }], missing: [] }, send_back: null, links: { from: null, to: [] }, rated: true, you,
  asked_again: asked ? { by: "Janet Shaw", at: "2026-10-07T08:00:00+00:00", roles: ["decider"] } : null,
  next: [{ kind: "nothing", title: "", ref: null, reason }], signature: [{ role: "decider", name: "Daniel Kerr", state: "waiting", at: "", how: null }], link_out: null,
  sentences: [{ slot: "summary", text: "Decided: Use month-end. By Daniel Kerr.", sources: [{ label: "Outcome", ref: "outcome" }], by: "north", edited_at: null }],
  people: [{ name: "Janet Shaw", role: "organiser", label: "Fewer than five" }, { name: "Daniel Kerr", role: "decider", label: "Fewer than five" }],
});
const sent: string[] = [];
function mock(reason: string, asked = false) {
  sent.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "PUT") sent.push(String(init.body));
    return url === "/api/intents/dec-1/closure" ? json(view(reason, asked)) : json({});
  }));
}
const open = () => render(<MemoryRouter initialEntries={["/centre/intent/dec-1/close"]}><Routes><Route path="/centre/intent/:intentId/close" element={<CloseView />} /></Routes></MemoryRouter>);
afterEach(() => vi.unstubAllGlobals());

describe("the decider on the closure screen", () => {
  test("the option name and the summary show; Decide works once the next row has its reason", async () => {
    mock("The decision itself is the outcome.", true);
    open();
    expect(await screen.findByText("Use month-end")).toBeInTheDocument();
    expect(screen.queryByText(t.notDrafted)).toBeNull();
    expect(screen.getByText(t.askedAgain("Janet Shaw"))).toBeInTheDocument();
    const btn = screen.getByRole("button", { name: "Decide" });
    expect(btn).toBeEnabled();
    expect(screen.queryByText(t.checkFirst)).toBeNull();
    await userEvent.click(btn);
    expect(sent.some((b) => b.includes('"action":"sign"'))).toBe(true);
  });

  test("an empty next reason names the organiser instead of a check the decider cannot do", async () => {
    mock("");
    open();
    expect(await screen.findByText(t.waitNext("Janet Shaw"))).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Decide" })).toBeDisabled();
    expect(screen.queryByText(t.checkFirst)).toBeNull();
  });
});

test("a closed intent's header clock says Closed, never a countdown", async () => {
  const { clockLabel, headerCopy } = await import("../IntentHeader");
  expect(clockLabel("2099-01-01T00:00:00Z", "closed")).toBe(headerCopy.closed);
  expect(clockLabel("2099-01-01T00:00:00Z", "cancelled")).toBe(headerCopy.cancelled);
});
