import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import App from "../../../App";
import { setSessionExpiredHandler } from "../../../api/client";
import type { BriefingView, TimerView } from "../api";
import { m1Briefing, m1Flow, m1Nira } from "../copy";
import { saveToken } from "../room/guestToken";

// M1-05, M1-06, M1-07 screens: briefing for the organiser and a participant, the video slot, Nira's panel, five states.

const SID = "a".repeat(32);
const BASE = `/api/modules/m1_intent/sessions/${SID}`;
const RULES = [
  { id: "purpose", label: "What this session is for", text: "Agree what we want to know" },
  { id: "time", label: "How the time is shared", text: "20 minutes in all: 4 for this briefing." },
  { id: "notes", label: "How notes are shown", text: "You choose, note by note, whether your name is shown." },
];
const view = (over: Partial<BriefingView> = {}): BriefingView => ({
  stage: "briefing", company_name: "Harbor Test Co", title: "Agree what we want to know", rules: RULES,
  video: { mode: "placeholder" }, read_aloud: { available: false, message: "Reading aloud is not available yet." },
  me: { role: "organiser", status: "waiting" }, can_send: true, next: "briefing", confirmed: 1, seats: 3, ...over,
});
const TIMER: TimerView = {
  stage: "briefing", timed: true, status: "running", started_at: "x", ends_at: "y", now: "z", remaining_seconds: 240,
  warning_seconds: 60, extensions: [], extension_minutes: [2, 5, 10], may_extend: true,
};
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const calls: { method: string; url: string; body: unknown }[] = [];
const videoHeaders: Record<string, string>[] = [];
const niraCall = (kind: string) =>
  calls.find((c) => c.url.endsWith("/nira") && (c.body as { kind?: string } | undefined)?.kind === kind);

interface World {
  briefing?: BriefingView;
  status?: number;
  body?: unknown;
  hold?: boolean;
  nira?: { text: string };
  timer?: TimerView;
  niraStatus?: number;
  videoStatus?: number;
}
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
      if (url === `${BASE}/timer`) return json(200, w.timer ?? TIMER);
      if (url === `${BASE}/briefing` && method === "GET") {
        if (w.hold) return new Promise<Response>(() => undefined);
        return w.status ? json(w.status, w.body ?? {}) : json(200, w.briefing ?? view());
      }
      if (url === `${BASE}/briefing/confirm`) return json(200, view({ me: { role: "organiser", status: "clear" }, confirmed: 2 }));
      if (url === `${BASE}/briefing/video`) {
        videoHeaders.push((init?.headers ?? {}) as Record<string, string>);
        return w.videoStatus ? json(w.videoStatus, { error: "x" }) : new Response("mp4", { status: 200 }); // a string body: jsdom's Blob has no stream() for Node's Response
      }
      if (url === `${BASE}/briefing/send`) return json(200, { state: "private_rooms" });
      if (url === `${BASE}/nira`)
        return w.niraStatus
          ? json(w.niraStatus, { error: "invalid", message: "Please write your question for Nira." })
          : json(200, { available: true, name: "Nira", role: "the guide", text: w.nira?.text ?? "You have 20 minutes." });
      return json(404, {});
    }),
  );
}
const inRules = (text: string) => within(screen.getByRole("region", { name: m1Briefing.rulesTitle })).getByText(text);
const open = () =>
  render(
    <MemoryRouter initialEntries={[`/modules/m1_intent/sessions/${SID}/briefing`]}>
      <App />
    </MemoryRouter>,
  );

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  sessionStorage.clear();
  localStorage.clear();
  setSessionExpiredHandler(null);
});

describe("briefing: five states", () => {
  test("loading", async () => {
    mock({ hold: true });
    open();
    await waitFor(() => expect(screen.getAllByRole("status").some((e) => /Loading/.test(e.textContent ?? ""))).toBe(true));
  });

  test("error: one plain sentence from the server, and a way to try again", async () => {
    mock({ status: 404, body: { error: "not_found", message: "We could not find that session." } });
    open();
    expect(await screen.findByText("We could not find that session.")).toBeInTheDocument();
    mock({ status: 500, body: { detail: "boom" } });
    open();
    expect((await screen.findAllByRole("button", { name: "Try again" })).length).toBeGreaterThan(0);
    expect(document.body).not.toHaveTextContent("boom");
  });

  test("refused: no seat in this session", async () => {
    mock({ status: 403, body: { error: "forbidden", message: "You do not have a seat in this session." } });
    open();
    expect(await screen.findByText(/You do not have access/)).toBeInTheDocument();
  });

  test("populated: company, title, every rule from the session, in plain words", async () => {
    mock({});
    open();
    expect(await screen.findByRole("heading", { level: 1, name: "Agree what we want to know" })).toBeInTheDocument();
    expect(within(screen.getByRole("main")).getByText("Harbor Test Co")).toBeInTheDocument();
    const rules = screen.getByRole("region", { name: m1Briefing.rulesTitle });
    for (const r of RULES) {
      expect(within(rules).getByText(r.label)).toBeInTheDocument();
      expect(within(rules).getByText(r.text)).toBeInTheDocument();
    }
  });

  test("empty: a briefing that cannot be read is an error with a retry, never a blank screen", async () => {
    mock({ status: 204 }); // nothing usable came back
    open();
    expect(await screen.findAllByRole("alert")).not.toHaveLength(0);
  });
});

