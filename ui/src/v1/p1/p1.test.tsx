import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { routes } from "./routes";

// P1 against p1_routes; fetch is stubbed with synthetic data.
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const PROJECT = {
  id: "prj-1a2b3c4d", intent_id: "ini-1", title: "Monthly performance pack", started_by: "Arjun Mehta", started_at: "2026-10-08T09:00:00Z", stage: "talking",
  artefacts: ["intent", "design", "build_pack", "brief"].map((kind) => ({ kind, record_path: "", version: 1, state: "draft", signed_by: null, signed_at: null })),
  people: { raiser: "Arjun Mehta", sponsor: "Priya Nair", builder: null, head_of_data: null, ops: null },
};
const COMMENT = { id: "c_1", artefact: "intent", line_ref: "3.1", by: "span", name: "Span", to: "Arjun Mehta", text: "Is the return before or after fees?",
  kind: "comment", state: "open", at: "2026-10-08T09:01:00Z", answer: null, answered_at: null };
const DOC = {
  project: "prj-1a2b3c4d", kind: "intent", name: "Intent of work", title: "Monthly performance pack", state: "draft", version: 1, signed_by: null,
  signed_at: null, signers: ["Arjun Mehta"], me: "Arjun Mehta", comments: [COMMENT],
  sections: [{ n: 3, heading: "3. KPIs", lines: [{ ref: "3.1", text: "**Time-weighted return** (defined): growth net of fees." }] }],
};

function mock(answer = 200) {
  const calls: { method: string; url: string }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ method, url });
    if (method === "POST") return answer === 200 ? json(200, { ...COMMENT, state: "answered" }) : json(answer, { error: "not_allowed", message: "Only Arjun Mehta can answer this comment." });
    return json(200, url.includes("/artefacts/") ? DOC : PROJECT);
  }));
  return calls;
}
const view = (at = "/centre/project/prj-1a2b3c4d") => render(
  <ThemeProvider><MemoryRouter initialEntries={[at]}><Routes>
    {routes.map((r) => <Route key={r.path} path={`/centre/${r.path}`} element={r.element} />)}
  </Routes></MemoryRouter></ThemeProvider>,
);

afterEach(() => vi.unstubAllGlobals());

test("shows the intent of work as numbered lines and answers a comment addressed to me", async () => {
  const calls = mock();
  view();
  expect(await screen.findByText("Time-weighted return (defined): growth net of fees.")).toBeInTheDocument();
  expect(screen.getByText("3.1")).toBeInTheDocument();
  expect(screen.getByText(/Is the return before or after fees?/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Answer Span"), { target: { value: "After fees" } });
  fireEvent.click(screen.getByRole("button", { name: "Answer" }));
  await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.url.endsWith("/comments/c_1/answer"))).toBe(true));
});

test("says plainly when the answer is refused", async () => {
  mock(403);
  view();
  fireEvent.change(await screen.findByLabelText("Answer Span"), { target: { value: "After fees" } });
  fireEvent.click(screen.getByRole("button", { name: "Answer" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Only Arjun Mehta can answer this comment.");
});

test("a link from Pulse opens the artefact and highlights the comment", async () => {
  const calls = mock();
  view("/centre/project/prj-1a2b3c4d?artefact=design&line=3.1&comment=c_1");
  await screen.findByText(/Is the return before or after fees/);
  expect(calls.some((c) => c.url.endsWith("/artefacts/design"))).toBe(true);
  expect(document.querySelector('[aria-current="true"]')).toHaveTextContent("Is the return before or after fees?");
});
