import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import type { Channel, Delivery, Summary } from "./api";
import CompletePage from "./CompletePage";
import DeliveryPage from "./DeliveryPage";
import SettingsPage from "./SettingsPage";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

const CH = (o: Partial<Channel>): Channel => ({ id: "ch-000001", kind: "slack", label: "Slack channel", title: "Slack channel", dashboard_id: "dash-00000001", status: "draft", live: false, set_up: true,
  when: { freq: "daily", at: "07:00" }, made_by_name: "Mei Chen", last_sent: null, sent_back: null, preview: { subject: "Board pack: net worth 100", text: "Board pack\nNet worth: 100" },
  can: { submit: false, approve: false, stop: false }, ...o });
const DEL = (o: Partial<Delivery> = {}): Delivery => ({ project_id: "prj-1", dashboards: [{ id: "dash-00000001", title: "Board pack" }], live_at: null, kinds: [
  { kind: "slack", label: "Slack channel" }, { kind: "email", label: "Email digest" }, { kind: "alert", label: "Threshold alert" }],
  settings: { channels: [], email: { configured: false, domains: [] } }, outbox: [], can: { make: true, go_live: false, settings: false },
  channels: [CH({ can: { submit: true, approve: false, stop: true } }), CH({ id: "ch-000002", kind: "teams", label: "Microsoft Teams channel", title: "Teams", set_up: false, status: "submitted", can: { submit: false, approve: true, stop: false } })], ...o });

function mock(delivery: Delivery, posts: string[] = [], extra: Record<string, unknown> = {}) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Mei", company_id: "evergreen", roles: ["analyst"] });
    if (init?.method && init.method !== "GET") { posts.push(`${init.method} ${url} ${init.body ?? ""}`); return json(200, extra[url] ?? {}); }
    if (url in extra) return json(200, extra[url]);
    if (url === "/api/v1/build/p/prj-1/delivery") return json(200, delivery);
    return json(404, { error: "not_found", message: "Not found." });
  }));
}
const page = (el: React.ReactElement, path: string) => render(<ThemeProvider><MemoryRouter initialEntries={[path]}><SessionProvider>
  <Routes><Route path="/centre/build/p/:projectId/*" element={el} /><Route path="/centre/build/delivery-settings" element={el} /></Routes></SessionProvider></MemoryRouter></ThemeProvider>);