describe("video slot (M1-06)", () => {
  test("placeholder card with the text version beside it", async () => {
    mock({});
    open();
    expect(await screen.findByText(m1Briefing.videoPlaceholder)).toBeInTheDocument();
    expect(inRules("Agree what we want to know")).toBeInTheDocument();
  });

  test("a stored video plays from the company's own space, fetched with the guest's token (a video tag cannot send one)", async () => {
    videoHeaders.length = 0;
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: () => "blob:briefing-video", revokeObjectURL: () => undefined }));
    saveToken({ token: "guest-token-for-test", sessionId: SID });
    mock({ briefing: view({ video: { mode: "file", content_type: "video/mp4" } }) });
    const { container } = open();
    await screen.findByRole("heading", { level: 1 });
    await waitFor(() => expect(container.querySelector("video")).toHaveAttribute("src", "blob:briefing-video"));
    expect(videoHeaders[0]?.["X-Session-Token"]).toBe("guest-token-for-test");
    expect(screen.queryByText(m1Briefing.videoPlaceholder)).not.toBeInTheDocument();
    expect(inRules("Agree what we want to know")).toBeInTheDocument();
  });

  test("a video that cannot be loaded says so and leaves the rules", async () => {
    mock({ briefing: view({ video: { mode: "file", content_type: "video/mp4" } }), videoStatus: 401 });
    const { container } = open();
    expect(await screen.findByText(m1Briefing.videoFailed)).toBeInTheDocument();
    expect(container.querySelector("video")).toBeNull();
    expect(inRules("Agree what we want to know")).toBeInTheDocument();
  });

  test("the no-video option hides the slot and keeps the rules", async () => {
    mock({ briefing: view({ video: { mode: "none" } }) });
    open();
    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByRole("region", { name: m1Briefing.videoTitle })).not.toBeInTheDocument();
    expect(inRules("Agree what we want to know")).toBeInTheDocument();
  });

  test("read aloud says plainly that it is not available yet", async () => {
    mock({});
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: m1Briefing.readAloud }));
    expect(screen.getByText("Reading aloud is not available yet.")).toBeInTheDocument();
  });
});

describe("read aloud uses the same speech as the private room (M1-UI1)", () => {
  test("when speech is available the button speaks the written rules; if it cannot play, the person is told plainly", async () => {
    mock({ briefing: view({ read_aloud: { available: true } }) });
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: m1Briefing.readAloud }));
    const spoke = await waitFor(() => {
      const c = calls.find((x) => x.url === `${BASE}/voice/speak`);
      expect(c).toBeDefined();
      return c;
    });
    const said = (spoke?.body as { text: string }).text;
    for (const r of RULES) expect(said).toContain(r.text);
    expect(await screen.findByText(m1Briefing.aloudFailed)).toBeInTheDocument(); // the stub answers 404: no sound, a plain line
  });
});

describe("organiser", () => {
  test("sees how many are clear, can say clear, and sends everyone to their rooms", async () => {
    mock({});
    const user = userEvent.setup();
    open();
    expect(await screen.findByText(m1Briefing.ready(1, 3))).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: m1Briefing.clear }));
    expect(await screen.findByText(m1Briefing.ready(2, 3))).toBeInTheDocument();
    expect(screen.getByText(m1Briefing.clearDone)).toBeInTheDocument();
    expect(calls.find((c) => c.url.endsWith("/briefing/confirm"))?.body).toEqual({ answer: "clear" });
    await user.click(screen.getByRole("button", { name: m1Briefing.send }));
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/briefing/send") && c.method === "POST")).toBe(true));
  });

  test("the timer with the extend control is on the screen", async () => {
    mock({});
    open();
    expect(await screen.findByRole("timer")).toHaveTextContent("4:00");
    expect(screen.getByRole("group", { name: "Add time" })).toBeInTheDocument();
  });
});

