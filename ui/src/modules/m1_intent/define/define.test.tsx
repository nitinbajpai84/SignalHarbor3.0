import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import type { TogetherCluster, TogetherView } from "../api";
import { m1Define as d } from "./copy";
import DefineScreen from "./DefineScreen";
import { cellText } from "./LensPanel";

// IC-3s: the Define screen. Five states, shelves, ring states, Future needs a reason, read-only for everyone but the organiser.

const SID = "d".repeat(32);
const BASE = `/api/modules/m1_intent/sessions/${SID}`;
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const cluster = (over: Partial<TogetherCluster> = {}): TogetherCluster => ({
  id: "c1", name: "Calls arrive too late", note_count: 6, agree_count: 0, comment_count: 0,
  votes: { must: 3, should: 1, could: 0, not_this_time: 0 }, vote_total: 4, priority: "must", ticked: true, my_vote: null, my_agree: false,
  comments: [], notes: [], shelf: "must", colour: 1, ...over,
});
const view = (over: Partial<TogetherView> = {}): TogetherView => ({
  stage: "together", paused_from: null, held: false, organiser: true, can_vote: true, options: [],
  clusters: [cluster(), cluster({ id: "c2", name: "Nobody owns the list", note_count: 2, shelf: "future", shelf_reason: "Wait for the new system", review_date: "2027-01-06", governed: true })],
  on_its_own_count: 0, ticked_count: 1, open_count: 1, i_done: false, done_count: 0, people_count: 3, ...over,
});
const calls: { method: string; url: string; body: unknown }[] = [];
function serve(get: () => Response | Promise<Response>, after?: (url: string, method: string) => Response | undefined) {
  calls.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    if (url === `${BASE}/together` && method === "GET") return get();
    if (url === `${BASE}/timer`) return json(200, { stage: "together", timed: false, now: "z" });
    return after?.(url, method) ?? json(404, {});
  }));
}
const open = () => render(<MemoryRouter initialEntries={[`/s/${SID}`]}><Routes><Route path="/s/:sessionId" element={<DefineScreen />} /></Routes></MemoryRouter>);
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

