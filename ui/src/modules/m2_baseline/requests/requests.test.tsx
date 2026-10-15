// slow under a full parallel run; the 5 s default timed out a different test each time
vi.setConfig({ testTimeout: 30000 });
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import OwnerAnswerPage from "../../../pages/OwnerAnswerPage";
import { ThemeProvider } from "../../../theme";
import type { OwnerForm, Outstanding, QuestionnaireSpec, RequestRow } from "../api";
import { m2Form as F, m2Req as R } from "../copy";
import MeetingScreen from "./MeetingScreen";
import RequestsScreen from "./RequestsScreen";

// M2-P02 screens in their five states: the requests and outstanding view, the owner's answer page, answering in a meeting.
// fetch is stubbed. Family-office wording, synthetic.

const BASE = "/api/modules/m2_baseline";
const BID = "baseline1";
const TOKEN = `ow-${"a".repeat(32)}-${"s".repeat(43)}`;
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

interface Call { method: string; url: string; headers: Record<string, string>; body: unknown }
const calls: Call[] = [];
function mock(handler: (call: Call) => Response | Promise<Response>) {
  calls.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const call = { method: init?.method ?? "GET", url, headers: (init?.headers ?? {}) as Record<string, string>, body: init?.body ? JSON.parse(String(init.body)) : undefined };
    calls.push(call);
    return handler(call);
  }));
}
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

const spec: QuestionnaireSpec = {
  marks: [{ value: "stated", label: "I am sure" }, { value: "guessed", label: "My best guess" }, { value: "unknown", label: "I don't know" }],
  limits: { text_chars: 500, hops: 10 },
  fields: [
    { key: "tracked_today", kind: "choice", question: "Is it tracked today?", choices: [{ value: "tracked_now", label: "Yes, it is tracked" }, { value: "partly", label: "Partly" }, { value: "not_tracked", label: "No, it is not tracked" }] },
    { key: "source", kind: "text", question: "Where does it come from?" },
    { key: "in_between", kind: "hops", question: "In between: who reshapes it, and where? Is it done by hand?", hop: [{ key: "who", label: "Who" }, { key: "step", label: "Where and what they change (for example a workbook)" }, { key: "manual", label: "Done by hand" }] },
  ],
};
const ownerForm = (over: Partial<OwnerForm> = {}): OwnerForm => ({
  owner_name: "Tom Reyes", role: "business owner", state: "opened", expires_at: "2026-10-17T10:00:00+00:00",
  kpis: [{ id: "k1", name: "Funding capacity", answers: null }, { id: "k2", name: "Capital call timing", answers: null }], questionnaire: spec, confirmable: [], ...over,
});

const row = (over: Partial<RequestRow> = {}): RequestRow => ({
  id: "r1", owner_name: "Wei Chen", role: "data owner", state: "no_reply", kpis: [{ id: "k3", name: "Distribution lag" }], sent_at: "2026-10-01T10:00:00+00:00",
  opened_at: null, answered_at: null, reminders: [], link: "open", expires_at: "2026-10-15T10:00:00+00:00", answered_kpis: 0, meeting: null,
  days_waiting: 3, remind_due: true, organiser_told: false, next_reminder_on: null, nira: "Wei Chen has not replied in 3 days. A reminder is due: press Remind and I will note it.", ...over,
});
const outstanding = (rows: RequestRow[], over: Partial<Outstanding> = {}): Outstanding => ({
  requests: rows, summary: { asked: rows.length, answered: rows.filter((r) => r.state === "answered").length, outstanding: rows.filter((r) => r.state !== "answered").length, in_meeting: 0 },
  waiting_on: [{ kpi_id: "k3", kpi_name: "Distribution lag", waiting_on: ["Wei Chen"] }], alerts: [], not_yet_asked: [], ...over,
});