describe("participant", () => {
  const me: BriefingView["me"] = { role: "participant", status: "waiting" };
  test("has no send button and no count; can say clear", async () => {
    mock({ briefing: view({ me, can_send: false, confirmed: undefined, seats: undefined }) });
    open();
    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByRole("button", { name: m1Briefing.send })).not.toBeInTheDocument();
    expect(screen.queryByText(/people say they are clear/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: m1Briefing.clear })).toBeInTheDocument();
  });

  test("a latecomer is told the rooms are open and to read the rules first", async () => {
    mock({ briefing: view({ stage: "private_rooms", me, can_send: false, next: "briefing", confirmed: undefined }) });
    open();
    expect(await screen.findByText(m1Briefing.lateNote)).toBeInTheDocument();
    expect(inRules("Agree what we want to know")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: m1Flow.toRoom })).toHaveAttribute("href", `/modules/m1_intent/sessions/${SID}/room`);
  });

  test("once clear in an open session they are told they can go to their room", async () => {
    mock({ briefing: view({ stage: "private_rooms", me: { role: "participant", status: "clear" }, can_send: false, next: "room" }) });
    open();
    expect(await screen.findByText(m1Briefing.readyForRoom)).toBeInTheDocument();
    expect(screen.queryByText(m1Briefing.lateNote)).not.toBeInTheDocument();
  });
});

describe("Nira's panel (M1-07)", () => {
  test("is labelled as Nira, the guide, and shows her answer under that name", async () => {
    mock({});
    const user = userEvent.setup();
    open();
    const panel = await screen.findByRole("region", { name: m1Nira.name });
    await user.type(within(panel).getByLabelText(m1Nira.question), "How long do we have?");
    await user.click(within(panel).getByRole("button", { name: m1Nira.ask }));
    const log = await within(panel).findByRole("log", { name: m1Nira.conversation });
    await waitFor(() => expect(log).toHaveTextContent("You have 20 minutes."));
    expect(log).toHaveTextContent("How long do we have?"); // her answer follows the person's own question
    expect(niraCall("ask")?.body).toEqual({ kind: "ask", question: "How long do we have?" });
  });

  test("asking marks the person as having asked, not clear", async () => {
    mock({ briefing: view({ me: { role: "participant", status: "waiting" }, can_send: false }) });
    const user = userEvent.setup();
    open();
    await user.type(await screen.findByLabelText(m1Nira.question), "Where is my room?");
    await user.click(screen.getByRole("button", { name: m1Nira.ask }));
    expect(await screen.findByText(m1Briefing.asked)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: m1Briefing.clear })).toBeInTheDocument();
  });

  test("what do I do now sends that kind and needs no question", async () => {
    mock({ nira: { text: "Read the rules, then say you are clear." } });
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: m1Nira.now }));
    expect(await screen.findByRole("log", { name: m1Nira.conversation })).toHaveTextContent("Read the rules, then say you are clear.");
    expect(niraCall("now")?.body).toEqual({ kind: "now" });
  });

  test("an empty question is not sent", async () => {
    mock({});
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: m1Nira.ask }));
    expect(await screen.findByText(m1Nira.needQuestion)).toBeInTheDocument();
    expect(niraCall("ask")).toBeUndefined();
  });

  test("a refusal from the server is shown in its own plain words", async () => {
    mock({ niraStatus: 422 });
    const user = userEvent.setup();
    open();
    await user.type(await screen.findByLabelText(m1Nira.question), "x");
    await user.click(screen.getByRole("button", { name: m1Nira.ask }));
    expect(await screen.findByText("Please write your question for Nira.")).toBeInTheDocument();
  });

  test("her welcome shows on the briefing screen without being asked", async () => {
    mock({ nira: { text: "Welcome, everyone." } });
    open();
    const panel = await screen.findByRole("region", { name: m1Nira.name });
    expect(await within(panel).findByText("Welcome, everyone.")).toBeInTheDocument();
    expect(niraCall("welcome")?.body).toEqual({ kind: "welcome" });
  });

  test("at the warning time the panel shows her one-minute warning", async () => {
    mock({ nira: { text: "About one minute is left." }, timer: { ...TIMER, status: "warning", remaining_seconds: 60 } });
    open();
    const panel = await screen.findByRole("region", { name: m1Nira.name });
    await waitFor(() => expect(niraCall("warning")).toBeDefined());
    await waitFor(() => expect(within(panel).getByRole("log", { name: m1Nira.conversation })).toHaveTextContent("About one minute is left."));
  });

  test("with plenty of time left she gives no warning", async () => {
    mock({});
    open();
    await screen.findByRole("timer");
    expect(niraCall("warning")).toBeUndefined();
  });
});
