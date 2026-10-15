import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { setSessionExpiredHandler } from "../api/client";
import { ThemeProvider } from "../theme";
import { SessionProvider } from "../useSession";
import InterviewPage from "./InterviewPage";

// The one interview: five screen states, the people list with status, a draft with its source to Keep or Change, the progress line,
// the last question with its share choice, and a guest's own link. fetch is stubbed; the page is not wired into App.tsx by this package.

const card = (over: object = {}) => ({ qid: "Q3", agent: "north", mode: "confirm", text: "Which numbers tell you it is going well?", draft: { text: "Single-issuer concentration 13.32%", from: "Monthly pack, Sept, p.3" }, final: false, share: false, ...over });
const iv = (over: object = {}) => ({
  person: { id: "wei-chen", name: "Wei Chen" }, status: "in_progress", kind: "participant",
  progress: { answered: 6, of: 13, minutes_left: 7 },
  log: [{ who: "north", qid: "Q3", text: "From Monthly pack, Sept, p.3: Single-issuer concentration 13.32%. Is that right?" }],
  card: card(), ...over,
});
const person = (over: object = {}) => ({ id: "wei-chen", name: "Wei Chen", role: "Analyst", kind: "participant", status: "in_progress", answered: 2, of: 7, self: true, ...over });

const calls: { method: string; url: string; headers: Record<string, string>; body: unknown }[] = [];
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

interface World { list?: object; listStatus?: number; hold?: boolean; started?: object; answered?: object; startStatus?: number; roles?: string[] }
function mock(w: World) {
  calls.length = 0;
  document.cookie = "sh_csrf=tok123";
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ method, url, headers: (init?.headers ?? {}) as Record<string, string>, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    if (url === "/api/auth/me") return json(200, { display_name: "Wei Chen", company_id: "co-a", roles: w.roles ?? ["company_admin"] });
    if (url === "/api/company") return json(200, { company_id: "co-a", name: "Lakeside Test Co", industry: "family_office" });
    if (url === "/api/interview") {
      if (w.hold) return new Promise<Response>(() => undefined);
      if (w.listStatus) return json(w.listStatus, { error: w.listStatus === 403 ? "forbidden" : "x", message: "x" });
      return json(200, w.list ?? { people: [person()], organiser: true });
    }
    if (/\/start$/.test(url)) return w.startStatus === 403 ? json(403, { error: "module_not_available", message: "This module is not part of your plan." }) : w.startStatus ? json(w.startStatus, { error: "bad_link", message: "This link is not valid any more. Please ask the person who sent it for a new one." }) : json(200, w.started ?? iv());
    if (/\/answer$/.test(url)) return json(200, w.answered ?? iv({ card: card({ qid: "Q4", mode: "ask", draft: null, text: "What would you like to see coming?" }), progress: { answered: 7, of: 13, minutes_left: 6 } }));
    if (/\/finish$/.test(url)) return json(200, iv({ status: "done", card: null, progress: { answered: 7, of: 13, minutes_left: 0 } }));
    if (/\/link$/.test(url)) return json(200, { person: "wei-chen", link: "/interview/iv.co-a.abc.def" });
    return json(404, {});
  }));
}

const open = (path = "/company/interview") => render(
  <MemoryRouter initialEntries={[path]}>
    <ThemeProvider><SessionProvider>
      <Routes>
        <Route path="/company/interview" element={<InterviewPage />} />
        <Route path="/interview/:token" element={<InterviewPage />} />
      </Routes>
    </SessionProvider></ThemeProvider>
  </MemoryRouter>,
);

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  sessionStorage.clear();
  setSessionExpiredHandler(null);
});

describe("The one interview: five states", () => {
  test("loading", async () => {
    mock({ hold: true });
    open();
    expect(await screen.findByRole("status")).toHaveTextContent("Loading");
  });

  test("empty: says who is missing, in plain words", async () => {
    mock({ list: { people: [], organiser: true } });
    open();
    expect(await screen.findByText(/Nobody is on the people list yet/)).toBeInTheDocument();
  });

  test("error: one sentence and a way to try again", async () => {
    mock({ listStatus: 500 });
    const user = userEvent.setup();
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong");
    mock({});
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("listitem", { name: "Wei Chen" })).toBeInTheDocument();
  });

  test("refused: a plain sentence, no codes", async () => {
    mock({ listStatus: 403 });
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent("You do not have access to this. Ask your administrator.");
  });

  test("populated: everyone with their status, and an invite link", async () => {
    mock({ list: { people: [person(), person({ id: "dan-data", name: "Dan Data", status: "done", answered: 7, of: 7, self: false }), person({ id: "sue", name: "Sue Sponsor", status: "not_started", answered: 0, of: 0, self: false })], organiser: true } });
    const user = userEvent.setup();
    open();
    expect(within(await screen.findByRole("listitem", { name: "Wei Chen" })).getByText("In progress")).toBeInTheDocument();
    expect(within(screen.getByRole("listitem", { name: "Dan Data" })).getByText("Finished")).toBeInTheDocument();
    expect(within(screen.getByRole("listitem", { name: "Sue Sponsor" })).getByText("Not started")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Invite link for Dan Data" }));
    expect(await screen.findByLabelText("Link for Dan Data")).toHaveValue(`${window.location.origin}/interview/iv.co-a.abc.def`);
    expect(screen.getByText(/Nothing is sent/)).toBeInTheDocument();
  });
});