function openOwner(token = TOKEN) {
  return render(
    <MemoryRouter initialEntries={[`/answer/${token}`]}>
      <ThemeProvider>
        <Routes>
          <Route path="/answer/:token" element={<OwnerAnswerPage />} />
        </Routes>
      </ThemeProvider>
    </MemoryRouter>,
  );
}
const openRequests = (path = `/modules/m2_baseline/requests/${BID}`) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/modules/m2_baseline/requests/:baselineId" element={<RequestsScreen />} />
        <Route path="/modules/m2_baseline/requests/:baselineId/meeting" element={<MeetingScreen />} />
      </Routes>
    </MemoryRouter>,
  );

describe("the owner's answer page: five states", () => {
  test("loading", async () => {
    mock(() => new Promise<Response>(() => undefined));
    openOwner();
    expect(await screen.findByRole("status")).toHaveTextContent("Loading");
  });

  test("error: a link that does not work shows the server's sentence, never the token", async () => {
    mock(() => json(404, { error: "link_invalid", message: "This link is not working. Please ask for a new one." }));
    openOwner();
    expect(await screen.findByRole("alert")).toHaveTextContent("This link is not working. Please ask for a new one.");
    expect(document.querySelector(".guest-header")).not.toBeNull();
    expect(document.querySelector(".n-topbar")).toBeNull();
    expect(screen.getByRole("radio", { name: "Dark" })).toBeInTheDocument();
    expect(document.body.textContent).not.toContain(TOKEN);
  });

  test("refused: too many tries has its own sentence", async () => {
    mock(() => json(429, { error: "too_many_tries", message: "x" }));
    openOwner();
    expect(await screen.findByRole("alert")).toHaveTextContent(F.tooMany);
  });

  test("empty: a request with no measures still opens, with the send button", async () => {
    mock(() => json(200, ownerForm({ kpis: [] })));
    openOwner();
    expect(await screen.findByRole("button", { name: F.send })).toBeInTheDocument();
  });

  test("populated: the token travels only in the header, with the person's measures and questions", async () => {
    mock(() => json(200, ownerForm()));
    openOwner();
    expect(await screen.findByText(F.measure(1, 2, "Funding capacity"))).toBeInTheDocument();
    expect(screen.getByText(F.measure(2, 2, "Capital call timing"))).toBeInTheDocument();
    expect(screen.getAllByText("Is it tracked today?").length).toBeGreaterThan(0);
    expect(screen.getAllByText("I don't know").length).toBeGreaterThan(0);
    expect(calls[0]).toMatchObject({ method: "POST", url: `${BASE}/answer/form`, headers: { "X-Session-Token": TOKEN } });
    expect(calls[0]?.url).not.toContain(TOKEN);
    expect(document.body.textContent).not.toContain(TOKEN);
  });
});

