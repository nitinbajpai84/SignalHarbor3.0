import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import SkillsPage from "../knowledge/SkillsPage";
import ActionPage from "./ActionPage";
import SkillReviewPage from "./SkillReviewPage";

vi.mock("../../useSession", () => ({ useSession: () => ({ user: { display_name: "Anita Rao" } }) }));
afterEach(() => vi.unstubAllGlobals());
const json = (b: unknown, ok = true) => new Response(JSON.stringify(b), { status: ok ? 200 : 500, headers: { "Content-Type": "application/json" } });

const row = (o: object) => ({ id: "s1", name: "Read call notices", goal: "Read a notice.", when: "A PDF.", centre: "build", source: "office", tier: "fast", version: 1, status: "waiting", tested: { passed: 3, total: 4 }, used: 0, last_changed: { by: "Harbor", at: "2026-10-14T06:00:00" }, ...o });
const detail = { ...row({}), inputs: "The PDF", output: "Five fields", steps: ["Read the title"], tools: [], checks: ["Amount adds up"], never: ["Pay"], history: [{ v: 1, at: "2026-10-14T06:00:00", by: "Harbor", change: "drafted" }],
  why: "You marked it by hand twice.", evidence: [{ at: "2026-09-02T00:00:00", text: "A call notice marked by hand." }],
  tests: [{ input: "Capital call", expected: "600,000", got: "550,000", ok: false }], cache: { answers: 212, golden: 38 } };
const desk = { needs: [{ kind: "decision", thread: "t1", title: "Liquidity", text: "Go live?", actions: [{ label: "Go live", answer: "go_live" }] },
  { kind: "exception", thread: "t1", title: "Recon", text: "T-005 is missing.", actions: [{ label: "It is timing", answer: "timing" }] }],
  note: null, threads: [{ id: "t1", title: "Liquidity", stage: "decision3", needs: 1 }], files: { arrived: 0, recognised: 0, waiting: 0 } };
const thread = { id: "t1", title: "Liquidity", events: [{ at: new Date().toISOString(), kind: "decision_done", text: "Chose current value.", by: "Daniel" }] };

function mock(posts: string[], over: Record<string, unknown> = {}) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") { posts.push(`${url} ${String(init.body)}`); return json(detail); }
    if (url in over) { const v = over[url]; return v === "fail" ? json({}, false) : json(v); }
    if (url === "/api/v3/desk") return json(desk);
    if (url === "/api/v3/threads/t1") return json(thread);
    if (url === "/api/v3/skills") return json({ skills: [row({}), row({ id: "s2", name: "Answer a question", status: "in_use", centre: "consume", source: "core", version: 4 })] });
    if (url === "/api/v3/skills/s1" || url === "/api/v3/skills/s2") return json(detail);
    return json({}, false);
  }));
}
const at = (path: string, ui: React.ReactElement, route = path) =>
  render(<MemoryRouter initialEntries={[path]}><Routes><Route path={route} element={ui} /></Routes></MemoryRouter>);

test("action queue: counts, filter, open a skill, decide a card, done list", async () => {
  const posts: string[] = [];
  mock(posts);
  at("/v3/action", <ActionPage />);
  expect(await screen.findByRole("button", { name: /^All\s*3$/ })).toBeInTheDocument();
  expect(screen.getByText("Daniel", { exact: false })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /^New skills/ }));
  expect(screen.queryByText("Go live?")).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Open Read call notices" }));
  expect(screen.getByRole("link", { name: "Review" })).toHaveAttribute("href", "/v3/skill/s1");
  await userEvent.click(screen.getByRole("button", { name: /^All/ }));
  await userEvent.click(screen.getByRole("button", { name: "Open Liquidity" }));
  await userEvent.click(screen.getByRole("button", { name: "Go live" }));
  await waitFor(() => expect(posts).toEqual(['/api/v3/threads/t1/decide {"n":3,"answer":"go_live"}']));
});

test("action: error offers a retry; empty says so", async () => {
  mock([], { "/api/v3/desk": "fail" });
  const a = at("/v3/action", <ActionPage />);
  expect(await screen.findByRole("button", { name: "Try again" })).toBeInTheDocument();
  a.unmount();
  mock([], { "/api/v3/desk": { ...desk, needs: [], threads: [] }, "/api/v3/skills": { skills: [] } });
  at("/v3/action", <ActionPage />);
  expect(await screen.findByText("Nothing needs a person right now.")).toBeInTheDocument();
});

test("skill review: edit a line, try again, reject needs a reason", async () => {
  const posts: string[] = [];
  mock(posts);
  at("/v3/skill/s1", <SkillReviewPage />, "/v3/skill/:id");
  expect(await screen.findByText("You marked it by hand twice.")).toBeInTheDocument();
  expect(screen.getByText("A call notice marked by hand.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Edit Goal" }));
  const box = screen.getByLabelText("Change Goal");
  await userEvent.clear(box);
  await userEvent.type(box, "Read it well.");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(posts[0]).toBe('/api/v3/skills/s1/edit {"field":"goal","value":"Read it well."}'));
  expect(screen.getByRole("button", { name: "Admit (signs as Anita Rao, version 2)" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Try it again" }));
  await waitFor(() => expect(posts[1]).toBe("/api/v3/skills/s1/try {}"));
  await userEvent.click(screen.getByRole("button", { name: "Reject" }));
  const go = screen.getByRole("button", { name: "Reject the skill" });
  expect(go).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Reason (required)"), "Wrong fund");
  await userEvent.click(go);
  await waitFor(() => expect(posts[2]).toBe('/api/v3/skills/s1/reject {"reason":"Wrong fund"}'));
});

test("skill review: load error offers a retry", async () => {
  mock([], { "/api/v3/skills/s1": "fail" });
  at("/v3/skill/s1", <SkillReviewPage />, "/v3/skill/:id");
  expect(await screen.findByRole("button", { name: "Try again" })).toBeInTheDocument();
});

test("skills library: filter by source, search, detail with cache", async () => {
  mock([]);
  at("/v3/knowledge/skills", <SkillsPage />);
  expect(await screen.findByText("2 of 2 skills shown")).toBeInTheDocument();
  await userEvent.click(screen.getAllByRole("button", { name: "Core" })[0]!);
  expect(screen.getByText("1 of 2 skills shown")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Answer a question" }));
  expect(await screen.findByText(/212 answers cached/)).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Search skills"), "zzz");
  expect(screen.getByText("No skill matches those filters.")).toBeInTheDocument();
});

test("skills library: error and empty states", async () => {
  mock([], { "/api/v3/skills": "fail" });
  const a = at("/v3/knowledge/skills", <SkillsPage />);
  expect(await screen.findByRole("button", { name: "Try again" })).toBeInTheDocument();
  a.unmount();
  mock([], { "/api/v3/skills": { skills: [] } });
  at("/v3/knowledge/skills", <SkillsPage />);
  expect(await screen.findByText("There are no skills in this office yet.")).toBeInTheDocument();
});