test("loading", () => { serve(() => new Promise<Response>(() => {})); open(); expect(screen.getByRole("status")).toBeInTheDocument(); });
test("error", async () => { serve(() => json(500, {})); open(); expect(await screen.findByRole("button", { name: /try again/i })).toBeInTheDocument(); });
test("refused", async () => { serve(() => json(403, { detail: "No" })); open(); await screen.findByText(d.title); expect(screen.queryByRole("heading", { name: "MUST" })).toBeNull(); });
test("empty", async () => { serve(() => json(200, view({ clusters: [] }))); open(); expect(await screen.findByText(d.empty)).toBeInTheDocument(); });
test("populated: header, shelves, counts, sentence", async () => {
  serve(() => json(200, view({ clusters: [cluster({ measure_codes: ["k1", "k2"] }), cluster({ id: "c2", name: "Other", note_count: 2, shelf: "should", measure_codes: ["k2"] })] })));
  open();
  expect(await screen.findByText(d.sub)).toBeInTheDocument();
  expect(screen.getByText(d.crumbs[1])).toBeInTheDocument();
  expect(screen.getByText(d.counts(8, 2, 2))).toBeInTheDocument();
  for (const s of d.shelves) expect(screen.getByRole("heading", { name: s.label })).toBeInTheDocument();
  expect(screen.getByText(d.people(3))).toBeInTheDocument();
});
test("ring: dashed with the missing text when governed is absent, solid when true", async () => {
  serve(() => json(200, view()));
  open();
  const a = (await screen.findByRole("button", { name: d.select("Calls arrive too late") })).closest("[data-cluster]") as HTMLElement;
  expect(a.querySelector("[data-ring]")).toHaveAttribute("data-ring", "dashed");
  expect(a.querySelector("[data-ring]")).toHaveTextContent(d.ringMissing);
  const b = screen.getByRole("button", { name: d.select("Nobody owns the list") }).closest("[data-cluster]") as HTMLElement;
  expect(b.querySelector("[data-ring]")).toHaveAttribute("data-ring", "solid");
});
test("tiles read Not available yet, never 0, and decisions left comes from served data", async () => {
  serve(() => json(200, view()));
  open();
  await screen.findByText(d.sub);
  const tile = (name: string) => screen.getByText(name).parentElement as HTMLElement;
  expect(within(tile(d.tiles.decisions)).getByText("1")).toBeInTheDocument();
  for (const n of [d.tiles.owners, d.tiles.unchanged, d.tiles.glossary, d.tiles.sealed]) expect(within(tile(n)).getByText(d.notYet)).toBeInTheDocument();
});
test("moving to a shelf calls the route", async () => {
  serve(() => json(200, view()), (u, m) => (u === `${BASE}/together/clusters/c1/shelf` && m === "POST" ? json(200, view({ clusters: [cluster({ shelf: "should" })] })) : undefined));
  open();
  await userEvent.selectOptions(await screen.findByLabelText(d.moveTo("Calls arrive too late")), "should");
  await waitFor(() => expect(calls.find((c) => c.url.endsWith("/c1/shelf"))?.body).toEqual({ shelf: "should" }));
});
test("Future asks for a reason first, shows the review date, then sends it", async () => {
  serve(() => json(200, view()), (u) => (u.endsWith("/c1/shelf") ? json(200, view()) : undefined));
  open();
  await userEvent.selectOptions(await screen.findByLabelText(d.moveTo("Calls arrive too late")), "future");
  expect(calls.some((c) => c.url.endsWith("/shelf"))).toBe(false);
  expect(screen.getByText(/^Review date: \d{4}-\d{2}-\d{2}$/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: d.futureSave }));
  expect(screen.getByRole("alert")).toHaveTextContent(d.futureNeed);
  await userEvent.type(screen.getByLabelText(d.futureReason), "Wait for the new system");
  await userEvent.click(screen.getByRole("button", { name: d.futureSave }));
  await waitFor(() => expect(calls.find((c) => c.url.endsWith("/c1/shelf"))?.body).toEqual({ shelf: "future", reason: "Wait for the new system" }));
});
test("Future shelf lists reason, review date and the footer", async () => {
  serve(() => json(200, view()));
  open();
  expect(await screen.findByText(d.parkedReason("Wait for the new system"))).toBeInTheDocument();
  expect(screen.getByText(d.reviewOn("2027-01-06"))).toBeInTheDocument();
  expect(screen.getByText(d.footer)).toBeInTheDocument();
});
test("a non-organiser sees the shelves read-only", async () => {
  serve(() => json(200, view({ organiser: false })));
  open();
  await screen.findByText(d.sub);
  expect(screen.queryByLabelText(d.moveTo("Calls arrive too late"))).toBeNull();
  expect(document.querySelector("[draggable=true]")).toBeNull();
  expect(screen.getByText(d.readOnly)).toBeInTheDocument();
});
test("Lens panel: definitions with provenance, confirm calls module 2", async () => {
  const kpi = { kpi_id: "k1", name: "Cash call lag", definition: "Days from call to cash", confirmed: null, complete: true, missing: [], open: 0, ready: { ready: true, reasons: [], label: "" },
    parts: [{ part: "calculation", label: "Calculation", cell: { value: "paid minus called", mark: "stated", by: "Ada", at: "t", from: "answer" }, links: [], proposal: null, withheld: false }] };
  serve(() => json(200, view({ baseline_id: "b1", clusters: [cluster({ measure_codes: ["k1"] })] })), (u, m) => {
    if (u.endsWith("/baselines/b1/technical") && m === "GET") return json(200, { kpis: [kpi] });
    if (u.endsWith("/baselines/b1/kpis/k1/technical/confirm")) return json(200, { kpis: [kpi] });
    return undefined;
  });
  open();
  await userEvent.click(await screen.findByRole("button", { name: d.select("Calls arrive too late") }));
  expect(await screen.findByText("Days from call to cash")).toBeInTheDocument();
  expect(screen.getByText("paid minus called")).toBeInTheDocument();
  expect(screen.getByText(/Stated · Ada/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: d.lens.confirm }));
  await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.url.endsWith("/kpis/k1/technical/confirm"))).toBe(true));
});

const six = ["owners", "classification", "may_see", "resolving", "affects", "review_date"];
const governedBody = (missing: string[]) => ({
  measures: [{ id: "k1", name: "Cash call lag", state: {}, governed: missing.length === 0, missing }],
  percentages: { owned: 40, classified: 0, may_see_confirmed: 0, sealed: 0 },
});
const techKpi = { kpi_id: "k1", name: "Cash call lag", definition: "Days", confirmed: null, complete: true, missing: [], open: 0, ready: { ready: true, reasons: [], label: "" }, parts: [] };