describe("the questionnaire", () => {
  test("an answer with no mark is not sent; the person is told to say how sure they are", async () => {
    mock(() => json(200, ownerForm()));
    openOwner();
    const first = (await screen.findByText(F.measure(1, 2, "Funding capacity"))).closest("section") as HTMLElement;
    const user = userEvent.setup();
    await user.click(within(first).getByLabelText("Partly"));
    await user.click(within(first).getByRole("button", { name: F.saveMeasure }));
    expect(await within(first).findByRole("alert")).toHaveTextContent(F.needMark);
    expect(calls.filter((c) => c.url.endsWith("/answer/save"))).toHaveLength(0);
  });

  test("saving sends each answer with its mark; I don't know sends no value; a hop sends who, step and by hand", async () => {
    mock((c) => (c.url.endsWith("/answer/save") ? json(200, { saved: { id: "x", kpi_id: "k1", owner_name: "Tom Reyes", sample_title: null } }) : json(200, ownerForm())));
    openOwner();
    const first = (await screen.findByText(F.measure(1, 2, "Funding capacity"))).closest("section") as HTMLElement;
    const user = userEvent.setup();
    const marks = (field: string) => within(within(first).getByText(field).closest("fieldset") as HTMLElement);
    await user.click(within(first).getByLabelText("Partly"));
    await user.click(marks("Is it tracked today?").getAllByLabelText("I am sure")[0] as HTMLElement);
    await user.click(marks("Where does it come from?").getByLabelText("I don't know"));
    await user.type(within(first).getByLabelText("Who"), "Sara Lim");
    await user.type(within(first).getByLabelText(/Where and what they change/), "Workbook");
    await user.click(within(first).getByLabelText("Done by hand"));
    await user.click(marks("In between: who reshapes it, and where? Is it done by hand?").getByLabelText("My best guess"));
    await user.click(within(first).getByRole("button", { name: F.saveMeasure }));
    expect(await within(first).findByText(F.saved)).toBeInTheDocument();
    const sent = calls.find((c) => c.url.endsWith("/answer/save"));
    expect(sent?.headers["X-Session-Token"]).toBe(TOKEN);
    expect(sent?.body).toEqual({ kpi_id: "k1", answers: {
      tracked_today: { value: "partly", mark: "stated" },
      source: { value: null, mark: "unknown" },
      in_between: { value: [{ who: "Sara Lim", step: "Workbook", manual: true }], mark: "guessed" },
    } });
  });

  test("a server refusal is shown in its own plain words", async () => {
    mock((c) => (c.url.endsWith("/answer/save") ? json(422, { error: "invalid", message: "Please choose one of the answers offered." }) : json(200, ownerForm())));
    openOwner();
    const first = (await screen.findByText(F.measure(1, 2, "Funding capacity"))).closest("section") as HTMLElement;
    const user = userEvent.setup();
    await user.click(within(first).getAllByLabelText("I don't know")[0] as HTMLElement);
    await user.click(within(first).getByRole("button", { name: F.saveMeasure }));
    expect(await within(first).findByRole("alert")).toHaveTextContent("Please choose one of the answers offered.");
  });

  test("sending the answers says thank you", async () => {
    mock((c) => (c.url.endsWith("/answer/submit") ? json(200, { state: "answered" }) : json(200, ownerForm())));
    openOwner();
    await userEvent.setup().click(await screen.findByRole("button", { name: F.send }));
    expect(await screen.findByText(F.sentThanks)).toBeInTheDocument();
  });

  test("a sample is read and sent with the file name, and its title is shown", async () => {
    mock((c) => (c.url.endsWith("/answer/sample") ? json(200, { saved: { id: "x", kpi_id: "k1", owner_name: "Tom Reyes", sample_title: "statement.csv" } }) : json(200, ownerForm())));
    openOwner();
    const first = (await screen.findByText(F.measure(1, 2, "Funding capacity"))).closest("section") as HTMLElement;
    const file = new File(["date,balance\n"], "statement.csv", { type: "text/csv" });
    await userEvent.setup().upload(within(first).getByLabelText(F.addSample), file);
    expect(await within(first).findByText(F.sampleAdded("statement.csv"))).toBeInTheDocument();
    expect(within(first).getByText(/^Uploaded: statement\.csv, /)).toBeInTheDocument();
    expect((within(first).getByLabelText(F.addSample) as HTMLInputElement).value).toBe("");  // the picker is reset, not left on the old file
    const sent = calls.find((c) => c.url.endsWith("/answer/sample"));
    expect(sent?.body).toMatchObject({ kpi_id: "k1", filename: "statement.csv" });
  });
});

