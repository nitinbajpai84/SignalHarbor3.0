import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import BaselineSignoff from "./BaselineSignoff";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const kpi = (id: string, name: string) => ({ id, name, priority: "must", parts: [] });
const gm = (id: string, governed: boolean, missing: string[] = []) => ({ id, name: id, state: {}, governed, missing });
const PCTS = { owned: 50, classified: 100, may_see_confirmed: 50, sealed: 0 };

function mock(review: object, governed: object, onPost?: (url: string) => void) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") { onPost?.(url); return json(200, { ...review, status: "signed" }); }
    if (url.endsWith("/review")) return json(200, review);
    if (url.endsWith("/governed")) return json(200, governed);
    return json(404, {});
  }));
}
const base = { baseline_id: "b1", version: 1, status: "open", signatures: [], waiting_for: ["Sponsor", "Head of data"], can_countersign: true, viewer: { name: "Sam", sponsor: true, can_settle: true, slot: "sponsor" }, kpis: [kpi("K1", "Capital calls"), kpi("K2", "Exposure")] };

afterEach(() => { vi.unstubAllGlobals(); });

test("gate not met shows what is missing and blocks signing", async () => {
  mock(base, { measures: [gm("K1", true), gm("K2", false, ["owners"])], percentages: PCTS });
  render(<BaselineSignoff baselineId="b1" />);
  expect(await screen.findByText("Exposure: owners not stated yet")).toBeInTheDocument();
  expect(screen.getByText("Owned: 50%")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Sign" })).toBeNull();
  expect(screen.getByText("You can sign once every Must measure is governed.")).toBeInTheDocument();
});

test("the sponsor can sign when every Must measure is governed", async () => {
  const posts: string[] = [];
  mock(base, { measures: [gm("K1", true), gm("K2", true)], percentages: PCTS }, (u) => posts.push(u));
  render(<BaselineSignoff baselineId="b1" />);
  expect(await screen.findByText("Waiting for Sponsor")).toBeInTheDocument();
  const btn = screen.getByRole("button", { name: "Sign" });
  expect(btn).toBeEnabled();
  await userEvent.click(btn);
  expect(posts[0]).toMatch(/\/baselines\/b1\/countersign$/);
});

test("a signed baseline is read-only and says by whom and when", async () => {
  const signed = { ...base, status: "signed", waiting_for: [], signatures: [{ slot: "sponsor", label: "Sponsor", name: "Sam Sponsor", at: "2026-10-01T09:00:00Z" }, { slot: "head", label: "Head of data", name: "Hana Head", at: "2026-10-02T09:00:00Z" }] };
  mock(signed, { measures: [gm("K1", true), gm("K2", true)], percentages: PCTS });
  render(<BaselineSignoff baselineId="b1" />);
  expect(await screen.findByText("Signed by Sam Sponsor (Sponsor) · 1 October 2026")).toBeInTheDocument();
  expect(screen.queryByRole("button")).toBeNull();
});

test("the gate lists what is missing, in plain words, and only for Must measures not governed", async () => {
  const review = { ...base, kpis: [kpi("K1", "Capital calls"), kpi("K2", "Exposure"), { ...kpi("K3", "Fees charged"), priority: "should" }] };
  mock(review, { measures: [gm("K1", true), gm("K2", false, ["may_see", "review_date"]), gm("K3", false, ["owners"])], percentages: PCTS });
  render(<BaselineSignoff baselineId="b1" />);
  expect(await screen.findByText("1 of 2 Must measures governed")).toBeInTheDocument();
  const list = screen.getByRole("list", { name: "Not governed yet" });
  expect(list).toHaveTextContent("Exposure: who may see, review date not stated yet");
  expect(list).not.toHaveTextContent("Capital calls");
  expect(list).not.toHaveTextContent("Fees charged");
  expect(screen.getByRole("progressbar", { name: "Owned" })).toHaveAttribute("value", "50");
});
