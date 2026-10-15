import { render, screen, waitFor, configure } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import App from "../../../App";
import { setSessionExpiredHandler } from "../../../api/client";
import type { Lists, Preparation, SessionView } from "../api";
import { m1Room } from "../copy";

// These tests render the whole App; on a loaded machine the 1s default for findBy*/waitFor is too short.
configure({ asyncUtilTimeout: 5000 });

// Nitin's hands-on finding (M1-P02 fix round 1): after "Save draft" the wizard must lead on to the page where
// "Start the room" is, and that page says "Save your draft first" only while the draft is not saved. fetch is stubbed.

const BASE = "/api/modules/m1_intent";
const SID = "a".repeat(32);
const SESSION_PAGE = `/modules/m1_intent/sessions/${SID}`;
const LISTS: Lists = {
  seats: { min: 1, max: 10 }, time_presets_minutes: [5, 10, 20, 30], custom_length_minutes: { min: 5, max: 120 },
  min_stage_minutes: 1, default_length_minutes: 20, default_split: { briefing: 4, individual: 8, together: 8 },
  default_split_percent: { briefing: 20, individual: 40, together: 40 }, briefing_video_options: ["standard", "none"],
  charter_templates: [{ id: "standard", name: "Standard charter", description: "d" }], default_template: "standard",
  north: { problem_library_available: false, industry_practice_available: false, problem_count: 0, message: null },
};
const PREP: Preparation = {
  purpose: "Agree what we want to know", outcome: "A signed charter", charter_template: "standard", seats: 3,
  length_minutes: 20, split: { briefing: 4, individual: 8, together: 8 }, north_industry_practice: false,
  north_problem_library: false, briefing_video: "standard", approver_name: "", approver_account_id: null,
};
const view = (): SessionView => ({
  id: SID, state: "draft", paused_from: null, is_solo: false, editable: true, preparation: PREP,
  outcome_id: "b".repeat(32), created_at: "2026-10-03T10:00:00+00:00", updated_at: "2026-10-03T10:00:00+00:00",
});
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function mock() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      if (url === "/api/auth/me") return json(200, { display_name: "Ann", company_id: "co-a", roles: ["company_admin"] });
      if (url === "/api/company") return json(200, { company_id: "co-a", name: "Harbor Test Co", industry: "none" });
      if (url === "/api/modules")
        return json(200, [{ id: "m1_intent", number: 1, name: "Intent", description: "d", agent: "North" }]);
      if (url === `${BASE}/lists`) return json(200, LISTS);
      if (url === `${BASE}/templates`) return json(200, []);
      if (url === `${BASE}/sessions` && method === "GET") return json(200, []);
      if (url === `${BASE}/sessions` && method === "POST") return json(201, view());
      if (url === `${BASE}/sessions/${SID}` && method === "PUT") return json(200, view());
      if (url === `${BASE}/sessions/${SID}`) return json(200, view());
      return json(404, {});
    }),
  );
}

const open = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  sessionStorage.clear();
  setSessionExpiredHandler(null);
});

describe("after Save draft the wizard leads on to Start the room", () => {
  test("a new draft: no way on before saving, then 'Continue to start the room' opens the session page with Start the room", async () => {
    mock();
    const user = userEvent.setup();
    open("/modules/m1_intent/prepare");
    await user.type(await screen.findByLabelText(/What is this session for/), "Why do renewals slip?");
    for (let i = 0; i < 6; i++) await user.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.queryByRole("link", { name: m1Room.continueToStart })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save draft" }));
    const go = await screen.findByRole("link", { name: m1Room.continueToStart });
    expect(go).toHaveAttribute("href", SESSION_PAGE);
    await user.click(go);
    expect(await screen.findByRole("button", { name: m1Room.start.button })).toBeInTheDocument();
    expect(screen.queryByText(m1Room.start.saveFirst)).not.toBeInTheDocument();
  }, 20000); // ~30 clicks through the wizard: over the 5s default on a loaded machine

  test("a change after saving takes the way on away again until it is saved", async () => {
    mock();
    const user = userEvent.setup();
    open("/modules/m1_intent/prepare");
    const purpose = await screen.findByLabelText(/What is this session for/);
    await user.type(purpose, "Why do renewals slip?");
    for (let i = 0; i < 6; i++) await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(screen.getByRole("button", { name: "Save draft" }));
    await screen.findByRole("link", { name: m1Room.continueToStart });
    for (let i = 0; i < 6; i++) await user.click(screen.getByRole("button", { name: "Back" }));
    await user.type(screen.getByLabelText(/What is this session for/), " again");
    for (let i = 0; i < 6; i++) await user.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.queryByRole("link", { name: m1Room.continueToStart })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save draft" }));
    expect(await screen.findByRole("link", { name: m1Room.continueToStart })).toBeInTheDocument();
  }, 20000); // ~40 clicks through the wizard: over the 5s default on a loaded machine
});

describe("the session page of a saved draft", () => {
  test("reopening a saved draft shows Start the room and no 'Save your draft first'", async () => {
    mock();
    open(SESSION_PAGE);
    expect(await screen.findByRole("button", { name: m1Room.start.button })).toBeInTheDocument();
    expect(screen.queryByText(m1Room.start.saveFirst)).not.toBeInTheDocument();
  });

  test("'Save your draft first' shows while the wizard holds changes that are not saved, and goes once they are", async () => {
    mock();
    const user = userEvent.setup();
    open(SESSION_PAGE);
    await screen.findByRole("button", { name: m1Room.start.button });
    await user.type(await screen.findByLabelText(/What is this session for/), " and more");
    expect(await screen.findByText(m1Room.start.saveFirst)).toBeInTheDocument();
    for (let i = 0; i < 6; i++) await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(screen.getByRole("button", { name: "Save draft" }));
    await waitFor(() => expect(screen.queryByText(m1Room.start.saveFirst)).not.toBeInTheDocument());
  });
});