describe("the list of systems or files", () => {
  const rowsSpec: QuestionnaireSpec = {
    ...spec,
    fields: [
      {
        key: "sources", kind: "rows", question: "Which systems or files does it come from? Add one row for each.",
        row: [
          { key: "name", kind: "text", label: "Name of the system or file" },
          { key: "kind", kind: "choice", label: "What kind is it?", choices: [{ value: "excel", label: "Excel workbook" }, { value: "api", label: "Third-party API" }] },
          { key: "tables", kind: "list", label: "Main tables, files or document types (a short list)" },
        ],
      },
      { key: "in_between", kind: "hops", question: "In between", hop: [{ key: "who", label: "Who" }, { key: "team", label: "Their team or system" }, { key: "step", label: "Where and what they change" }, { key: "order", label: "Step number" }, { key: "manual", label: "Done by hand" }] },
    ],
  };

  test("each system is a row with its kind and tables; a second row can be added; empty cells are not sent; the step carries its team and number", async () => {
    mock((c) => (c.url.endsWith("/answer/save") ? json(200, { saved: { id: "x", kpi_id: "k1", owner_name: "Tom Reyes", sample_title: null } }) : json(200, ownerForm({ questionnaire: rowsSpec }))));
    openOwner();
    const first = (await screen.findByText(F.measure(1, 2, "Funding capacity"))).closest("section") as HTMLElement;
    const user = userEvent.setup();
    const q = (text: string) => within(within(first).getByText(text).closest("fieldset") as HTMLElement);
    await user.type(within(first).getByLabelText("Name of the system or file"), "Performance workbook");
    await user.selectOptions(within(first).getByLabelText("What kind is it?"), "excel");
    await user.type(within(first).getByLabelText(/Main tables, files or document types/), "Fund returns, Benchmark levels");
    await user.click(within(first).getByRole("button", { name: F.addSource }));
    const second = within(first).getByRole("group", { name: F.sourceLabel(2) });
    await user.type(within(second).getByLabelText("Name of the system or file"), "Vendor API");
    await user.selectOptions(within(second).getByLabelText("What kind is it?"), "api");
    await user.click(q("Which systems or files does it come from? Add one row for each.").getByLabelText("I am sure"));
    await user.type(within(first).getByLabelText("Who"), "Tom");
    await user.type(within(first).getByLabelText("Their team or system"), "Investments");
    await user.type(within(first).getByLabelText("Step number"), "4");
    await user.click(q("In between").getByLabelText("My best guess"));
    await user.click(within(first).getByRole("button", { name: F.saveMeasure }));
    expect(await within(first).findByText(F.saved)).toBeInTheDocument();
    const sent = calls.find((c) => c.url.endsWith("/answer/save"));
    expect(sent?.body).toEqual({ kpi_id: "k1", answers: {
      sources: { value: [{ name: "Performance workbook", kind: "excel", tables: "Fund returns, Benchmark levels" }, { name: "Vendor API", kind: "api" }], mark: "stated" },
      in_between: { value: [{ who: "Tom", team: "Investments", step: "", order: "4", manual: false }], mark: "guessed" },
    } });
  });

  test("a saved row comes back filled in, a list as words", async () => {
    const cell = (value: unknown) => ({ value, mark: "stated", by: "Tom Reyes", from: "answer link", at: "2026-10-03T10:00:00+00:00" });
    const rec = { id: "x", kpi_id: "k1", owner_name: "Tom Reyes", sample_title: null, unanswered: [], sources: { ...cell([{ name: cell("Index provider API"), kind: cell("api"), tables: cell(["S&P 500 levels", "MSCI World levels"]), lands: { value: null, mark: "unknown", by: "Tom Reyes", from: "x", at: "t" } }]) } };
    mock(() => json(200, ownerForm({ questionnaire: rowsSpec, kpis: [{ id: "k1", name: "Funding capacity", answers: rec }, { id: "k2", name: "Capital call timing", answers: null }] })));
    openOwner();
    const first = (await screen.findByText(F.measure(1, 2, "Funding capacity"))).closest("section") as HTMLElement;
    expect(within(first).getByLabelText("Name of the system or file")).toHaveValue("Index provider API");
    expect(within(first).getByLabelText("What kind is it?")).toHaveValue("api");
    expect(within(first).getByLabelText(/Main tables, files or document types/)).toHaveValue("S&P 500 levels, MSCI World levels");
  });
});