test("Lens panel: the governed block shows n of 6 with the missing fields flagged", async () => {
  serve(() => json(200, view({ baseline_id: "b1", clusters: [cluster({ measure_codes: ["k1"], governed: false, missing: ["owners", "may_see"] })] })), (u) => {
    if (u.endsWith("/baselines/b1/technical")) return json(200, { kpis: [techKpi] });
    if (u.endsWith("/baselines/b1/governed")) return json(200, governedBody(["owners", "may_see"]));
    return undefined;
  });
  open();
  await userEvent.click(await screen.findByRole("button", { name: d.select("Calls arrive too late") }));
  const block = await screen.findByLabelText(`${d.lens.governedTitle}: Cash call lag`);
  expect(within(block).getByText(d.lens.governedCount(4))).toBeInTheDocument();
  for (const f of six) expect(block.querySelector(`[data-field=${f}]`)).toHaveAttribute("data-missing", String(f === "owners" || f === "may_see"));
  const card = screen.getByRole("button", { name: d.select("Calls arrive too late") }).closest("[data-cluster]") as HTMLElement;
  expect(card.querySelector("[data-ring]")).toHaveAttribute("data-ring", "dashed");
  expect(card.querySelector("[data-ring]")).toHaveTextContent("Needs an owner and who may see");
});
test("Lens panel: send back opens a note prompt and calls the route", async () => {
  serve(() => json(200, view({ baseline_id: "b1", clusters: [cluster({ measure_codes: ["k1"] })] })), (u, m) => {
    if (u.endsWith("/baselines/b1/technical")) return json(200, { kpis: [techKpi] });
    if (u.endsWith("/baselines/b1/measures/k1/send-back") && m === "POST") return json(200, { kpis: [{ ...techKpi, sent_back: { note: "Which rate date?", label: "Sent back: Which rate date?" } }] });
    return undefined;
  });
  open();
  await userEvent.click(await screen.findByRole("button", { name: d.select("Calls arrive too late") }));
  await userEvent.click(await screen.findByRole("button", { name: d.lens.sendBack }));
  await userEvent.type(screen.getByLabelText(d.lens.sendBackLabel), "Which rate date?");
  await userEvent.click(screen.getByRole("button", { name: d.lens.sendBackSend }));
  await waitFor(() => expect(calls.find((c) => c.url.endsWith("/measures/k1/send-back"))?.body).toEqual({ note: "Which rate date?" }));
  expect(await screen.findByText(d.lens.sentBack("Which rate date?"))).toBeInTheDocument();
});
test("a refused shelf move shows the server's sentence as a plain line", async () => {
  const sentence = "Needs an owner and who may see before it can sit on Must.";
  serve(() => json(200, view()), (u, m) => (u.endsWith("/c1/shelf") && m === "POST" ? json(422, { error: "invalid", message: sentence }) : undefined));
  open();
  await userEvent.selectOptions(await screen.findByLabelText(d.moveTo("Calls arrive too late")), "should");
  expect(await screen.findByRole("alert")).toHaveTextContent(sentence);
});
test("the tiles read owners confirmed and glossary terms from module 2 where available", async () => {
  serve(() => json(200, view({ baseline_id: "b1" })), (u) => {
    if (u.endsWith("/baselines/b1/governed")) return json(200, governedBody(["owners"]));
    if (u.endsWith("/baselines/b1/glossary")) return json(200, { built: true, counts: { all: 12 } });
    return undefined;
  });
  open();
  await screen.findByText(d.sub);
  const tile = (name: string) => screen.getByText(name).parentElement as HTMLElement;
  await waitFor(() => expect(within(tile(d.tiles.owners)).getByText("40%")).toBeInTheDocument());
  expect(within(tile(d.tiles.glossary)).getByText("12")).toBeInTheDocument();
});

