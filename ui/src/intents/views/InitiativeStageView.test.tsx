import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, test, vi } from "vitest";

import InitiativeStageView, { stageCopy } from "./InitiativeStageView";

// The Initiative stage view (spec 22, Screen C). fetch is stubbed; synthetic text only.
const SID = "d".repeat(32);
const S = `/api/modules/m1_intent/sessions/${SID}`;
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const wall = (role = "organiser", sid: string | null = SID) => ({ session_id: sid, role, intent: { title: "F17 Faster report", purpose: "Cut the days to produce the client report", state: "open", ends: null } });
const PEOPLE = {
  me: { person_id: "p1", role: "organiser", status: "joined" }, counts: { invited: 0, named: 2 },
  people: [{ person_id: "p1", name: "Janet Shaw", role: "organiser", status: "joined" }, { person_id: "p2", name: "Daniel Kerr", role: "sponsor", status: "invited" }, { person_id: "p3", name: "Aaron Lyle", role: "participant", status: "invited" }],
};
const calls: string[] = [];

function mock(opts: { role?: string; sid?: string | null; people?: unknown; start?: Response; frozen?: boolean } = {}) {
  calls.length = 0;
  let state = "draft";
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push(`${init?.method ?? "GET"} ${url}`);
    if (url === "/api/intents/i1/wall") return json(200, { ...wall(opts.role, opts.sid === undefined ? SID : opts.sid), ...(opts.frozen ? { stages: [{ key: "think_unfiltered", state: "closed" }, { key: "define_strategically", state: "open" }] } : {}) });
    if (url === "/api/intents/i1/clock") return json(200, { stages: [{ key: "think_unfiltered", due: "2026-10-12T09:00:00+00:00", days: 3 }] });
    if (url.startsWith("/api/intents/i1/people")) return json(200, opts.people ?? PEOPLE);
    if (url === `${S}/start`) { if (opts.start) return opts.start; state = "lobby"; return json(201, { join_path: "/join/abc", state: "lobby" }); }
    if (url === S) return json(200, { id: SID, state, editable: state === "draft", preparation: { wall_window_days: 3, topic: "Finance" } });
    if (url.startsWith(`${S}/lobby`)) return state === "draft" ? json(404, {}) : json(200, { session_id: SID, state, organiser: true, seat_count: 3, arrived: 1, seats: [], me: null });
    if (url.startsWith(`${S}/join-link`)) return json(200, { join_path: "/join/abc", state });
    return json(404, {});
  }));
}
const open = () => render(<MemoryRouter initialEntries={["/centre/intent/i1"]}><Routes><Route path="/centre/intent/:intentId" element={<InitiativeStageView />} /></Routes></MemoryRouter>);
afterEach(() => vi.unstubAllGlobals());

describe("the Initiative stage view", () => {
  test("a prepared wall shows the hand-over card, not an error, and never asks the lobby", async () => {
    mock(); open();
    expect(await screen.findByText(stageCopy.card)).toBeInTheDocument();
    const card = screen.getByTestId("handover");
    expect(card).toHaveTextContent("Cut the days to produce the client report");
    await waitFor(() => expect(card).toHaveTextContent("Open until 12 Oct (3 working days)."));
    expect(card).toHaveTextContent("Lanes: Tracking today, Missing, Watch, Levers.");
    await waitFor(() => expect(card).toHaveTextContent("Invited: 2 people."));
    expect(screen.getByRole("button", { name: "Open the wall" })).toBeEnabled();
    expect(screen.getByRole("link", { name: "Change the wall setup" })).toHaveAttribute("href", `/modules/m1_intent/sessions/${SID}`);
    expect(screen.queryByText("We could not find that.")).toBeNull();
    expect(calls.some((c) => c.includes("/lobby"))).toBe(false);
  });

  test("one invitation draft per named person", async () => {
    mock(); open();
    const list = await screen.findByTestId("drafts");
    expect(list).toHaveTextContent("Daniel Kerr: Janet Shaw has opened an Initiative and asked you to take part");
    expect(list).toHaveTextContent("Aaron Lyle");
    expect(list).not.toHaveTextContent("Janet Shaw: Janet");
  });

  test("nobody named shows the empty line", async () => {
    mock({ people: { ...PEOPLE, counts: { invited: 0, named: 0 }, people: [PEOPLE.people[0]] } }); open();
    expect(await screen.findByText(stageCopy.nobody)).toBeInTheDocument();
  });

  test("Open the wall starts the room once and then shows the invite panel", async () => {
    mock(); open();
    await userEvent.click(await screen.findByRole("button", { name: "Open the wall" }));
    expect(await screen.findByText(stageCopy.cardOpen)).toBeInTheDocument();
    expect(calls.filter((c) => c === `POST ${S}/start`)).toHaveLength(1);
    expect(screen.getByRole("link", { name: stageCopy.goToWall })).toHaveAttribute("href", "/centre/intent/i1/wall");
    expect(screen.queryByRole("button", { name: "Open the wall" })).toBeNull();
    await waitFor(() => expect(screen.getByRole("region", { name: "Invite" })).toBeInTheDocument());
  });

  test("a clashing topic says so in plain words", async () => {
    mock({ start: json(409, { message: "x" }) }); open();
    await userEvent.click(await screen.findByRole("button", { name: "Open the wall" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(stageCopy.topicTaken);
  });

  test("a reader gets a link to the wall and no controls", async () => {
    mock({ role: "participant" }); open();
    expect(await screen.findByRole("link", { name: stageCopy.goToWall })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Open the wall" })).toBeNull();
  });

  test("once the wall is frozen the intent page moves on to Define (F50)", async () => {
    mock({ frozen: true }); open();
    expect(await screen.findByText(stageCopy.defineOpen)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: stageCopy.goToDefine })).toHaveAttribute("href", "/centre/intent/i1/define");
    expect(screen.queryByText(stageCopy.cardOpen)).toBeNull();
    expect(screen.queryByRole("button", { name: "Open the wall" })).toBeNull();
  });
});