describe("requests and the outstanding view", () => {
  test("loading, error, refused", async () => {
    mock(() => new Promise<Response>(() => undefined));
    const a = openRequests();
    expect(await screen.findByRole("status")).toHaveTextContent("Getting your requests…");  // R4 defect 9: not a bare "Loading..."
    a.unmount();
    mock(() => json(500, { detail: "boom" }));
    const b = openRequests();
    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong");
    b.unmount();
    mock(() => json(403, { error: "forbidden", message: "x" }));
    openRequests();
    expect(await screen.findByRole("alert")).toHaveTextContent("You do not have access");
  });

  test("empty: nobody is named yet, so there is nothing to send", async () => {
    mock(() => json(200, outstanding([], { waiting_on: [] })));
    openRequests();
    expect(await screen.findByText(R.nobodyToAsk)).toBeInTheDocument();
  });

  test("populated: who owes answers, how long they have waited, what Nira says, and waiting on", async () => {
    const rows = [
      row({ id: "r0", owner_name: "Arjun Rao", role: "data owner", state: "answered", answered_kpis: 2, remind_due: false, nira: null, kpis: [{ id: "k1", name: "Funding capacity" }, { id: "k2", name: "Capital call timing" }] }),
      row({ id: "r2", owner_name: "Tom Reyes", state: "opened", role: "business owner", days_waiting: 1, remind_due: false, nira: null, kpis: [{ id: "k1", name: "Funding capacity" }] }),
      row(),
    ];
    mock(() => json(200, outstanding(rows)));
    openRequests();
    expect((await screen.findAllByText(R.summary({ asked: 3, answered: 1 }))).length).toBeGreaterThan(0);
    expect(screen.getByText("Opened, not answered")).toBeInTheDocument();
    expect(screen.getByText("No reply, 3 days")).toBeInTheDocument();
    expect(screen.getByText(R.reminderDue)).toBeInTheDocument();
    expect(screen.getByText(/Wei Chen has not replied in 3 days/)).toBeInTheDocument();
    expect(screen.getByText(R.waitingOn("Distribution lag", ["Wei Chen"]))).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: R.remind })).toHaveLength(2); // the answered person cannot be reminded
    expect(document.body.textContent).not.toMatch(/ow-[0-9a-f]{32}/);
  });

  test("make requests shows each new link once, with the email to copy and no email sent", async () => {
    let made = false;
    mock((c) => {
      if (c.method === "POST") {
        made = true;
        return json(200, { new: 1, sent: [{ ...row({ id: "r9", state: "sent", days_waiting: 0, remind_due: false, nira: null, owner_name: "Tom Reyes" }), link_path: `/answer/${TOKEN}`,
          email: { subject: 'A few questions about "Funding capacity"', body: "Hello Tom Reyes,\n\nAnswer here: {link}\n\nThank you,\nNira" } }] });
      }
      return json(200, made ? outstanding([row({ id: "r9", state: "sent", owner_name: "Tom Reyes", days_waiting: 0, remind_due: false, nira: null })]) : outstanding([], { not_yet_asked: ["Tom Reyes"], waiting_on: [] }));
    });
    openRequests();
    const user = userEvent.setup();
    expect(await screen.findByText(R.notYetAsked(["Tom Reyes"]))).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: R.sendButton }));
    const link = (await screen.findByLabelText(R.linkLabel)) as HTMLInputElement;
    expect(link.value).toBe(`${window.location.origin}/answer/${TOKEN}`);
    expect((screen.getByLabelText(R.emailTitle) as HTMLTextAreaElement).value).toContain(`Answer here: ${link.value}`);
    expect(screen.getByText(R.linkHelp)).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: R.close }));
    expect(screen.queryByLabelText(R.linkLabel)).not.toBeInTheDocument();
  });

  test("Remind marks the reminder and gives Nira's words to copy, with no link in them", async () => {
    mock((c) => c.method === "POST"
      ? json(200, { request: row({ reminders: ["2026-10-04T09:00:00+00:00"], remind_due: false }), email: { subject: 'Reminder: a few questions about "Distribution lag"', body: "Please use the link in my earlier message." } })
      : json(200, outstanding([row()])));
    openRequests();
    await userEvent.setup().click(await screen.findByRole("button", { name: R.remind }));
    expect(await screen.findByText(R.reminderTitle("Wei Chen"))).toBeInTheDocument();
    expect(screen.queryByLabelText(R.linkLabel)).not.toBeInTheDocument();
    expect(calls.at(-2)).toMatchObject({ method: "POST", url: `${BASE}/baselines/${BID}/requests/r1/remind` });
  });

  test("Answer in a meeting instead calls the meeting route", async () => {
    mock((c) => c.method === "POST" ? json(200, { request: row({ state: "in_meeting" }) }) : json(200, outstanding([row()])));
    openRequests();
    await userEvent.setup().click(await screen.findByRole("button", { name: R.meeting }));
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/requests/r1/meeting"))).toBe(true));
  });

  test("the seven-day alert tells the organiser", async () => {
    mock(() => json(200, outstanding([row({ organiser_told: true })], { alerts: ["Wei Chen has not answered in 7 days. You may want to answer in a meeting instead."] })));
    openRequests();
    expect(await screen.findByText(R.tellsYou)).toBeInTheDocument();
    expect(screen.getAllByText(/answer in a meeting instead/).length).toBeGreaterThan(0);
  });
});