describe("Signed-in face", () => {
  test("lists who answered, with how far each has got", async () => {
    mock({ list: { people: [person({ answered: 2, of: 7 }), person({ id: "dan-data", name: "Dan Data", status: "done", answered: 7, of: 7, self: false })], organiser: true } });
    open();
    expect(within(await screen.findByRole("listitem", { name: "Dan Data" })).getByText("7 of 7")).toBeInTheDocument();
    expect(within(screen.getByRole("listitem", { name: "Wei Chen" })).getByText("2 of 7")).toBeInTheDocument();
  });
});

describe("The interview chat", () => {
  test("a draft shows its source and the progress line; Keep sends the keep action", async () => {
    mock({});
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: "Open Wei Chen's interview" }));
    expect(await screen.findByText("6 of 13 · about 7 minutes left")).toBeInTheDocument();
    const draft = screen.getByRole("article", { name: "Draft to confirm" });
    expect(within(draft).getByText("From: Monthly pack, Sept, p.3. Please confirm.")).toBeInTheDocument();
    await user.click(within(draft).getByRole("button", { name: "Keep" }));
    expect(calls.find((x) => /\/answer$/.test(x.url))?.body).toEqual({ action: "keep" });
    expect(await screen.findByText("7 of 13 · about 6 minutes left")).toBeInTheDocument();
    expect(screen.getByLabelText("Your answer")).toBeInTheDocument();
  });

  test("Change lets the person write their own words", async () => {
    mock({});
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: "Open Wei Chen's interview" }));
    await user.click(await screen.findByRole("button", { name: "Change" }));
    const box = screen.getByLabelText("Your answer");
    await user.clear(box);
    await user.type(box, "About 12 percent");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(calls.find((x) => /\/answer$/.test(x.url))?.body).toEqual({ text: "About 12 percent", action: "change" });
  });

  test("the last question is marked, and the share choice is three buttons", async () => {
    mock({ started: iv({ card: card({ qid: "Q14", mode: "ask", draft: null, final: true, text: "Is there anything else?" }) }), answered: iv({ card: card({ qid: "Q14", mode: "followup", draft: null, final: true, share: true, text: "May we share this note?" }) }) });
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: "Open Wei Chen's interview" }));
    expect(await screen.findByText("One last question")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Your answer"), "Reports are late");
    await user.click(screen.getByRole("button", { name: "Send" }));
    await user.click(await screen.findByRole("button", { name: "Anonymous" }));
    expect(calls.filter((x) => /\/answer$/.test(x.url)).pop()?.body).toEqual({ text: "anonymous" });
    expect(screen.getByRole("button", { name: "Named" })).toBeInTheDocument();
  });

  test("the organiser can see another person's interview but not answer it", async () => {
    mock({ list: { people: [person({ self: false })], organiser: true } });
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: "Open Wei Chen's interview" }));
    expect(await screen.findByText(/Only Wei Chen can answer/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Your answer")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Keep" })).not.toBeInTheDocument();
  });

  test("I am done finishes the interview with a thank you", async () => {
    mock({});
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: "Open Wei Chen's interview" }));
    await user.click(await screen.findByRole("button", { name: "I am done" }));
    expect(await screen.findByText(/Thank you. That is everything/)).toBeInTheDocument();
  });
});

describe("A guest's own link", () => {
  test("starts with the token in the header only, never in the body", async () => {
    mock({});
    open("/interview/iv.co-a.abc.def");
    expect(await screen.findByText("6 of 13 · about 7 minutes left")).toBeInTheDocument();
    const start = calls.find((x) => /guest\/start$/.test(x.url));
    expect(start?.headers["X-Session-Token"]).toBe("iv.co-a.abc.def");
    expect(JSON.stringify(start?.body)).not.toContain("iv.co-a");
    expect(calls.some((x) => x.url === "/api/interview")).toBe(false);
  });

  test("shows the GuestShell header and no signed-in top bar", async () => {
    mock({});
    const { container } = open("/interview/iv.co-a.abc.def");
    expect(await screen.findByText("6 of 13 · about 7 minutes left")).toBeInTheDocument();
    expect(container.querySelector(".ds-topbar")).toHaveTextContent("Signal Harbor");
    expect(container.querySelector(".n-topbar")).toBeNull();
    expect(container.querySelector(".ds-screen")).not.toBeNull();
    expect(screen.getByRole("heading", { level: 1, name: "Your interview" })).toBeInTheDocument();
  });

  test("a link that is no longer valid says so in plain words", async () => {
    mock({ startStatus: 404 });
    open("/interview/iv.co-a.abc.def");
    expect(await screen.findByRole("alert")).toHaveTextContent("This link is not valid any more. Please ask the person who sent it for a new one.");
  });

  test("a signed-in person opening someone else's link is told so plainly, not that a module is missing", async () => {
    mock({ startStatus: 403 });
    open("/interview/iv.co-a.abc.def?for=Aaron");
    const msg = "You are signed in as someone else. Sign out to answer as Aaron, or open your interview from your home page.";
    expect(await screen.findByRole("alert")).toHaveTextContent(msg);
    expect(screen.queryByText(/not part of your plan/)).not.toBeInTheDocument();
  });
});