test("delivery lists channels with state, warns when not set up, and a maker sends for approval", async () => {
  const posts: string[] = [];
  mock(DEL(), posts);
  page(<DeliveryPage />, "/centre/build/p/prj-1/delivery");
  expect(await screen.findByText("Choose where it goes")).toBeInTheDocument();
  expect(await screen.findByText("Draft")).toBeInTheDocument();
  expect(screen.getByText("Waiting for approval")).toBeInTheDocument();
  expect(screen.getByText(/Microsoft Teams channel is not set up yet/)).toBeInTheDocument();
  await userEvent.click(screen.getAllByRole("button", { name: "Preview" })[0]!);
  expect(screen.getByText(/Names are masked when a message leaves/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Send for approval" }));
  await waitFor(() => expect(posts).toContain("POST /api/v1/build/p/prj-1/delivery/channels/ch-000001/submit {}"));
});

test("an approver can approve, and send back needs a reason", async () => {
  const posts: string[] = [];
  mock(DEL(), posts);
  page(<DeliveryPage />, "/centre/build/p/prj-1/delivery");
  const approve = await screen.findByRole("button", { name: "Approve" });
  const back = screen.getByRole("button", { name: "Send back" });
  expect(back).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Why send it back"), "Wrong people");
  expect(back).toBeEnabled();
  await userEvent.click(approve);
  await waitFor(() => expect(posts.some((p) => p.endsWith("/ch-000002/approve {}"))).toBe(true));
});

test("go live shows only when a channel is approved, and says nothing is sent", async () => {
  const posts: string[] = [];
  mock(DEL({ can: { make: true, go_live: true, settings: true }, channels: [CH({ status: "approved", approved_by_name: "Daniel Foo" })] }), posts);
  page(<DeliveryPage />, "/centre/build/p/prj-1/delivery");
  expect(await screen.findByText(/Approved by Daniel Foo/)).toBeInTheDocument();
  expect(screen.getByText(/Nothing is sent when you press Go live/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Go live" }));
  await waitFor(() => expect(posts.some((p) => p.includes("/delivery/go-live"))).toBe(true));
  expect(await screen.findByText(/Nothing was sent just now/)).toBeInTheDocument();
});

test("a held message sits in the outbox with its preview and can be sent again", async () => {
  const posts: string[] = [];
  mock(DEL({ channels: [], outbox: [{ id: "ob-1", channel_id: "ch-000001", kind: "slack", title: "Slack channel", at: "2026-10-13T07:00:00+00:00", trigger: "daily", status: "held",
    reason: "Slack channel is not set up yet. Ask your administrator. The message is kept here.", subject: "Board pack: net worth 100", preview: "Board pack\nNet worth: 100" }] }), posts);
  page(<DeliveryPage />, "/centre/build/p/prj-1/delivery");
  expect(await screen.findByText("Kept here, not sent")).toBeInTheDocument();
  expect(screen.getByText(/Net worth: 100/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Send again" }));
  await waitFor(() => expect(posts).toContain("POST /api/v1/build/p/prj-1/delivery/outbox/ob-1/retry {}"));
});

test("empty state when no dashboard is approved", async () => {
  mock(DEL({ dashboards: [], channels: [] }));
  page(<DeliveryPage />, "/centre/build/p/prj-1/delivery");
  expect(await screen.findByText("No approved dashboard yet")).toBeInTheDocument();
  expect(screen.queryByText("Add a channel")).toBeNull();
});

test("refused shows a plain message", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => url === "/api/auth/me" ? json(200, { display_name: "Sofia", company_id: "evergreen", roles: ["participant"] }) : json(403, { error: "not_allowed", message: "You do not have access to this." })));
  page(<DeliveryPage />, "/centre/build/p/prj-1/delivery");
  expect(await screen.findByRole("alert")).toHaveTextContent("You do not have access to this.");
});

test("settings save the secret by name and host", async () => {
  const posts: string[] = [];
  mock(DEL(), posts, { "/api/v1/settings/delivery": { channels: [{ kind: "slack", label: "Slack channel", secret: "", host: "", configured: false }], email: { configured: false, domains: ["acme.test"] } } });
  page(<SettingsPage />, "/centre/build/delivery-settings");
  await userEvent.type(await screen.findByLabelText(/Name of the secret/), "SH_SLACK_WEBHOOK");
  await userEvent.type(screen.getByLabelText(/Host it sends to/), "hooks.slack.com");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(posts[0]).toContain('"secret":"SH_SLACK_WEBHOOK","host":"hooks.slack.com"'));
  expect(screen.getByText(/messages are kept in the outbox/)).toBeInTheDocument();
});

test("project complete lists only what the records say", async () => {
  const S: Summary = { project_id: "prj-1", title: "Monthly report", complete: true, live_at: "2026-10-13T10:00:00+00:00", verified: [{ text: "All 2 delivery channels approved by someone who did not set them up", by: "Daniel Foo, Raj Patel" }],
    delivered_to: [{ id: "ch-1", kind: "slack", label: "Slack channel", title: "Slack channel", approved_by: "Daniel Foo", approved_at: "2026-10-13", live: true }], not_approved: [] };
  mock(DEL(), [], { "/api/v1/build/p/prj-1/delivery/summary": S });
  page(<CompletePage />, "/centre/build/p/prj-1/complete");
  expect(await screen.findByText("Monthly report is live.")).toBeInTheDocument();
  expect(screen.getByText(/All 2 delivery channels approved/)).toBeInTheDocument();
  expect(screen.getByText("Slack channel", { selector: "strong" })).toBeInTheDocument();
});

const FIG = { month: "2026-09", month_name: "September 2026", portfolio_pct: "4.17", benchmark_pct: "2.71", difference_pts: "1.46", version: 1, name: "Family benchmark", code: "BLEND", portfolio: "EG",
  state: "accepted", accepted_by: "Mei Chen", sentence: "September performance: the liquid portfolio returned 4.17% against the family benchmark of 2.71%, ahead by 1.46 points.",
  email_subject: "September: portfolio 4.17%, benchmark 2.71%, ahead by 1.46 points", note_line: "Ahead of the benchmark by 1.46 points in September.", mix: [] };

test("D4: the side panel shows the benchmark sentence, the email subject, the Morning Note line and Where is this from?; a stopped channel sits last", async () => {
  const stopped = CH({ id: "ch-000009", status: "stopped", title: "Slack channel", can: { submit: false, approve: false, stop: false } });
  const live = CH({ id: "ch-000001", status: "approved", live: true, title: "Slack channel", preview: { subject: "S", text: "Board pack\nNet worth: 100\nOpen the dashboard in Signal Harbor under Consume.", tile: "tile-1" } });
  mock(DEL({ figures: FIG, channels: [stopped, live] }), [], { "/api/trail?kind=tile&id=tile-1": { kind: "tile", id: "tile-1", title: "Net worth", figure: null, steps: [] } });
  page(<DeliveryPage />, "/centre/build/p/prj-1/delivery");
  expect(await screen.findByText(/ahead by 1.46 points\./)).toBeInTheDocument();
  expect(screen.getByText(/September: portfolio 4.17%/)).toBeInTheDocument();
  expect(screen.getByText(/Ahead of the benchmark by 1.46 points in September/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Where is this from?" })).toBeInTheDocument();
  const cards = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
  expect(cards.indexOf("Slack channel")).toBeLessThan(cards.lastIndexOf("Slack channel"));
  expect(screen.getAllByText("Stopped")).toHaveLength(1);
  const items = screen.getAllByRole("listitem").filter((li) => li.className.includes("d1-card"));
  expect(items[0]).toHaveTextContent("Approved");
  expect(items[items.length - 1]).toHaveTextContent("Stopped");
});

test("D5: four steps, what was verified with the figure line, and what entered the company map", async () => {
  const S: Summary = { project_id: "prj-1", title: "Monthly report", complete: true, live_at: "2026-10-13T10:00:00+00:00", figures: FIG, not_approved: [], delivered_to: [],
    steps: [{ n: 1, label: "Intent", who: "North, the industry expert", state: "Signed by Mei Chen" }, { n: 2, label: "Architecture", who: "Span maps it to your data", state: null },
      { n: 3, label: "Pipelines", who: "Span tries it, then runs it", state: "Verified by Leo Park" }, { n: 4, label: "Dashboards and delivery", who: "Lumen builds views and sends them", state: "Approved and delivered to 2 channels" }],
    verified: [{ text: "September 2026 figures match the certified report: portfolio 4.17%, benchmark 2.71%, 1.46 points", by: "Mei Chen" }],
    knowledge: [{ group: "Sources", items: [{ text: "admin", verified: true }] }, { group: "People", items: [{ text: "Mei Chen, owner", verified: false }] }] };
  mock(DEL(), [], { "/api/v1/build/p/prj-1/delivery/summary": S });
  page(<CompletePage />, "/centre/build/p/prj-1/complete");
  expect(await screen.findByText("Signed by Mei Chen")).toBeInTheDocument();
  expect(screen.getByText("Not recorded")).toBeInTheDocument();
  expect(screen.getByText(/benchmark 2.71%, 1.46 points/)).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "Added to the company knowledge map" })).toHaveTextContent("2 items");
  expect(screen.getAllByText("Verified")).toHaveLength(1);
  expect(screen.getByText("PROJECT COMPLETE · 13 OCT 2026")).toBeInTheDocument();   // V6 (D5): the eyebrow, Back to Build and "Before this"
  expect(screen.getByRole("link", { name: "Back to Build" })).toHaveAttribute("href", "/centre/build");
  expect(screen.getByRole("link", { name: "Open in the map" })).toHaveAttribute("href", "/centre/map");
  expect(screen.getByRole("note")).toHaveTextContent(/BEFORE THIS\s*Go live was pressed on 13 Oct 2026/);
});