describe("answering in a meeting", () => {
  const answers = { questionnaire: spec, kpis: [{ id: "k3", name: "Distribution lag" }], answers: [] };
  test("empty: no measures", async () => {
    mock((c) => c.url.endsWith("/answers") ? json(200, { ...answers, kpis: [] }) : json(200, outstanding([])));
    openRequests(`/modules/m2_baseline/requests/${BID}/meeting`);
    expect(await screen.findByText(F.noMeasures)).toBeInTheDocument();
  });

  test("the person's name is needed, and the answers are saved on their behalf with it", async () => {
    mock((c) => c.url.endsWith("/answers") ? json(200, answers) : c.method === "PUT"
      ? json(200, { saved: { id: "x", kpi_id: "k3", owner_name: "Wei Chen", sample_title: null } }) : json(200, outstanding([row()])));
    openRequests(`/modules/m2_baseline/requests/${BID}/meeting`);
    expect(await screen.findByText(F.needName)).toBeInTheDocument();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(F.who), "Wei Chen");
    const form = screen.getByRole("form", { name: "Distribution lag" });
    await user.click(within(form).getByLabelText("Partly"));
    await user.click(within(within(form).getByText("Is it tracked today?").closest("fieldset") as HTMLElement).getByLabelText("My best guess"));
    await user.click(within(form).getByRole("button", { name: F.saveMeasure }));
    expect(await screen.findByText(F.meetingSaved("Wei Chen"))).toBeInTheDocument();
    const put = calls.find((c) => c.method === "PUT");
    expect(put?.url).toBe(`${BASE}/baselines/${BID}/meeting-answers`);
    expect(put?.body).toEqual({ owner_name: "Wei Chen", kpi_id: "k3", answers: { tracked_today: { value: "partly", mark: "guessed" } } });
  });
});

describe("reopening an answered request", () => {
  test("an answered person gets a Reopen button, which shows the new link once", async () => {
    const answered = row({ id: "r2", owner_name: "Tom Reyes", state: "answered", remind_due: false, nira: null, answered_kpis: 1 });
    mock((c) => c.method === "POST"
      ? json(200, { request: { ...answered, state: "sent" }, link_path: `/answer/${TOKEN}`, email: { subject: "s", body: `Answer here: http://localhost/answer/${TOKEN}` } })
      : json(200, outstanding([answered], { waiting_on: [] })));
    openRequests();
    await userEvent.setup().click(await screen.findByRole("button", { name: R.reopen }));
    expect(await screen.findByLabelText(R.linkLabel)).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST")).toMatchObject({ url: `${BASE}/baselines/${BID}/requests/r2/reopen` });
    expect(screen.queryByRole("button", { name: R.newLink })).not.toBeInTheDocument();
  });
});

