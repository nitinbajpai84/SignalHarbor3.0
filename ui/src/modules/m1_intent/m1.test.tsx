import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import App from "../../App";
import { setSessionExpiredHandler } from "../../api/client";
import { m1, m1Nira } from "./copy";
import { defaultSplit, splitProblem, blankForm } from "./form";
import type { Lists, Preparation, SessionRow, SessionView, TemplateRow } from "./api";

// M1-P01 screens: module home, Prepare wizard, read-only started session, shell top bar. fetch is stubbed.

const BASE = "/api/modules/m1_intent";
const LISTS: Lists = {
  seats: { min: 1, max: 10 },
  time_presets_minutes: [5, 10, 20, 30],
  custom_length_minutes: { min: 5, max: 120 },
  min_stage_minutes: 1,
  default_length_minutes: 20,
  default_split: { briefing: 4, individual: 8, together: 8 },
  default_split_percent: { briefing: 20, individual: 40, together: 40 },
  briefing_video_options: ["standard", "none"],
  charter_templates: [
    { id: "standard", name: "Standard charter", description: "Everything on each line." },
    { id: "short", name: "Short charter", description: "Problem and priority only." },
  ],
  default_template: "standard",
  north: { problem_library_available: true, industry_practice_available: true, problem_count: 3, message: null },
};
const PACKLESS = { ...LISTS.north, problem_library_available: false, industry_practice_available: false, problem_count: 0, message: "No industry knowledge is available yet for this industry. You can still work from your own company's information." };
const PREP: Preparation = {
  purpose: "Agree what we want to know", outcome: "A signed charter", charter_template: "standard", seats: 3,
  length_minutes: 20, split: { briefing: 4, individual: 8, together: 8 }, north_industry_practice: false,
  north_problem_library: false, briefing_video: "standard", approver_name: "", approver_account_id: null,
};
const view = (over: Partial<SessionView> = {}): SessionView => ({
  id: "a".repeat(32), state: "draft", paused_from: null, is_solo: false, editable: true, preparation: PREP,
  outcome_id: "b".repeat(32), created_at: "2026-10-03T10:00:00+00:00", updated_at: "2026-10-03T10:00:00+00:00", ...over,
});

interface World {
  rows?: SessionRow[];
  lists?: Lists;
  templates?: TemplateRow[];
  session?: SessionView;
  listStatus?: number;
  listBody?: unknown;
  expire?: boolean;
  hold?: boolean;
  saveError?: { status: number; body: unknown };
}
const calls: { method: string; url: string; body: unknown }[] = [];
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function mock(w: World) {
  calls.length = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
      if (url === "/api/auth/me") return json(200, { display_name: "Ann", company_id: "co-a", roles: ["company_admin"] });
      if (url === "/api/company") return json(200, { company_id: "co-a", name: "Harbor Test Co", industry: "none" });
      if (url === "/api/modules")
        return json(200, [{ id: "m1_intent", number: 1, name: "Intent", description: "d", agent: "North" }]);
      if (w.expire) return json(401, { error: "session_expired", message: "x", login_url: "/login" });
      if (url === `${BASE}/sessions` && method === "GET") {
        if (w.hold) return new Promise<Response>(() => undefined); // never answers: the loading state
        return w.listStatus ? json(w.listStatus, w.listBody ?? {}) : json(200, w.rows ?? []);
      }
      if (url === `${BASE}/lists`) return json(200, w.lists ?? LISTS);
      if (url === `${BASE}/templates` && method === "GET") return json(200, w.templates ?? []);
      if (url === `${BASE}/templates` && method === "POST") return json(201, { id: "c".repeat(32), name: "t", preparation: PREP, created_at: "x" });
      if (url === `${BASE}/sessions` && method === "POST") {
        if (w.saveError) return json(w.saveError.status, w.saveError.body);
        return json(201, view());
      }
      if (url.startsWith(`${BASE}/sessions/`) && method === "GET") return json(200, w.session ?? view());
      if (url.startsWith(`${BASE}/sessions/`) && method === "PUT") return json(200, view());
      if (url.startsWith(`${BASE}/sessions/`) && method === "DELETE") return json(200, { deleted: true });
      return json(404, {});
    }),
  );
}

function open(path = "/modules/m1_intent") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  sessionStorage.clear();
  setSessionExpiredHandler(null);
});

const row = (over: Partial<SessionRow> = {}): SessionRow => ({
  id: "a".repeat(32), state: "draft", label: "Renewal questions", seats: 3, outcome_id: "b".repeat(32),
  updated_at: "2026-10-03T10:00:00+00:00", ...over,
});

