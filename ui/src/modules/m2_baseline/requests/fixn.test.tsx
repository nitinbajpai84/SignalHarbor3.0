// slow under a full parallel run; the 5 s default timed out a different test each time
vi.setConfig({ testTimeout: 30000 });
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import OwnerAnswerPage from "../../../pages/OwnerAnswerPage";
import { ThemeProvider } from "../../../theme";
import type { OwnerForm, QuestionnaireSpec } from "../api";
import { m2Form as F } from "../copy";

// M2-FIX-N D3: the owner form sends each step only what its kind has in the contract (questionnaire.yaml), so "manual" is on the
// in-between step alone. The earlier tests used a spec with one hop field, so an upstream step was never filled the way an owner does.

const TOKEN = `ow-${"a".repeat(32)}-${"s".repeat(43)}`;
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const calls: { url: string; body: unknown }[] = [];
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

const hop = (...parts: [string, string][]) => parts.map(([key, label]) => ({ key, label }));
const spec: QuestionnaireSpec = {
  marks: [{ value: "stated", label: "I am sure" }, { value: "guessed", label: "My best guess" }, { value: "unknown", label: "I don't know" }],
  limits: { text_chars: 500, hops: 10 },
  fields: [
    { key: "upstream", kind: "hops", question: "Upstream", hop: hop(["who", "Who"], ["team", "Their team or system"], ["what", "What they give you"], ["order", "Step number"]) },
    { key: "in_between", kind: "hops", question: "In between", hop: hop(["who", "Who"], ["team", "Their team or system"], ["step", "Where and what they change"], ["order", "Step number"], ["manual", "Done by hand"]) },
    { key: "downstream", kind: "hops", question: "Downstream", hop: hop(["who", "Who"], ["team", "Their team or system"], ["what", "What they use it for"], ["order", "Step number"]) },
  ],
};
const form: OwnerForm = {
  owner_name: "Tom Reyes", role: "business owner", state: "opened", expires_at: "2026-10-17T10:00:00+00:00",
  kpis: [{ id: "k1", name: "Funding capacity", answers: null }], questionnaire: spec, confirmable: [],
};

test("filling every step kind as an owner does sends no manual flag upstream or downstream", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    return String(url).endsWith("/answer/save") ? json(200, { saved: { id: "x", kpi_id: "k1", owner_name: "Tom Reyes", sample_title: null } }) : json(200, form);
  }));
  render(
    <MemoryRouter initialEntries={[`/answer/${TOKEN}`]}>
      <ThemeProvider>
        <Routes>
          <Route path="/answer/:token" element={<OwnerAnswerPage />} />
        </Routes>
      </ThemeProvider>
    </MemoryRouter>,
  );
  const panel = (await screen.findByText(F.measure(1, 1, "Funding capacity"))).closest("section") as HTMLElement;
  const user = userEvent.setup();
  const q = (text: string) => within(within(panel).getByText(text).closest("fieldset") as HTMLElement);
  for (const [name, who, what] of [["Upstream", "Bank", "Statement"], ["In between", "Sara", "Workbook"], ["Downstream", "Board", "Pack"]] as const) {
    const box = q(name);
    await user.type(box.getByLabelText("Who"), who);
    await user.type(box.getByLabelText(/^(What they give you|Where and what they change|What they use it for)$/), what);
    await user.click(box.getByLabelText("I am sure"));
  }
  await user.click(within(panel).getByRole("button", { name: F.saveMeasure }));
  expect(await within(panel).findByText(F.saved)).toBeInTheDocument();
  const sent = calls.find((c) => c.url.endsWith("/answer/save"))?.body as { answers: Record<string, { value: Record<string, unknown>[] }> };
  expect(sent.answers.upstream!.value).toEqual([{ who: "Bank", what: "Statement" }]);
  expect(sent.answers.in_between!.value).toEqual([{ who: "Sara", step: "Workbook", manual: false }]);
  expect(sent.answers.downstream!.value).toEqual([{ who: "Board", what: "Pack" }]);
});
