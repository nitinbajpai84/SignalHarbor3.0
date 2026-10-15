import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";

import { setSessionExpiredHandler } from "../api/client";
import { ThemeProvider } from "../theme";
import { SessionProvider } from "../useSession";
import BuildCentre from "./BuildCentre";
import BuildEnvironment from "./BuildEnvironment";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const cell = (value: string | null, mark: string, from: string) => ({ value, mark, by: "Ann", from });
const QS = (scheduler: unknown) => ({ questions: [
  { key: "warehouse_location", question: "Where may the warehouse live?", answer: cell("Inside this company plane", "guessed", "Default rule") },
  { key: "scheduler", question: "Is there a scheduler today?", answer: scheduler },
] });

function mock(status = 200) {
  const calls: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Ann", company_id: "co-a", roles: ["company_admin"] });
    if (init?.method === "PUT") { calls.push(String(init.body)); return json(200, QS(cell("A cron", "stated", "Confirmed in the environment check"))); }
    return status !== 200 ? json(status, { error: "forbidden", message: "x" }) : json(status, QS(cell(null, "unknown", "Nothing in the profile says")));
  }));
  return calls;
}
const wrap = (el: ReactElement) => render(<MemoryRouter><ThemeProvider><SessionProvider>{el}</SessionProvider></ThemeProvider></MemoryRouter>);

afterEach(() => { vi.unstubAllGlobals(); setSessionExpiredHandler(null); });

describe("Build Centre", () => {
  const HOME = (signed: boolean, confirmed = 5) => ({ rooms: [
    { room: 1, state: "open", environment: { confirmed, of: 5 }, blueprint: { state: signed ? "signed" : "draft", signed_by: signed ? ["Ann Lee"] : [], signed_at: signed ? "2026-06-12" : null }, detail: ["Blueprint drafted: waits for the head of data to sign"] },
    { room: 2, state: signed ? "next" : "locked", pipelines: { sources: 3, last_run: { ok: 2, late: 1, failed: 0 } }, proven: { match: 4, gap: 1, not_yet: 2, uat_signed: 3 }, release: "draft", detail: ["custody: late, owner Sara"] },
    { room: 3, state: "locked", today: { late: 1, failed: 0, open_alerts: 2 }, detail: ["index feed: late, owner Marcus Todd"] },
  ] });
  const home = (signed: boolean, confirmed = 5) => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => (url === "/api/auth/me" ? json(200, { display_name: "Ann", company_id: "co-a", roles: ["company_admin"] }) : json(200, HOME(signed, confirmed)))));
    wrap(<BuildCentre />);
  };
  const tile = (name: string) => screen.getByText(name).closest(".ds-room") as HTMLElement;

  test("home: rooms lit in order", async () => {
    home(false);
    expect(await screen.findByText("Turn the signed catalogue into working data.")).toBeInTheDocument();
    expect(screen.getByText("from: signed gap report")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Review the blueprint" })).toHaveAttribute("href", "/centre/build/blueprint");
    expect(within(tile("Build the data")).getByText(/Not yet/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Open Ops" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Run the pipelines" })).toBeNull();
  });

  test("home: rooms lit from the home shape, each with its counts and one action", async () => {
    home(false, 3);
    await screen.findByText("Architect your design");
    expect(tile("Architect your design")).toHaveClass("ds-room--open");
    expect(tile("Build the data")).toHaveClass("ds-room--dim");
    expect(tile("Ops manager")).toHaveClass("ds-room--dim");
    expect(within(tile("Architect your design")).getByText(/3 of 5 confirmed/)).toBeInTheDocument();
    expect(within(tile("Architect your design")).getAllByRole("link")).toHaveLength(1);
    expect(within(tile("Build the data")).queryAllByRole("link")).toHaveLength(0);
  });

  test("home: detail lines say what is late and what waits", async () => {
    home(true);
    await screen.findByText("Build the data");
    expect(screen.getByText("custody: late, owner Sara")).toBeInTheDocument();
    expect(screen.getByText("index feed: late, owner Marcus Todd")).toBeInTheDocument();
    expect(screen.getAllByText(/signed by Ann Lee on 12 June 2026/).length).toBeGreaterThan(0);
    expect(screen.getByRole("list", { name: "Ops manager: what is late and what waits" }).closest(".ds-side")).not.toBeNull();
  });

  test("home: counts render and room 2 is next once signed", async () => {
    home(true);
    await screen.findByText("Build the data");
    expect(tile("Build the data")).toHaveClass("ds-room--next");
    expect(screen.getByText(/Blueprint signed by Ann Lee/)).toBeInTheDocument();
    expect(screen.getByText(/Pipelines: 3 sources; last run 2 ok, 1 late, 0 failed/)).toBeInTheDocument();
    expect(screen.getByText(/4 match, 1 gap, 2 not yet; UAT signed 3/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Run the pipelines" })).toHaveAttribute("href", "/centre/build/pipelines");
    expect(Array.from(document.querySelectorAll(".ds-room__counts")).map((e) => e.textContent).join(" | ")).toMatch(/2 open alerts/);
  });

  test("environment: marks and sources show, Confirm sends the answer and turns it stated", async () => {
    const calls = mock();
    wrap(<BuildEnvironment />);
    expect(await screen.findByText(/Guessed · Default rule/)).toBeInTheDocument();
    expect(screen.getByText(/Unknown · Nothing in the profile says/)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Is there a scheduler today?"), "A cron");
    await userEvent.click(screen.getByRole("button", { name: "Confirm: Is there a scheduler today?" }));
    expect(await screen.findByText(/Stated · Confirmed in the environment check/)).toBeInTheDocument();
    expect(calls[0]).toContain('"scheduler":"A cron"');
    expect(screen.getByText("A cron")).toBeInTheDocument(); // the stated answer reads as text, no second Confirm
    expect(screen.queryByRole("button", { name: "Confirm: Is there a scheduler today?" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Change: Is there a scheduler today?" }));
    expect(screen.getByLabelText("Is there a scheduler today?")).toHaveValue("A cron");
  });

  test("environment: Confirm all sends every answer in one pass", async () => {
    const calls = mock();
    wrap(<BuildEnvironment />);
    const all = await screen.findByRole("button", { name: "Confirm all" });
    expect(all).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Is there a scheduler today?"), "A cron");
    await userEvent.click(all);
    expect(calls).toHaveLength(1);
    expect(JSON.parse(calls[0] ?? "")).toEqual({ answers: { warehouse_location: "Inside this company plane", scheduler: "A cron" } });
  });

  test("environment: refused", async () => {
    mock(403);
    wrap(<BuildEnvironment />);
    expect(await screen.findByRole("alert")).toHaveTextContent("not part of your plan");
  });
});
