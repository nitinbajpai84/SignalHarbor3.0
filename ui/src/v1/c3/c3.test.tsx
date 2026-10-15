import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { routes } from "./routes";

// C3 against c3_routes (docs/plan/v1-landings/C3.md); fetch is stubbed with synthetic data.
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const BRIEF = {
  views: [{ name: "Committee overview", audience: "the investment committee", kpis: ["K02", "K01"], comparisons: ["policy benchmark"], filters: ["entity"], refresh: "monthly" }],
  feeds_wanted: ["fx_rates"], levers: [{ name: "Cash withdrawal", affects: ["K02"], range: "small to large" }],
  existing_dashboards: [], end_user_inputs: [], notes: [],
};
const CHAT = {
  intent_id: "int_1", title: "Monthly performance pack", line: null, state: "open", needs_done: [], brief: BRIEF, skill: "Shaping what people see",
  kpis: [{ code: "K01", name: "Time-weighted return" }, { code: "K02", name: "Cash drag" }], feeds: [{ id: "fx_rates", kind: "FX rates" }],
  ask_next: "Which figures do you look at first, and what do you decide from them?", greeting: "Hello Leela. I am Lumen.", me: "Dev Sharma",
  turns: [],
};

function mock(post = 200) {
  const calls: { method: string; url: string }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ method, url });
    if (method === "GET") return json(200, CHAT);
    if (post !== 200) return json(post, { error: "not_allowed", message: "Only the analyst or the decision maker can shape the page." });
    return json(200, { ...CHAT, turns: [{ id: "t1", by: "person", name: "Leela Raman", text: "Cash drag first", at: "2026-10-08T09:00:00Z" },
      { id: "t2", by: "lumen", name: "Lumen", text: "What do you compare it with?", at: "2026-10-08T09:00:02Z" }] });
  }));
  return calls;
}
const view = (at: string) => render(
  <ThemeProvider><MemoryRouter initialEntries={[at]}><Routes>
    {routes.map((r) => <Route key={r.path} path={`/centre/${r.path}`} element={r.element} />)}
  </Routes></MemoryRouter></ThemeProvider>,
);

afterEach(() => vi.unstubAllGlobals());

test("greets, shows the brief by name and the sketch, and talks to Lumen", async () => {
  const calls = mock();
  view("/centre/consume/design");
  expect(await screen.findByText("Hello Leela. I am Lumen.")).toBeInTheDocument();
  expect(screen.getByText("Cash drag, Time-weighted return")).toBeInTheDocument();
  expect(screen.getByText("FX rates")).toBeInTheDocument();
  expect(screen.getByLabelText("Sketch of the Consume page")).toHaveTextContent("Cash drag");
  fireEvent.change(screen.getByLabelText("Your message"), { target: { value: "Cash drag first" } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  expect(await screen.findByText("What do you compare it with?")).toBeInTheDocument();
  expect(calls.some((c) => c.method === "POST" && c.url === "/api/v1/consume/brief/int_1/chat")).toBe(true);
});

test("a refused message says so in plain words", async () => {
  mock(403);
  view("/centre/consume/design");
  fireEvent.change(await screen.findByLabelText("Your message"), { target: { value: "hello" } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Only the analyst or the decision maker"));
});

test("an end user answers the short questions", async () => {
  const calls = mock();
  view("/centre/consume/design/int_1/ask");
  expect(await screen.findByText(CHAT.ask_next)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Your answer"), { target: { value: "Return first" } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.url === "/api/v1/consume/brief/int_1/input")).toBe(true));
});