const two = () => view({ clusters: [cluster({ topic: "Treasury" }), cluster({ id: "c2", name: "Nobody owns the list", shelf: "should", topic: "Reporting" })] });
test("topics: each cluster shows its chip and All topics plus one chip per topic", async () => {
  serve(() => json(200, two()));
  open();
  await screen.findByRole("button", { name: d.select("Calls arrive too late") });
  expect(screen.getAllByTestId("topic").map((x) => x.textContent)).toEqual(["Treasury", "Reporting"]);
  const bar = screen.getByRole("group", { name: d.topicFilter });
  expect(within(bar).getAllByRole("button").map((b) => b.textContent)).toEqual([d.allTopics, "Treasury", "Reporting"]);
});
test("topics: choosing a topic keeps only its clusters; All topics brings them back", async () => {
  serve(() => json(200, two()));
  open();
  await screen.findByRole("button", { name: d.select("Calls arrive too late") });
  await userEvent.click(within(screen.getByRole("group", { name: d.topicFilter })).getByRole("button", { name: "Reporting" }));
  expect(screen.queryByRole("button", { name: d.select("Calls arrive too late") })).toBeNull();
  expect(screen.getByRole("button", { name: d.select("Nobody owns the list") })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: d.allTopics }));
  expect(screen.getByRole("button", { name: d.select("Calls arrive too late") })).toBeInTheDocument();
});
test("topics: one topic or none changes nothing on screen", async () => {
  serve(() => json(200, view({ clusters: [cluster({ topic: "Treasury" }), cluster({ id: "c2", name: "Other", topic: "Treasury" })] })));
  open();
  await screen.findByRole("button", { name: d.select("Calls arrive too late") });
  expect(screen.queryByTestId("topic")).toBeNull();
  expect(screen.queryByRole("group", { name: d.topicFilter })).toBeNull();
});

test("a sealed cluster shows as a silhouette: no words, sealed votes, its codes, and Lens shows no definitions", async () => {
  const sealedNote = { id: "n1", text: "A sealed card", anonymous: true, mine: false, sealed: true } as TogetherCluster["notes"][number];
  serve(() => json(200, view({ baseline_id: "b1", clusters: [cluster(), cluster({ id: "c9", name: "A sealed cluster", notes: [sealedNote], vote_total: 6, measure_codes: ["K18"] })] })));
  open();
  const card = (await screen.findByRole("button", { name: d.select("A sealed cluster") })).closest("[data-cluster]") as HTMLElement;
  expect(card).toHaveAttribute("data-sealed", "true");
  expect(within(card).getByText(d.sealedMeta(6))).toBeInTheDocument();
  expect(within(card).getByText("K18")).toBeInTheDocument();
  expect(within(card).getByText(d.sealedLine)).toBeInTheDocument();
  await userEvent.click(within(card).getByRole("button", { name: d.select("A sealed cluster") }));
  expect(screen.getByText(d.sealedLens)).toBeInTheDocument();
  expect(calls.some((c) => c.url.includes("/technical"))).toBe(false);
});

test("a closed session is kept as locked: no lock, no moves, the lock date and a link to the charter", async () => {
  serve(() => json(200, view({ stage: "closed" })), (url) =>
    url === `${BASE}/charter` ? json(200, { charter: { versions: [{ version: 1, status: "signed", created_at: "2026-04-17T05:00:00Z" }] } }) : undefined);
  open();
  expect(await screen.findByText(d.closedLine("2026-04-17T05:00:00Z"))).toBeInTheDocument();
  expect(screen.getByText(/Shelves locked on 17 April 2026\./)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: d.lock })).toBeNull();
  expect(screen.queryByRole("combobox")).toBeNull();
  expect(screen.queryByText(d.dropHere)).toBeNull();
  expect(screen.getByRole("link", { name: d.openCharter })).toHaveAttribute("href", `/centre/intent/charter/${SID}`);
});

test("a cluster's measures come from the signed baseline's work list, over the pack's suggestion", async () => {
  serve(() => json(200, view({ clusters: [cluster({ measure_codes: ["K09"], baseline_id: "b1" } as Partial<TogetherCluster>)] })), (url) =>
    url === "/api/modules/m2_baseline/baselines/b1" ? json(200, { problems: [{ id: "c1", title: "x", priority: null, kpi_ids: ["K01", "K04"], has_kpi: true }] }) : undefined);
  open();
  expect(await screen.findByText(d.counts(6, 1, 2))).toBeInTheDocument();
  expect(screen.getByLabelText(d.measures(["K01", "K04"]))).toBeInTheDocument();
});

test("governed values as module 2 keeps them: owners and who resolves it are objects, an empty stated list is not a gap", () => {
  expect(cellText({ value: { business: "Ethan Ng", data: "Harvey Rowley", process: "Ethan Ng" }, mark: "stated" })).toBe("Ethan Ng · Harvey Rowley · Ethan Ng");
  expect(cellText({ value: { team: "Treasury", target_week: 44 }, mark: "stated" })).toBe("Treasury · week 44");
  expect(cellText({ value: [], mark: "stated" })).toBe(d.lens.noneNamed);
  expect(cellText({ value: null, mark: "unknown" })).toBe(d.notYet);
});