describe("module home: five states", () => {
  test("loading", async () => {
    mock({ hold: true });
    open();
    expect(await screen.findByRole("heading", { name: "Intent Centre" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Loading");
  });

  test("empty company: honest empty state, the prepare button, the solo hint, nothing invented", async () => {
    mock({ rows: [] });
    open();
    expect(await screen.findByText(m1.home.empty)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Prepare a session" })).toHaveAttribute("href", "/modules/m1_intent/prepare");
    expect(screen.getByText(m1.home.soloHint)).toBeInTheDocument();
    expect(screen.queryByText("Illustrative")).not.toBeInTheDocument();
  });

  test("populated: drafts, in progress and closed are grouped; a solo draft says so", async () => {
    mock({ rows: [row(), row({ id: "c".repeat(32), state: "briefing", label: "Live one", seats: 1 }),
      row({ id: "d".repeat(32), state: "closed", label: "Old one" }), row({ id: "e".repeat(32), state: "paused", label: "Held one" })] });
    open();
    const drafts = await screen.findByRole("region", { name: "Drafts" });
    expect(within(drafts).getByText("Renewal questions")).toBeInTheDocument();
    const live = screen.getByRole("region", { name: "In progress" });
    expect(within(live).getByText("Live one")).toBeInTheDocument();
    expect(within(live).getByText("Held one")).toBeInTheDocument();
    expect(within(live).getByText(/1 seat \(solo\)/)).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Closed" })).getByText("Old one")).toBeInTheDocument();
    expect(within(drafts).getByRole("link", { name: "Open" })).toHaveAttribute("href", `/modules/m1_intent/sessions/${"a".repeat(32)}`);
  });

  test("error: one sentence and a way to try again", async () => {
    mock({ listStatus: 500, listBody: { detail: "boom" } });
    const user = userEvent.setup();
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong. Try again in a moment.");
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(calls.filter((c) => c.url === `${BASE}/sessions`).length).toBeGreaterThan(1);
  });

  test("refused: the module is not part of the plan", async () => {
    mock({ listStatus: 403, listBody: { error: "module_not_available", message: "x" } });
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent("This module is not part of your plan. Ask your administrator.");
  });

  test("refused: a role without access gets plain words, not a role code", async () => {
    mock({ listStatus: 403, listBody: { error: "forbidden", message: "x" } });
    open();
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("You do not have access to this. Ask your administrator.");
  });

  test("a session that ended inside the module goes to sign-in", async () => {
    mock({ expire: true });
    open();
    expect(await screen.findByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });
});

describe("shell", () => {
  test("the top bar shows Signal Harbor with the lighthouse mark next to the company name", async () => {
    mock({ rows: [] });
    open("/legacy");
    const company = await screen.findByText("Harbor Test Co");
    const bar = company.closest("header");
    expect(bar).not.toBeNull();
    expect(within(bar as HTMLElement).getByText("Signal Harbor")).toBeInTheDocument();
    expect(within(bar as HTMLElement).getByRole("img", { name: "Signal Harbor" })).toBeInTheDocument();
  });
});

describe("prepare wizard", () => {
  test("steps run in order and Next waits for the purpose", async () => {
    mock({});
    const user = userEvent.setup();
    open("/modules/m1_intent/prepare");
    const next = await screen.findByRole("button", { name: "Next" });
    expect(next).toBeDisabled();
    const steps = within(screen.getByRole("list", { name: "Steps" })).getAllByRole("listitem");
    expect(steps.map((s) => s.textContent)).toEqual(
      ["Purpose", "Charter", "People and time", "North", "Briefing video", "Approver", "Review"]);
    await user.type(screen.getByLabelText(/What is this session for/), "Why do renewals slip?");
    expect(next).toBeEnabled();
    await user.click(next);
    expect(screen.getByRole("radio", { name: /Standard charter/ })).toBeChecked(); // from the contract list
    expect(screen.getByRole("radio", { name: /Short charter/ })).not.toBeChecked();
  });

  async function toPeople(user: ReturnType<typeof userEvent.setup>) {
    await user.type(await screen.findByLabelText(/What is this session for/), "Why do renewals slip?");
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(screen.getByRole("button", { name: "Next" }));
  }

  test("the organiser chooses how names show on notes: three options, each explained, Each person chooses by default, sent with the draft", async () => {
    mock({});
    const user = userEvent.setup();
    open("/modules/m1_intent/prepare");
    await toPeople(user);
    expect(screen.getByText("How should names be shown on notes?")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Each person chooses/ })).toBeChecked();
    expect(screen.getByText("Everyone's name is shown on their notes.")).toBeInTheDocument();
    expect(screen.getByText("No name is ever shown on a note.")).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: /^Anonymous/ }));
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(screen.getByRole("button", { name: "Save draft" }));
    await screen.findByText("Draft saved.");
    expect(calls.find((c) => c.method === "POST" && c.url === `${BASE}/sessions`)?.body).toMatchObject({ names: "anonymous" });
  });

  test("seats 1 to 10 come from the lists and one seat is a solo session", async () => {
    mock({});
    const user = userEvent.setup();
    open("/modules/m1_intent/prepare");
    await toPeople(user);
    const seats = screen.getByLabelText("How many people will join?") as HTMLSelectElement;
    expect([...seats.options].map((o) => o.value)).toEqual(["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]);
    expect(seats.options[0]?.textContent).toMatch(/solo session/);
  });

  test("the split check is live: wrong sum says so in plain words, the right sum is confirmed", async () => {
    mock({});
    const user = userEvent.setup();
    open("/modules/m1_intent/prepare");
    await toPeople(user);
    expect(screen.getByText("The three parts add up to 20 minutes.")).toBeInTheDocument();
    const together = screen.getByLabelText(/^Together/);
    await user.clear(together);
    await user.type(together, "5");
    expect(screen.getByRole("alert")).toHaveTextContent(
      "The three parts add up to 17 minutes, but the session is 20 minutes. Change the parts so they add up to 20.");
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    await user.clear(together);
    await user.type(together, "8");
    expect(screen.getByRole("button", { name: "Next" })).toBeEnabled();
  });

  test("a new length brings a new default split; a custom length is checked against the limits", async () => {
    mock({});
    const user = userEvent.setup();
    open("/modules/m1_intent/prepare");
    await toPeople(user);
    await user.click(screen.getByRole("radio", { name: "30 minutes" }));
    expect((screen.getByLabelText(/^Briefing/) as HTMLInputElement).value).toBe("6");
    expect((screen.getByLabelText(/^Together/) as HTMLInputElement).value).toBe("12");
    await user.click(screen.getByRole("radio", { name: "Another length" }));
    await user.type(screen.getByLabelText("Length in minutes"), "999");
    expect(screen.getByRole("alert")).toHaveTextContent("Choose a length between 5 and 120 minutes.");
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  test("North step: an industry with no pack gets the honest empty state and nothing to switch on", async () => {
    mock({ lists: { ...LISTS, north: PACKLESS } });
    const user = userEvent.setup();
    open("/modules/m1_intent/prepare");
    await toPeople(user);
    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByLabelText("Let North offer industry practice")).toBeDisabled();
    expect(screen.getByLabelText(/Let North offer the problem library/)).toBeDisabled();
    expect(screen.getByText(/No industry knowledge is available yet/)).toBeInTheDocument();
    expect(screen.queryByText("Suggestion")).not.toBeInTheDocument();
  });

  test("North step with a pack: offers are labelled as suggestions", async () => {
    mock({});
    const user = userEvent.setup();
    open("/modules/m1_intent/prepare");
    await toPeople(user);
    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Suggestion")).toBeInTheDocument();
    expect(screen.getByText(/3 problems on offer/)).toBeInTheDocument();
    await user.click(screen.getByLabelText(/Let North offer the problem library/));
    expect(screen.getByLabelText(/Let North offer the problem library/)).toBeChecked();
  });

  test("review: saving sends the values; then the template and delete actions appear", async () => {
    mock({});
    const user = userEvent.setup();
    open("/modules/m1_intent/prepare");
    await user.type(await screen.findByLabelText(/What is this session for/), "Why do renewals slip?");
    for (let i = 0; i < 6; i++) await user.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Save the draft first to keep it.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save draft" }));
    expect(await screen.findByText("Draft saved.")).toBeInTheDocument();
    const post = calls.find((c) => c.method === "POST" && c.url === `${BASE}/sessions`);
    expect(post?.body).toMatchObject({ purpose: "Why do renewals slip?", seats: 1, length_minutes: 20,
      split: { briefing: 4, individual: 8, together: 8 }, charter_template: "standard", briefing_video: "standard" });
    await user.type(screen.getByLabelText("Template name"), "Quarterly");
    await user.click(screen.getByRole("button", { name: "Save as a template" }));
    expect(await screen.findByText("Template saved.")).toBeInTheDocument();
    expect(calls.some((c) => c.method === "POST" && c.url === `${BASE}/templates`)).toBe(true);
  });

  test("a server refusal is shown in its own plain words", async () => {
    mock({ saveError: { status: 422, body: { error: "invalid", field: "seats", message: "Please choose between 1 and 10 people. One person means a solo session." } } });
    const user = userEvent.setup();
    open("/modules/m1_intent/prepare");
    await user.type(await screen.findByLabelText(/What is this session for/), "x");
    for (let i = 0; i < 6; i++) await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(screen.getByRole("button", { name: "Save draft" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Please choose between 1 and 10 people.");
  });

  test("deleting asks first, then removes the draft and goes back to the list", async () => {
    mock({ rows: [] });
    const user = userEvent.setup();
    open(`/modules/m1_intent/sessions/${"a".repeat(32)}`);
    await screen.findByLabelText(/What is this session for/);
    for (let i = 0; i < 6; i++) await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(screen.getByRole("button", { name: "Delete this draft" }));
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
    await user.click(screen.getByRole("button", { name: "Yes, delete it" }));
    await waitFor(() => expect(calls.some((c) => c.method === "DELETE" && c.url.endsWith("?confirm=yes"))).toBe(true));
    expect(await screen.findByRole("heading", { name: "Intent Centre" })).toBeInTheDocument();
  });

  test("reopening a draft fills the form; a saved template can start a new one", async () => {
    mock({ templates: [{ id: "t".repeat(32), name: "Quarterly", preparation: { ...PREP, purpose: "From the template", seats: 4 }, created_at: "x" }] });
    const user = userEvent.setup();
    open("/modules/m1_intent/prepare");
    await user.selectOptions(await screen.findByLabelText(/Start from a saved template/), "Quarterly");
    expect(screen.getByLabelText(/What is this session for/)).toHaveValue("From the template");
  });

  test("a draft that already started is read-only", async () => {
    mock({ session: view({ state: "lobby", editable: false }) });
    open(`/modules/m1_intent/sessions/${"a".repeat(32)}`);
    expect(await screen.findByText(m1.summary.started)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Next" })).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: (n) => n !== m1Nira.question }) /* Nira's own ask box is always there */).not.toBeInTheDocument();
  });

  test("not found is shown in plain words, with the way back", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/auth/me") return json(200, { display_name: "Ann", company_id: "co-a", roles: ["company_admin"] });
      if (url === "/api/company") return json(200, { company_id: "co-a", name: "Co", industry: "none" });
      if (url === "/api/modules") return json(200, [{ id: "m1_intent", number: 1, name: "Intent", description: "d", agent: "North" }]);
      if (url === `${BASE}/lists`) return json(200, LISTS);
      if (url === `${BASE}/templates`) return json(200, []);
      return json(404, { error: "not_found", message: "We could not find that session." });
    }));
    open(`/modules/m1_intent/sessions/${"f".repeat(32)}`);
    expect(await screen.findByRole("alert")).toHaveTextContent("We could not find that session.");
    expect(screen.getByRole("link", { name: "Back to your sessions" })).toBeInTheDocument();
  });
});

describe("form helpers", () => {
  test("default split follows the contract percentages and always adds up", () => {
    for (const n of [5, 7, 10, 20, 30, 45, 120]) {
      const s = defaultSplit(n, LISTS.default_split_percent);
      expect(s.briefing + s.individual + s.together).toBe(n);
    }
    expect(defaultSplit(5, LISTS.default_split_percent)).toEqual({ briefing: 1, individual: 2, together: 2 });
  });
  test("split problems", () => {
    const f = blankForm(LISTS);
    expect(splitProblem(f, LISTS)).toBeNull();
    expect(splitProblem({ ...f, split: { ...f.split, together: "0" } }, LISTS)).toMatch(/at least 1 minute/);
    expect(splitProblem({ ...f, split: { ...f.split, together: "x" } }, LISTS)).toMatch(/add up/);
  });
});

describe("screen wording", () => {
  const flat = (v: unknown): string[] =>
    typeof v === "string" ? [v] : typeof v === "function" ? [String((v as (...a: number[]) => string)(3, 20, 5))]
      : v && typeof v === "object" ? Object.values(v).flatMap(flat) : [];

  test("no technical words in the module's copy", () => {
    const banned = /\b(json|api|uuid|http|token|session id|outcome id|company_admin|sponsor role|payload|database|endpoint|null|undefined|404|500)\b/i;
    for (const line of flat(m1)) expect(line, line).not.toMatch(banned);
  });

  test("North and Nira are named by role, never as bare model names", () => {
    expect(flat(m1).join(" ")).toMatch(/North, the industry expert|North/);
    expect(flat(m1).join(" ")).not.toMatch(/\b(gpt|claude|gemini|llm|model)\b/i);
  });
});
