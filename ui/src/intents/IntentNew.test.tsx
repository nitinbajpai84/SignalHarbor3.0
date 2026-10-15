import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

import { ThemeProvider } from "../theme";
import IntentNew from "./IntentNew";

// The chooser (spec 03). fetch is stubbed with synthetic data.

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const ty = (title: string, days: number) => ({ title, chooser_line: `${title} line`, open_button: "Open", time_box_days: days, start_questions: [] });
const CAT = { version: 1, types: { initiative: ty("Initiative", 10), brainstorm: ty("Brainstorm", 3), pulse: ty("Weekly check-in", 5), problem: ty("Problem", 5), decision: ty("Decision", 2) } };
const DRAFTS = [{ id: "d1", type: "problem", title: "Late capital call report", draft_updated_at: "2026-10-06T09:00:00Z" }];

function Where() { const l = useLocation(); return <p data-testid="where">{l.pathname + l.search}</p>; }
function mock(drafts: unknown[] | "fail" = DRAFTS, cat: unknown = CAT, classify = 200) {
  const posts: { url: string; body: Record<string, unknown> }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST" || init?.method === "PUT") {
      const body = init.body ? JSON.parse(String(init.body)) : {};
      posts.push({ url, body });
      if (url === "/api/intents") return json(201, { id: "n1" });
      if (url === "/api/intents/classify") return json(classify, { type: "brainstorm", reason: "It asks people to think of ideas together.", confidence: "Likely", title: "Ideas for investor day" });
      return json(200, {});
    }
    if (url === "/api/auth/me") return json(200, { display_name: "Janet Shaw", company_id: "co-a", roles: ["company_admin"] });
    if (url === "/api/company") return json(200, { company_id: "co-a", name: "Lakeside Test Co", industry: "family_office" });
    if (url === "/api/intents/types") return json(200, cat);
    if (url.startsWith("/api/intents/problem/start")) return json(200, { people: [], areas: [], catalogue: [], chips: [], prefill: {} });
    if (url === "/api/intents/d1") return json(200, { id: "d1", version: 4 });
    if (url.startsWith("/api/intents?")) return drafts === "fail" ? json(501, {}) : json(200, { intents: drafts });
    return json(200, {});
  }));
  return posts;
}
function view(at = "/centre/intent/new") {
  return render(
    <ThemeProvider><MemoryRouter initialEntries={[at]}>
      <Routes><Route path="/centre/intent/new" element={<><IntentNew /><Where /></>} /></Routes>
    </MemoryRouter></ThemeProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

test("five tiles with time boxes, and the drafts list", async () => {
  mock(); view();
  expect(await screen.findAllByRole("radio")).toHaveLength(5);
  expect(screen.getByText("10 working days")).toBeInTheDocument();
  expect(screen.getByText("Weekly check-in line")).toBeInTheDocument();
  expect(await screen.findByText("Late capital call report")).toBeInTheDocument();
  expect(screen.getByText("Carry on")).toBeInTheDocument();
});

test("no drafts reads as the spec says", async () => {
  mock([]); view();
  expect(await screen.findByText("No drafts. Anything you start and leave is kept here.")).toBeInTheDocument();
});

test("a tile writes the draft then hands over", async () => {
  const posts = mock(); view();
  fireEvent.click((await screen.findAllByRole("radio"))[3]!);
  await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("/centre/intent/new?type=problem&draft=n1"));
  expect(posts[0]!.body).toMatchObject({ type: "problem" });
});

test("North proposes a type and the person confirms it", async () => {
  const posts = mock(); view();
  await screen.findAllByRole("radio");
  fireEvent.change(screen.getByLabelText("Tell North what you want to do"), { target: { value: "think of ideas for investor day" } });
  fireEvent.click(screen.getByText("Ask North"));
  expect(await screen.findByText(/This looks like a Brainstorm/)).toBeInTheDocument();
  fireEvent.click(screen.getByText("Yes, a Brainstorm"));
  await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("type=brainstorm&draft=n1"));
  expect(posts.find((p) => p.url === "/api/intents")!.body).toMatchObject({ type: "brainstorm", north_proposal: { accepted: true, picked_type: "brainstorm" } });
});

test("a tile with no time box cannot be chosen", async () => {
  const { time_box_days: _, ...bare } = ty("Decision", 2);
  mock(DRAFTS, { version: 1, types: { ...CAT.types, decision: bare } }); view();
  const tiles = await screen.findAllByRole("radio");
  expect(tiles[4]).toBeDisabled();
  expect(screen.getByText("Time box not set")).toBeInTheDocument();
});

test("a double click on a tile writes one draft", async () => {
  const posts = mock(); view();
  const tile = (await screen.findAllByRole("radio"))[0]!;
  fireEvent.click(tile); fireEvent.click(tile);
  await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("draft=n1"));
  expect(posts.filter((p) => p.url === "/api/intents")).toHaveLength(1);
});

test("discard cancels with the version and the reason", async () => {
  const posts = mock(); view();
  fireEvent.click(await screen.findByText("Discard"));
  fireEvent.click(screen.getByText("Yes, discard"));
  await waitFor(() => expect(screen.queryByText("Late capital call report")).not.toBeInTheDocument());
  expect(posts[0]).toMatchObject({ url: "/api/intents/d1/cancel", body: { version: 4, cancel_reason: "Discarded by the organiser" } });
});

test("North off says Not available yet and leaves the tiles usable", async () => {
  mock(DRAFTS, CAT, 503); view();
  await screen.findAllByRole("radio");
  fireEvent.change(screen.getByLabelText("Tell North what you want to do"), { target: { value: "anything" } });
  fireEvent.click(screen.getByText("Ask North"));
  expect(await screen.findByText(/^Not available yet/)).toBeInTheDocument();
  expect(screen.getAllByRole("radio")[0]).toBeEnabled();
});

test("?type=problem from an item writes the draft at once and carries from and item", async () => {
  const posts = mock();
  render(
    <ThemeProvider><MemoryRouter initialEntries={["/centre/intent/new?type=problem&from=pul-1&item=it-2"]}>
      <Routes><Route path="/centre/intent/new" element={<><IntentNew /><Where /></>} /></Routes>
    </MemoryRouter></ThemeProvider>,
  );
  await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("/centre/intent/new?type=problem&draft=n1&from=pul-1&item=it-2"));
  expect(posts.filter((p) => p.url === "/api/intents")).toHaveLength(1);
});

test("from an opportunity: no chooser, the draft carries its hypothesis (57)", async () => {
  const posts = mock(); view("/centre/intent/new?type=brainstorm&from=opp-0007");
  await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("type=brainstorm&draft=n1&from=opp-0007"));
  expect(posts[0]!.body).toEqual({ type: "brainstorm" }); // an opportunity is not an intent: no links.from
  expect(posts.find((p) => p.url === "/api/intents/n1/start")!.body).toMatchObject({ carry: "opp-0007" });
  expect(screen.queryAllByRole("radio")).toHaveLength(0);
});