describe("an owner with an account is sent to sign in to confirm", () => {
  test("no Confirm button on the link; a sign-in prompt that returns to the sign-off screen", async () => {
    const part = { kpi_id: "k1", part: "definition", label: "Definition", confirmed: false };
    mock(() => json(200, ownerForm({ confirmable: [], sign_in_parts: [part], sign_in_path: `/modules/m2_baseline/signoff/${BID}` })));
    openOwner();
    const link = await screen.findByRole("link", { name: F.signInButton });
    expect(link).toHaveAttribute("href", `/login?next=${encodeURIComponent(`/modules/m2_baseline/signoff/${BID}`)}`);
    expect(screen.queryByRole("button", { name: new RegExp(`^${F.confirmButton}`) })).toBeNull();
  });
});

describe("confirming my part from the answer link", () => {
  const confirmable = [{ kpi_id: "k1", part: "definition", label: "Definition", confirmed: false }];
  test("a nominee with no account sees the parts that are theirs and confirms one with the token in the header", async () => {
    mock((c) => c.url.endsWith("/answer/confirm")
      ? json(200, { confirmable: [{ ...confirmable[0], confirmed: true }] })
      : json(200, ownerForm({ confirmable })));
    openOwner();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: `${F.confirmButton}: ${F.confirmPart("Funding capacity", "Definition")}` }));
    expect(await screen.findByText(F.confirmedDone)).toBeInTheDocument();
    const call = calls.find((c) => c.url.endsWith("/answer/confirm"));
    expect(call).toMatchObject({ method: "POST", headers: { "X-Session-Token": TOKEN }, body: { kpi_id: "k1", part: "definition" } });
    expect(call?.url).not.toContain(TOKEN);
  });

  test("a person with nothing to confirm sees no confirm panel", async () => {
    mock(() => json(200, ownerForm()));
    openOwner();
    await screen.findByText(F.measure(1, 2, "Funding capacity"));
    expect(screen.queryByText(F.confirmTitle)).not.toBeInTheDocument();
  });

  test("a refusal is shown in the server's words", async () => {
    mock((c) => c.url.endsWith("/answer/confirm") ? json(409, { error: "already_confirmed", message: "You have already confirmed this part." }) : json(200, ownerForm({ confirmable })));
    openOwner();
    await userEvent.setup().click(await screen.findByRole("button", { name: new RegExp(F.confirmButton) }));
    expect(await screen.findByRole("alert")).toHaveTextContent("You have already confirmed this part.");
  });
});

describe("CRITIC-M2 round 4: the signed state and the link page", () => {
  test("a signed baseline shows the read-only banner on the requests page and turns its actions off", async () => {
    mock(() => json(200, outstanding([row()], { signed: true })));
    openRequests();
    expect(await screen.findByText("Signed: read-only")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: new RegExp(R.sendButton) })).toBeDisabled();
    expect(screen.getByRole("button", { name: R.remind })).toBeDisabled();
  });

  test("every owner is told they can answer without signing in", async () => {
    mock(() => json(200, ownerForm()));
    openOwner();
    expect(await screen.findByText(/You can answer here without signing in/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/No account is needed/);
  });

  test("on a signed baseline the owner's page says read-only and its fields are off", async () => {
    mock(() => json(200, ownerForm({ signed: true })));
    openOwner();
    expect(await screen.findByText("Signed: read-only")).toBeInTheDocument();
    expect(screen.queryByText(/new version/)).toBeNull(); // an owner has no sign-off step to go to
    expect(screen.getAllByRole("button", { name: F.saveMeasure })[0]).toBeDisabled();
    expect(screen.getByRole("button", { name: F.send })).toBeDisabled();
  });
});
